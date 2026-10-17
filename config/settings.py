import os
from pathlib import Path
from dotenv import load_dotenv
from celery.schedules import crontab
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
CREDENTIAL_KEY = os.environ["CREDENTIAL_KEY"]
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
INSTALLED_APPS = ["inventory.apps.ConsoleAdminConfig", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "rest_framework", "rest_framework.authtoken", "inventory.apps.InventoryConfig"]
MIDDLEWARE = ["inventory.middleware.RequestTimingMiddleware", "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "inventory.context_processors.demo_login"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3", "OPTIONS": {"timeout": 30}}}
if os.getenv("POSTGRES_HOST"):
    DATABASES["default"] = {"ENGINE": "django.db.backends.postgresql", "HOST": os.environ["POSTGRES_HOST"], "PORT": os.getenv("POSTGRES_PORT", "5432"), "NAME": os.getenv("POSTGRES_DB", "dbims"), "USER": os.getenv("POSTGRES_USER", "dbims"), "PASSWORD": os.environ["POSTGRES_PASSWORD"]}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Shanghai")
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication", "rest_framework.authentication.SessionAuthentication"], "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"], "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 25, "DEFAULT_THROTTLE_RATES": {"probe": "30/min"}}
PROBE_ALLOWED_NETWORKS = os.getenv("PROBE_ALLOWED_NETWORKS", "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,::1/128").split(",")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "filesystem://")
if CELERY_BROKER_URL == "filesystem://":
    for directory in ("queue", "processed", "control"):
        (BASE_DIR / ".runtime" / directory).mkdir(parents=True, exist_ok=True)
    CELERY_BROKER_TRANSPORT_OPTIONS = {"data_folder_in": str(BASE_DIR / ".runtime/queue"), "data_folder_out": str(BASE_DIR / ".runtime/queue"), "data_folder_processed": str(BASE_DIR / ".runtime/processed"), "control_folder": str(BASE_DIR / ".runtime/control"), "store_processed": False}
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {"rotate-every-12-hours": {"task": "inventory.tasks.rotate_passwords", "schedule": crontab(hour="0,12", minute=0)}, "daily-instance-snapshot": {"task": "inventory.tasks.snapshot_instances", "schedule": crontab(hour=0, minute=0)}}
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "loggers": {"inventory": {"handlers": ["console"], "level": "INFO", "propagate": False}}}
