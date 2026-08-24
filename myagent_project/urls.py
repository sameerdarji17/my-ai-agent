from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from agent import views as agent_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Direct Google Search Console Verification Route
    path("google3Iy5jCu5wi24rANYhguN4Mm6cJJ6Av0ee6JM5TAN6mg.html",
         lambda r: HttpResponse("google-site-verification: google3Iy5jCu5wi24rANYhguN4Mm6cJJ6Av0ee6JM5TAN6mg.html")),

    path("", agent_views.chat_page, name="chat-page"),
    path("login/", agent_views.login_view, name="login"),
    path("signup/", agent_views.signup_view, name="signup"),
    path("logout/", agent_views.logout_view, name="logout"),
    path("test-email/", agent_views.test_email_view, name="test-email"),
    path("api/google-auth/", agent_views.google_auth_api, name="google-auth-api"),
    path("verify-email/<str:uidb64>/<str:token>/", agent_views.verify_email_view, name="verify-email"),
    path("api/agent/chat/", agent_views.AgentChatView.as_view(), name="agent-chat"),
    path("api/agent/conversations/", agent_views.ConversationListView.as_view(), name="conversation-list"),
    path("api/agent/conversations/<uuid:conversation_id>/", agent_views.ConversationDetailView.as_view(),
         name="conversation-detail"),
    path("api/agent/upload/", agent_views.UploadFileView.as_view(), name="upload-file"),
    path("api/agent/conversations/<uuid:conversation_id>/share/", agent_views.ShareConversationView.as_view(),
         name="share-conversation"),
    path("share/<uuid:conversation_id>/", agent_views.shared_conversation_view, name="shared-conversation"),
    path("billing/", include("billing.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
]