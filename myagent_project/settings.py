"""
Django settings for myagent_project.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # loads variables from .env if the file exists

# ---------------------------------------------------------------------------
# SECURITY
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-this-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

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
# Uses DATABASE_URL if set and non-empty (Railway/Render auto-inject this
# when you add a Postgres addon) — falls back to local SQLite otherwise.
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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
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
# AGENT / LLM CONFIG  (values come from environment variables — see .env.example)
# ---------------------------------------------------------------------------
# Groq is the default provider: it has a generous free tier, is OpenAI-API
# compatible, and needs no billing setup. Get a free key at console.groq.com
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Optional: switch to Anthropic (paid) instead by setting LLM_PROVIDER=anthropic
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # "groq" or "anthropic"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")  # web search provider

# OCR.space — free API for reading text from uploaded images (e.g. error
# screenshots). "helloworld" is OCR.space's shared public demo key with low
# limits — get your own free key (25,000/month) at https://ocr.space/ocrapi
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "")

# Directory where uploaded / readable files for the "read_file" tool must live.
# The tool refuses to read anything outside this directory (path-traversal guard).
AGENT_FILES_ROOT = BASE_DIR / "agent_files"
AGENT_FILES_ROOT.mkdir(exist_ok=True)

# Directory used as a scratch space for the code-execution tool.
SANDBOX_RUNS_ROOT = BASE_DIR / "sandbox_runs"
SANDBOX_RUNS_ROOT.mkdir(exist_ok=True)

# Hard limits for the code-execution tool (see agent/tools.py for details)
CODE_EXEC_TIMEOUT_SECONDS = int(os.environ.get("CODE_EXEC_TIMEOUT_SECONDS", "8"))
CODE_EXEC_MAX_OUTPUT_CHARS = 4000

MAX_AGENT_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "10"))
# How many recent messages to send to the LLM per request — keeps token
# usage bounded on long conversations (important for free-tier rate limits).
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "8"))

# ---------------------------------------------------------------------------
# EMAIL (used for real signup verification links)
# ---------------------------------------------------------------------------
# If EMAIL_HOST is not set, emails print to the terminal (console backend) —
# handy for local testing without needing a real mailbox. Set EMAIL_HOST etc.
# in .env to send real emails (e.g. Gmail app password, or a free service
# like Brevo/SendGrid/Mailgun).
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SD AGENT <no-reply@myagent.local>")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "chat-page"
LOGOUT_REDIRECT_URL = "chat-page"

# ---------------------------------------------------------------------------
# RAZORPAY (billing app) — get keys at https://dashboard.razorpay.com/app/keys
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
