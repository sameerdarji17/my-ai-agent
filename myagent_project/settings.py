"""
Django settings for myagent_project.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# Ensure GEMINI_API_KEY is read from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# SECURITY
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-this-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.up.railway.app",
    "https://web-production-d823e.up.railway.app",
    "https://sd-agent.up.railway.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

env_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS")
if env_csrf:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in env_csrf.split(",") if origin.strip()])

# ---------------------------------------------------------------------------
# APPS
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "agent",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myagent_project.urls"

# ---------------------------------------------------------------------------
# TEMPLATES (FIXED BACKEND PATH)
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myagent_project.wsgi.application"
ASGI_APPLICATION = "myagent_project.asgi.application"

# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------
_database_url = os.environ.get("DATABASE_URL", "").strip()
if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": dj_database_url.parse(f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# STATIC FILES CONFIGURATION
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "20/min", "user": "60/min"},
}

# ---------------------------------------------------------------------------
# AGENT / LLM CONFIG
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "")

AGENT_FILES_ROOT = BASE_DIR / "agent_files"
AGENT_FILES_ROOT.mkdir(exist_ok=True)

SANDBOX_RUNS_ROOT = BASE_DIR / "sandbox_runs"
SANDBOX_RUNS_ROOT.mkdir(exist_ok=True)

CODE_EXEC_TIMEOUT_SECONDS = int(os.environ.get("CODE_EXEC_TIMEOUT_SECONDS", "8"))
CODE_EXEC_MAX_OUTPUT_CHARS = 4000

MAX_AGENT_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "10"))
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "8"))

# ---------------------------------------------------------------------------
# EMAIL CONFIGURATION (SSL 465 & TLS 587 Auto-Switch with Timeout)
# ---------------------------------------------------------------------------
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")

try:
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))
except Exception:
    EMAIL_PORT = 465

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip().replace(" ", "")

# Port 465 uses SSL, Port 587 uses TLS
if EMAIL_PORT == 465:
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
else:
    EMAIL_USE_SSL = False
    EMAIL_USE_TLS = True

EMAIL_TIMEOUT = 15  # Gunicorn timeout / crash hone se rokta hai

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"SD AGENT <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "SD AGENT <support@sdagent.ai>"
)
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://sd-agent.up.railway.app")

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "chat-page"
LOGOUT_REDIRECT_URL = "chat-page"

# ---------------------------------------------------------------------------
# RAZORPAY
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

# ---------------------------------------------------------------------------
# PERSISTENT SESSION & COOKIE SECURITY (HTTPS / RAILWAY)
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600  # 14 Days
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# Production Cookie Security
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True