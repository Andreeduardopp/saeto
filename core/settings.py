from decouple import config
from pathlib import Path
import dj_database_url
import os


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ENV_NAME = config("ENV_NAME", default="dev")

ALLOWED_HOSTS = ["*"]

SITE_ID = 1


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework.authtoken",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "core",
    "estocasticos",
    "teoria_opcao",
    "financial_options",
    "usuario",
    "teoria_dos_jogos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "middleware.language_middleware.LanguageMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

WSGI_APPLICATION = "core.wsgi.application"

database_url = config("DATABASE_URL", default=None)
if database_url:
    DATABASES = {"default": dj_database_url.parse(database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATIC_URL = "/static/"
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

FILE_UPLOAD_MAX_MEMORY_SIZE = 10621440

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"
LOGOUT_REDIRECT_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/home/"

# Allauth configuration
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_USERNAME_REQUIRED = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": config("GOOGLE_CLIENT_ID", default=""),
            "secret": config("GOOGLE_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

# email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default="")
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
STATICFILES_STORAGE_BACKEND = "django.contrib.staticfiles.storage.StaticFilesStorage"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_BUCKET = config("USE_BUCKET", default=False, cast=bool)
if USE_BUCKET:
    INSTALLED_APPS += ['storages'] 
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')
    OCI_NAMESPACE = config('OCI_NAMESPACE')
    AWS_QUERYSTRING_AUTH = True 
    AWS_S3_ENDPOINT_URL = f'https://{OCI_NAMESPACE}.compat.objectstorage.{AWS_S3_REGION_NAME}.oraclecloud.com'
    AWS_S3_CUSTOM_DOMAIN = f'{OCI_NAMESPACE}.compat.objectstorage.{AWS_S3_REGION_NAME}.oraclecloud.com/{AWS_STORAGE_BUCKET_NAME}'

    AWS_DEFAULT_ACL = config('AWS_DEFAULT_ACL', default='public-read')
    AWS_S3_FILE_OVERWRITE = config("AWS_S3_FILE_OVERWRITE", default=False, cast=bool)

    STORAGES = {
        "default": { 
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": { 
            "BACKEND": STATICFILES_STORAGE_BACKEND,
            "OPTIONS": {
                "location": STATIC_ROOT,
            },
        },
    }


    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

else: # USE_BUCKET is False (local storage)
    MEDIA_ROOT = BASE_DIR / "media"
    STATIC_ROOT = BASE_DIR / "staticfiles"

    # Define STORAGES dictionary for local file system backends
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {
                "location": MEDIA_ROOT,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            "OPTIONS": {
                "location": STATIC_ROOT,
            },
        },
    }

    MEDIA_URL = "/media/"
    STATIC_URL = "/static/"
