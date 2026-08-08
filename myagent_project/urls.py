from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from agent.views import chat_page, signup_view, verify_email_view, shared_conversation_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/agent/", include("agent.urls")),
    path("billing/", include("billing.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="chat-page"), name="logout"),
    path("signup/", signup_view, name="signup"),
    path("verify-email/<uidb64>/<token>/", verify_email_view, name="verify-email"),
    path("share/<uuid:conversation_id>/", shared_conversation_view, name="shared-conversation"),
    path("", chat_page, name="chat-page"),
]
