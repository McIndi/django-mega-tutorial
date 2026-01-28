"""
For more information on this file, see
https://docs.djangoproject.com/en/6.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path
import os
import sys
import logging
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("The DJANGO_SECRET_KEY environment variable is not set.")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG", default=False)
if DEBUG:
    logging.warning("Django DEBUG mode is ON. This should be turned off in production!")
else:
    # Production security headers
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_SECURITY_POLICY = {
        "default-src": ("'self'",),
        "script-src": ("'self'", "cdn.jsdelivr.net"),
        "style-src": ("'self'", "cdn.jsdelivr.net"),
    }

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if DEBUG is False and not ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set when DEBUG=False")

# Proxy configuration
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=False)

# Email
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=1025 if DEBUG else 587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_SSL = env.bool("DJANGO_EMAIL_USE_SSL", default=False)
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=not EMAIL_USE_SSL)
EMAIL_TIMEOUT = env.int("DJANGO_EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="noreply@example.com")
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_REPLY_TO = env.list("DJANGO_EMAIL_REPLY_TO", default=[])
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="")

# Admin email notifications for errors (500s)
ADMINS = [
    (name.strip(), email.strip())
    for name, email in [
        tuple(admin.split(":")) for admin in env.list("DJANGO_ADMINS", default=[])
    ]
]
MANAGERS = ADMINS

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "core",
    "links",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
#
# Configuration priority:
# 1. If DATABASE_ENGINE env var is set, use that backend with provided credentials
# 2. Otherwise, default to SQLite (suitable for CI and local development)
#
# For PostgreSQL in Docker, set:
#   DATABASE_ENGINE=postgresql
#   DATABASE_NAME=<db_name>
#   DATABASE_USER=<db_user>
#   DATABASE_PASSWORD=<db_password>
#   DATABASE_HOST=<host>
#   DATABASE_PORT=<port>

if env("DATABASE_ENGINE", default=None):
    # Use PostgreSQL (or other database specified by DATABASE_ENGINE)
    if env("DATABASE_ENGINE") == "postgresql":
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": env("DATABASE_NAME", default="django_saas"),
                "USER": env("DATABASE_USER", default="postgres"),
                "PASSWORD": env("DATABASE_PASSWORD", default=""),
                "HOST": env("DATABASE_HOST", default="localhost"),
                "PORT": env("DATABASE_PORT", default="5432"),
            }
        }
    else:
        # Generic fallback for other database engines
        DATABASES = {
            "default": {
                "ENGINE": f"django.db.backends.{env('DATABASE_ENGINE')}",
                "NAME": env("DATABASE_NAME", default="db"),
            }
        }
else:
    # Default: SQLite for development and CI
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Authentication
AUTH_USER_MODEL = "accounts.CustomUser"

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/New_York"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "celery": {
            "format": "[{levelname}] {asctime} {name} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        # Celery Worker File Logging
        # ⚠️ MULTIPROCESS LOGGING CAVEAT:
        # RotatingFileHandler is thread-safe but NOT multiprocess-safe.
        # Multiple Celery worker processes writing to the same rotating file can cause:
        #   - Garbled/interleaved log output
        #   - ROTATION CORRUPTION: race conditions during rollover (the main risk)
        #   - Lost log lines when rename/rotate happens while other processes write
        #
        # SAFER PRODUCTION ALTERNATIVES:
        # 1. Log to stdout/stderr → let systemd/journald/Docker/supervisord handle it (RECOMMENDED)
        # 2. External rotation: Use non-rotating handler + logrotate (copytruncate mode)
        # 3. Per-worker files: f"celery_worker_{os.getpid()}.log" (many files to manage)
        # 4. Multiprocess-safe handler: pip install concurrent-log-handler
        # 5. QueueHandler + QueueListener: centralized writer thread in your app
        # 6. Syslog/external service: Sentry, DataDog, CloudWatch, syslog
        #
        # CURRENT SETUP: Using RotatingFileHandler with per-worker files for development/small deployments.
        # Acceptable for dev/testing/light production, but REPLACE with another option from the list above
        # for high throughput.
        #
        # OPTIMIZATION: delay=True means the log file is NOT created until the first log record is written.
        # Since we only log ERRORs (level="ERROR"), a worker that never encounters errors will never create
        # a log file. This prevents cluttering logs/ with empty files from successful workers.
        "celery_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / f"celery_worker-{os.getpid()}.log",
            "formatter": "celery",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "level": env("CELERY_LOG_LEVEL", default="ERROR"),
            "delay": True,  # Only create file when first error occurs
        },
        "celery_error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / f"celery_errors-{os.getpid()}.log",
            "formatter": "celery",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "level": "ERROR",
            "delay": True,  # Only create file when first error occurs
            # ⚠️ Same multiprocess rotation corruption risk as celery_file above
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "links": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file", "celery_error_file"],
            "level": env("CELERY_LOG_LEVEL", default="ERROR"),
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["console", "celery_file"],
            "level": env("CELERY_TASK_LOG_LEVEL", default="ERROR"),
            "propagate": False,
        },
    },
}


# Celery Configuration
# https://docs.celeryproject.io/en/stable/django/

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default="redis://localhost:6379/0" if not DEBUG else "memory://",
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default="redis://localhost:6379/1" if not DEBUG else "cache+memory://",
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# In test environment, execute tasks synchronously and eagerly
if "test" in sys.argv or env.bool("CELERY_ALWAYS_EAGER", default=False):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Task routing and scheduling
CELERY_TASK_ROUTES = {
    "core.tasks.send_welcome_email": {"queue": "email"},
    "core.tasks.send_password_reset_email": {"queue": "email"},
    "core.tasks.cleanup_expired_tokens": {"queue": "celery"},
}

CELERY_QUEUES = {
    "email": {
        "exchange": "email",
        "routing_key": "email",
    },
    "celery": {
        "exchange": "celery",
        "routing_key": "celery",
    },
}

# Celery worker configuration
CELERYD_PREFETCH_MULTIPLIER = env.int("CELERY_PREFETCH_MULTIPLIER", default=4)
CELERYD_MAX_TASKS_PER_CHILD = env.int("CELERY_MAX_TASKS_PER_CHILD", default=1000)
CELERYD_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=25 * 60)
CELERYD_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=30 * 60)

# Task retry configuration
CELERY_TASK_MAX_RETRIES = env.int("CELERY_TASK_MAX_RETRIES", default=3)
CELERY_TASK_DEFAULT_RETRY_DELAY = env.int("CELERY_TASK_DEFAULT_RETRY_DELAY", default=60)
