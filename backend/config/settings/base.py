from __future__ import annotations

from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-local-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if host]


def build_database_config(default_engine: str = "postgresql") -> dict:
    engine = os.environ.get("BAMBOO_DB_ENGINE", default_engine).lower()
    if engine == "sqlite":
        sqlite_name = os.environ.get("BAMBOO_DB_SQLITE_NAME", "db.sqlite3")
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / sqlite_name,
            }
        }
    if engine == "postgresql":
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.environ.get("BAMBOO_DB_NAME", "bamboo_meta"),
                "USER": os.environ.get("BAMBOO_DB_USER", "postgres"),
                "PASSWORD": os.environ.get("BAMBOO_DB_PASSWORD", ""),
                "HOST": os.environ.get("BAMBOO_DB_HOST", "127.0.0.1"),
                "PORT": os.environ.get("BAMBOO_DB_PORT", "5432"),
                "OPTIONS": {
                    "sslmode": os.environ.get("BAMBOO_DB_SSLMODE", "prefer"),
                },
            }
        }
    raise ValueError(f"Unsupported BAMBOO_DB_ENGINE: {engine}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.buildmeta",
    "apps.api",
    "apps.ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "apps" / "ui" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.ui.context_processors.provider_context",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = build_database_config()

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
