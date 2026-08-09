from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from agent import views as agent_views

urlpatterns = [
    # Main Root Route - Opening base URL opens chat directly
    path("", agent_views.chat_page, name="chat-page"),

    path("admin/", admin.site.urls),
    path("", include("agent.urls")),
    path("billing/", include("billing.urls")),

    # Custom Auth
    path("signup/", agent_views.signup_view, name="signup"),
    path("login/", agent_views.login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="chat-page"), name="logout"),
    path("verify-email/<str:uidb64>/<str:token>/", agent_views.verify_email_view, name="verify-email"),

    # Password Reset Routes
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt"
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"
    ), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html"
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html"
    ), name="password_reset_complete"),
]