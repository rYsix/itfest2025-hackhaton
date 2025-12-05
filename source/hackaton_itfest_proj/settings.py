import os
from pathlib import Path
from decouple import Config, RepositoryEnv, Csv
from django.core.files.storage import FileSystemStorage
from logging.handlers import RotatingFileHandler  # noqa: F401

# =============================================================================
# PATHS
# =============================================================================
SOURCE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SOURCE_DIR.parent


ENV_FILE = PROJECT_DIR / ".env"

if not ENV_FILE.exists():
    raise FileNotFoundError(f".env not found at {ENV_FILE}")

config = Config(RepositoryEnv(ENV_FILE))

RUNTIME_DIR = PROJECT_DIR / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
STATIC_ROOT = RUNTIME_DIR / "staticfiles"
MEDIA_ROOT = RUNTIME_DIR / "media"
PRIVATE_MEDIA_ROOT = RUNTIME_DIR / "private"

FILE_UPLOAD_PERMISSIONS = 0o660
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o770

# =============================================================================
# CORE SETTINGS
# =============================================================================

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv())

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# =============================================================================
# APPS
# =============================================================================
INSTALLED_APPS = [
    "htmlmin",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'apps.common',
    "apps.translation",
    "apps.support", 
    
    # local apps
    # "common",
]

# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "apps.common.middleware.SetRealIPMiddleware",
    "htmlmin.middleware.HtmlMinifyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.TimezoneMiddleware",
    "apps.translation.middleware.CustomLocaleMiddleware",
]

ROOT_URLCONF = "hackaton_itfest_proj.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SOURCE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.translation.context_processors.current_language"
            ],
        },
    },
]

WSGI_APPLICATION = "hackaton_itfest_proj.wsgi.application"

# =============================================================================
# DATABASES
# =============================================================================
DATABASE_MODE = config("DATABASE_MODE", default="sqlite")

if DATABASE_MODE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": RUNTIME_DIR / "db.sqlite3",
        }
    }
elif DATABASE_MODE == "psql":
    ssl_enabled = config("DATABASE_SSL_ENABLED", default="true").lower() == "true"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DATABASE_NAME"),
            "USER": config("DATABASE_USER"),
            "PASSWORD": config("DATABASE_PASSWORD"),
            "HOST": config("DATABASE_HOST", default="localhost"),
            "PORT": config("DATABASE_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"sslmode": "require" if ssl_enabled else "disable"},
        }
    }
else:
    raise ValueError("Invalid DATABASE_MODE: must be 'sqlite' or 'psql'")

# ============================================================================
# LOGGING
# ============================================================================

from .logging import LOGGING  # noqa: E402

# =============================================================================
# CACHE
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "hackaton_itfest_proj_cache",
        "OPTIONS": {"MAX_ENTRIES": 10_000, "CULL_FREQUENCY": 10},
    },
}

# =============================================================================
# USER MODEL
# =============================================================================

AUTH_USER_MODEL = "common.customuser"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"


# =============================================================================
# I18N / TIMEZONE
# =============================================================================
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC / MEDIA
# =============================================================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [SOURCE_DIR / "static"]

MEDIA_URL = "/media/"
PRIVATE_FILE_STORAGE = FileSystemStorage(
    location=PRIVATE_MEDIA_ROOT,
    base_url="/private/"
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# OPENAI
# =============================================================================
OPENAI_KEY = config("OPENAI_API_KEY")

# =============================================================================
# EMAIL
# =============================================================================
EMAIL_MODE = config("EMAIL_MODE", default="console")

if EMAIL_MODE == "console":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
elif EMAIL_MODE == "smtp":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = config("EMAIL_HOST")
    EMAIL_PORT = config("EMAIL_PORT", cast=int)
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool)
    EMAIL_USE_SSL = config("EMAIL_USE_SSL", cast=bool)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
else:
    raise ValueError("Invalid EMAIL_MODE: must be 'console' or 'smtp'")

# =============================================================================
# HTML MINIFY / ADMIN STYLE
# =============================================================================
HTML_MINIFY = True
KEEP_COMMENTS_ON_MINIFYING = False

JAZZMIN_SETTINGS = {
    "site_title": "hackaton_itfest_proj",
    "site_header": "hackaton_itfest_proj",
    "site_brand": "hackaton_itfest_proj",
    "welcome_sign": "Welcome to hackaton_itfest_proj Admin",
    "copyright": "hackaton_itfest_proj © 2025",
    "changeform_format": "single",
    "use_google_fonts_cdn": False,
    "default_color": "dark-mode",
    "navigation_expanded": True,
    "show_sidebar": True,
    "sidebar_fixed": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "admin.LogEntry": "fas fa-list-alt",
    },
    "topmenu_links": [
        {"name": "Вернуться на сайт", "url": "/", "new_window": False},
        {"name": "Users", "model": "auth.user"},
    ],
    "usermenu_links": [],
    "show_ui_builder": False,
    "show_recent": False,
    "show_themes": False,
}

# =============================================================================
# DEBUG PRINT (DEV ONLY)
# =============================================================================
if os.environ.get("RUN_MAIN") == "true":
    print("\n================= hackaton_itfest_proj Settings =================")
    print(f"DEBUG                 = {DEBUG}")
    print(f"SOURCE_DIR            = {SOURCE_DIR}")
    print(f"PROJECT_DIR           = {PROJECT_DIR}")
    print(f"RUNTIME_DIR           = {RUNTIME_DIR}")
    print(f"LOG_DIR               = {LOG_DIR}")
    print(f"STATIC_ROOT           = {STATIC_ROOT}")
    print(f"MEDIA_ROOT            = {MEDIA_ROOT}")
    print(f"PRIVATE_MEDIA_ROOT    = {PRIVATE_MEDIA_ROOT}")
    print(f"DATABASE_MODE         = {DATABASE_MODE}")
    print(f"EMAIL_MODE            = {EMAIL_MODE}")
    print(f"LANGUAGE_CODE         = {LANGUAGE_CODE}")
    print(f"TIME_ZONE             = {TIME_ZONE}")
    print(f"ALLOWED_HOSTS         = {ALLOWED_HOSTS}")
    print(f"CSRF_TRUSTED_ORIGINS  = {CSRF_TRUSTED_ORIGINS}")
    print("===========================================================\n")
