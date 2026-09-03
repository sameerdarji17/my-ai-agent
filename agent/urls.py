from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.AgentChatView.as_view(), name="agent-chat"),
    path("upload/", views.UploadFileView.as_view(), name="agent-upload"),
    path("conversations/", views.ConversationListView.as_view(), name="conversation-list"),
    path("conversations/<uuid:conversation_id>/", views.ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<uuid:conversation_id>/share/", views.ShareConversationView.as_view(),
         name="conversation-share"),

    # Google Auth Endpoints
    path("auth/google/", views.google_auth_api, name="google-auth-api"),
    path("google-auth/", views.google_auth_api, name="google-auth-fallback"),

    # Live Email Diagnostic Endpoints
    path("test-welcome/", views.test_welcome_view, name="test-welcome"),
    path("test-email/", views.test_email_view, name="test-email"),
]