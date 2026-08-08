import os

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
from .forms import SignupForm

FREE_ANON_MESSAGE_LIMIT = 3
FREE_MESSAGE_LIMIT = 8  # messages allowed per rolling window
FREE_WINDOW_HOURS = 5  # window length in hours


def chat_page(request):
    """Serves the browser-based chat UI (templates/agent/chat.html)."""
    is_premium = False
    display_name = ""
    if request.user.is_authenticated:
        from billing.models import Subscription

        sub, _ = Subscription.objects.get_or_create(user=request.user, defaults={"plan": "free", "status": "paid"})
        is_premium = sub.is_premium
        display_name = request.user.first_name or request.user.username
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


def _send_verification_email(request, user):
    """Safely attempts to send verification email without crashing if SMTP fails."""
    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Fetch live Railway base URL
        site_url = getattr(settings, "SITE_BASE_URL", "https://sd-agent.up.railway.app").rstrip("/")
        verify_url = f"{site_url}/verify-email/{uid}/{token}/"

        send_mail(
            subject="Verify your email — SD AGENT",
            message=(
                f"Hi {user.first_name or user.username},\n\nPlease verify your email by clicking the link below:\n\n"
                f"{verify_url}\n\nIf you didn't sign up, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,  # Prevents 500 error if email service is down
        )
    except Exception:
        pass


def signup_view(request):
    """Handles signup and triggers the verification email process."""
    success_msg = None
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False  # Set inactive until link click
                user.save()

                # Send verification email safely in background
                _send_verification_email(request, user)

                # Success message passed to templates/registration/signup.html
                success_msg = f"Signup successful! We have sent a verification link to {user.email}. Please check your mail inbox, click the link, and log in."
            except Exception as e:
                form.add_error(None, f"Signup Error: {str(e)}")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {
        "form": form,
        "success_msg": success_msg,
    })


def verify_email_view(request, uidb64, token):
    """Handles verification link click from Gmail."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        auth_login(request, user)  # Auto-login on email link click
        return redirect("chat-page")

    return render(request, "registration/verify_failed.html")


class AgentChatView(APIView):
    """
    POST /api/agent/chat/
    Handles limits, authentication checks, and routes messages to orchestrator.
    """

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_premium = False

        if request.user.is_authenticated:
            from billing.models import Subscription

            sub, _ = Subscription.objects.get_or_create(user=request.user, defaults={"plan": "free", "status": "paid"})
            is_premium = sub.is_premium

            # Check Free User Message Limit
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
                                "ke baad phir se try kar sakte hain, ya Premium le kar unlimited "
                                "use kar sakte hain."
                            ),
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
        else:
            # Anonymous / Non-logged in Users Check
            if not request.session.session_key:
                request.session.save()
            count = request.session.get("anon_msg_count", 0)
            if count >= FREE_ANON_MESSAGE_LIMIT:
                return Response(
                    {
                        "login_required": True,
                        "upgrade_required": False,
                        "detail": "Free message limit khatam ho gaya. Aage chalane ke liye login/signup karein.",
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
    """GET /api/agent/conversations/<id>/ -- full history + tool trace."""

    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)


class ConversationListView(APIView):
    """GET /api/agent/conversations/ -- list this user's conversations."""

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
    """POST /api/agent/upload/ -- saves uploaded file for read_file tool."""

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
    """POST /api/agent/conversations/<id>/share/ -- creates public link."""

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        conversation.is_shared = True
        conversation.save(update_fields=["is_shared"])
        share_url = f"{settings.SITE_BASE_URL}/share/{conversation.id}/"
        return Response({"share_url": share_url})


def shared_conversation_view(request, conversation_id):
    """Public read-only conversation view."""
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