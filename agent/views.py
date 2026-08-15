import os
import json
import uuid
import urllib.request
import urllib.parse

from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser

from .models import Conversation, Message
from .orchestrator import AgentOrchestrator
from .serializers import ChatRequestSerializer, ConversationSerializer

FREE_ANON_MESSAGE_LIMIT = 3
FREE_MESSAGE_LIMIT = 10  # 8 से बढ़ाकर 10 कर दिया गया है
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


@csrf_exempt
def google_auth_api(request):
    """Universal Google OAuth Login Handler (Supports Redirect & Direct Token)."""
    access_token = request.GET.get("access_token")
    email = ""
    full_name = ""

    if not access_token and request.method == "POST":
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            access_token = body_data.get("access_token")
        except Exception:
            pass

    if not access_token and request.method == "GET":
        return HttpResponse("""
            <!DOCTYPE html>
            <html>
            <head><title>Logging In...</title></head>
            <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #09090B; color: #fff;">
                <div style="text-align: center;">
                    <p style="font-size: 18px;">Logging you in to SD AGENT...</p>
                </div>
                <script>
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const token = params.get('access_token');
                    if (token) {
                        window.location.href = '/api/google-auth/?access_token=' + encodeURIComponent(token);
                    } else {
                        window.location.href = '/signup/';
                    }
                </script>
            </body>
            </html>
        """)

    if access_token:
        try:
            req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                user_info = json.loads(response.read().decode("utf-8"))
                email = user_info.get("email", "").strip().lower()
                full_name = user_info.get("name", "").strip()
        except Exception as e:
            print("Google UserInfo API Error:", e)

    if not email:
        return redirect("signup")

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        base_username = email.split("@")[0]
        username = f"{base_username}_{uuid.uuid4().hex[:6]}"
        name_parts = full_name.split(" ", 1) if full_name else [base_username]
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User.objects.create_user(
            username=username,
            email=email,
            password=User.objects.make_random_password(),
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )

    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    request.session.save()

    return HttpResponseRedirect("/")


def signup_view(request):
    """Single-Flow Email Authentication."""
    if request.user.is_authenticated:
        return redirect("chat-page")

    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        full_name = request.POST.get("full_name", "").strip()

        if not email or not password:
            error = "Email and password are required."
        else:
            try:
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    if user.check_password(password):
                        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                        return redirect("chat-page")
                    else:
                        error = "Invalid password for this email address."
                else:
                    base_username = email.split("@")[0]
                    username = f"{base_username}_{uuid.uuid4().hex[:6]}"
                    name_parts = full_name.split(" ", 1) if full_name else [base_username]
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    new_user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True
                    )
                    auth_login(request, new_user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect("chat-page")
            except Exception as e:
                error = f"Authentication error: {str(e)}"

    return render(request, "registration/signup.html", {"error": error})


def login_view(request):
    """Renders signup view directly."""
    return signup_view(request)


def logout_view(request):
    """Logs out the user and redirects back to signup page."""
    auth_logout(request)
    return redirect("signup")


def verify_email_view(request, uidb64, token):
    """Fallback view for verify-email URL route."""
    return redirect("chat-page")


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
                request.session.create()
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
            conversations = Conversation.objects.filter(owner=request.user).order_by('-updated_at')[:50]
        else:
            if not request.session.session_key:
                return Response([])
            conversations = Conversation.objects.filter(session_key=request.session.session_key).order_by('-updated_at')[:50]
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