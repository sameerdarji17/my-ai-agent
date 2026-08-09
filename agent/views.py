import os
import threading

from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser

from .models import Conversation, Message
from .orchestrator import AgentOrchestrator
from .serializers import ChatRequestSerializer, ConversationSerializer
from .forms import SignupForm, CustomLoginForm

FREE_ANON_MESSAGE_LIMIT = 3
FREE_MESSAGE_LIMIT = 8
FREE_WINDOW_HOURS = 5


def chat_page(request):
    """Serves the browser-based chat UI."""
    is_premium = False
    display_name = ""
    if request.user.is_authenticated:
        from billing.models import Subscription

        sub, _ = Subscription.objects.get_or_create(user=request.user, defaults={"plan": "free", "status": "paid"})
        is_premium = sub.is_premium
        display_name = request.user.get_full_name() or request.user.first_name or request.user.email.split('@')[0]
    return render(
        request,
        "agent/chat.html",
        {
            "agent_name": "SD AGENT",
            "is_authenticated": request.user.is_authenticated,
            "username": display_name,
            "is_premium": is_premium,
        },
    )


def _send_email_in_background(subject, message, recipient_email):
    """Sends email asynchronously without blocking or crashing execution."""
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost")
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient_email],
            fail_silently=True,
        )
    except Exception:
        pass


def _send_welcome_email(user):
    """Sends Welcome Email to newly registered user."""
    try:
        subject = "Welcome to SD AGENT 🎉"
        message = (
            f"Hi {user.first_name or user.email},\n\n"
            f"Welcome to SD AGENT! 🎉\n\n"
            f"Your account is now active. You can chat with your AI agent, search the web, execute code, upload files, and more.\n\n"
            f"Happy Chatting!\nSD AGENT Team"
        )
        thread = threading.Thread(
            target=_send_email_in_background,
            args=(subject, message, user.email)
        )
        thread.start()
    except Exception:
        pass


def signup_view(request):
    """Instant signup and auto-login view to guarantee zero login blocks."""
    if request.user.is_authenticated:
        return redirect("chat-page")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = True  # Instantly active so login never blocks
                user.save()

                # Auto-login immediately after registration
                auth_login(request, user)

                # Send Welcome Email in background
                _send_welcome_email(user)

                return redirect("chat-page")
            except Exception as e:
                form.add_error(None, f"Signup Error: {str(e)}")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {
        "form": form,
        "show_modal": False,
    })


def login_view(request):
    """Login view using Email and Password."""
    if request.user.is_authenticated:
        return redirect("chat-page")

    if request.method == "POST":
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("chat-page")
    else:
        form = CustomLoginForm()

    return render(request, "registration/login.html", {"form": form})


def verify_email_view(request, uidb64, token):
    """Fallback email verification handler."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        auth_login(request, user)
        return redirect("chat-page")

    return render(request, "registration/verify_failed.html")


class AgentChatView(APIView):
    """POST /api/agent/chat/"""

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_premium = False

        if request.user.is_authenticated:
            from billing.models import Subscription

            sub, _ = Subscription.objects.get_or_create(user=request.user, defaults={"plan": "free", "status": "paid"})
            is_premium = sub.is_premium

            if not is_premium:
                from django.utils import timezone
                from datetime import timedelta

                window_start = timezone.now() - timedelta(hours=FREE_WINDOW_HOURS)
                messages_in_window = Message.objects.filter(
                    role="user", conversation__owner=request.user, created_at__gte=window_start
                ).order_by("created_at")
                count = messages_in_window.count()

                if count >= FREE_MESSAGE_LIMIT:
                    earliest = messages_in_window.first()
                    reset_time = earliest.created_at + timedelta(
                        hours=FREE_WINDOW_HOURS) if earliest else timezone.now()
                    reset_time_local = timezone.localtime(reset_time)
                    return Response(
                        {
                            "login_required": False,
                            "upgrade_required": True,
                            "reset_time": reset_time.isoformat(),
                            "detail": (
                                f"Free limit khatam ho gaya. Aap {reset_time_local.strftime('%I:%M %p')} "
                                "ke baad phir se try kar sakte hain, ya Premium le kar unlimited use kar sakte hain."
                            ),
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
        else:
            if not request.session.session_key:
                request.session.save()
            count = request.session.get("anon_msg_count", 0)
            if count >= FREE_ANON_MESSAGE_LIMIT:
                return Response(
                    {
                        "login_required": True,
                        "upgrade_required": False,
                        "detail": "Free limit khatam ho gaya. Aage chalane ke liye login/signup karein.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        conv_id = data.get("conversation_id")
        if conv_id:
            conversation = get_object_or_404(Conversation, id=conv_id)
        else:
            owner = request.user if request.user.is_authenticated else None
            session_key = "" if request.user.is_authenticated else (request.session.session_key or "")
            conversation = Conversation.objects.create(
                title=data["message"][:60],
                owner=owner,
                session_key=session_key,
            )

        agent = AgentOrchestrator(conversation, is_premium=is_premium, style=data.get("style", "normal"))
        result = agent.run(data["message"])

        if not request.user.is_authenticated:
            request.session["anon_msg_count"] = request.session.get("anon_msg_count", 0) + 1

        return Response(
            {
                "conversation_id": str(conversation.id),
                "reply": result["reply"],
                "tool_trace": result["tool_trace"],
            },
            status=status.HTTP_200_OK,
        )


class ConversationDetailView(APIView):
    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)


class ConversationListView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            conversations = Conversation.objects.filter(owner=request.user)[:50]
        else:
            if not request.session.session_key:
                request.session.save()
            conversations = Conversation.objects.filter(session_key=request.session.session_key)[:50]
        serializer = ConversationSerializer(conversations, many=True)
        return Response(serializer.data)


class UploadFileView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        max_size_mb = 5
        if f.size > max_size_mb * 1024 * 1024:
            return Response({"error": f"File too big (max {max_size_mb}MB)"}, status=status.HTTP_400_BAD_REQUEST)

        safe_name = os.path.basename(f.name)
        dest_path = os.path.join(settings.AGENT_FILES_ROOT, safe_name)
        with open(dest_path, "wb+") as destination:
            for chunk in f.chunks():
                destination.write(chunk)

        return Response({"filename": safe_name}, status=status.HTTP_201_CREATED)


class ShareConversationView(APIView):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        conversation.is_shared = True
        conversation.save(update_fields=["is_shared"])
        share_url = f"{settings.SITE_BASE_URL}/share/{conversation.id}/"
        return Response({"share_url": share_url})


def shared_conversation_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, is_shared=True)
    messages_out = []
    for m in conversation.messages.order_by("created_at"):
        if m.role == "user":
            messages_out.append({"role": "user", "text": m.content if isinstance(m.content, str) else str(m.content)})
        elif m.role == "assistant":
            text = ""
            if isinstance(m.content, str):
                text = m.content
            elif isinstance(m.content, dict):
                text = m.content.get("content", "") or ""
            if text:
                messages_out.append({"role": "assistant", "text": text})
    return render(
        request,
        "agent/shared_chat.html",
        {"conversation": conversation, "messages": messages_out, "agent_name": "SD AGENT"},
    )