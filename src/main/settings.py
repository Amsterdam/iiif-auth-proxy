"""
Django settings for iiif_auth_proxy project.

Generated by 'django-admin startproject' using Django 2.1.8.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import json
import os
import sys
from distutils.util import strtobool

from corsheaders.defaults import default_headers
from opencensus.trace import config_integration

from .azure_settings import Azure

azure = Azure()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://bouwdossiers.amsterdam.nl/")
ALLOWED_HOSTS = ["*"]

if CORS_DOMAINS := os.getenv("CORS_DOMAINS", ""):
    CORS_ALLOWED_ORIGINS = CORS_DOMAINS.split(",")
    CORS_ALLOW_METHODS = (
        "GET",
        "POST",
    )
    CORS_ALLOW_HEADERS = [
        *default_headers,
    ]

METADATA_SERVER_BASE_URL = os.getenv(
    "METADATA_SERVER_BASE_URL",
    "http://app-iiif-metadata-server",
)
ACCESS_PUBLIC = "PUBLIC"
ACCESS_RESTRICTED = "RESTRICTED"
COPYRIGHT_YES = "J"
COPYRIGHT_NO = "N"
BOUWDOSSIER_PUBLIC_SCOPE = (
    "BD/P"  # BouwDossiers_Public_Read. Access to anybody with e-mail link
)
BOUWDOSSIER_READ_SCOPE = (
    "BD/R"  # BouwDossiers_Read. Access to civil servants of Amsterdam Municipality
)
BOUWDOSSIER_EXTENDED_SCOPE = "BD/X"  # BouwDossiers_eXtended. Access civil servants of Amsterdam Municipality with special rights.
# IIIF_BASE_URL = os.getenv("IIIF_BASE_URL", "http://iiif.service.consul")
# IIIF_PORT = os.getenv("IIIF_PORT", "8149")  # This port is static within the network
EDEPOT_BASE_URL = os.getenv(
    "EDEPOT_BASE_URL", "https://bwt.uitplaatsing.shcp03.archivingondemand.nl/rest/"
)
WABO_BASE_URL = os.getenv(
    "WABO_BASE_URL", "https://bwt.hs3-saa-bwt.shcp04.archivingondemand.nl/rest/"
)
EDEPOT_AUTHORIZATION = os.getenv("EDEPOT_AUTHORIZATION", "dummy")
WABO_AUTHORIZATION = os.getenv("WABO_AUTHORIZATION", "dummy")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
AZURITE_STORAGE_CONNECTION_STRING = os.getenv("AZURITE_STORAGE_CONNECTION_STRING")
AZURITE_QUEUE_CONNECTION_STRING = os.getenv("AZURITE_QUEUE_CONNECTION_STRING")
STORAGE_ACCOUNT_URL = os.getenv("STORAGE_ACCOUNT_URL")
QUEUE_ACCOUNT_URL = os.getenv("QUEUE_ACCOUNT_URL")
ZIP_QUEUE_NAME = "zip-queue"
LOGIN_ORIGIN_URL_TLD_WHITELIST = ["data.amsterdam.nl", "acc.dataportaal.amsterdam.nl"]
if strtobool(os.getenv("ALLOW_LOCALHOST_LOGIN_URL", "false")):
    LOGIN_ORIGIN_URL_TLD_WHITELIST += ["localhost", "127.0.0.1"]

# SMTP email settings using Secure Mail Relay
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = os.getenv("EMAIL_PORT", "587")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_FROM_EMAIL_ADDRESS = os.getenv(
    "EMAIL_FROM_EMAIL_ADDRESS", "bouwdossiers@amsterdam.nl"
)
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = 5

# Development
MOCK_GET_IMAGE_FROM_SERVER = (
    os.getenv("MOCK_GET_IMAGE_FROM_SERVER", "false").lower() == "true"
)

# The following JWKS data was obtained in the authz project :  jwkgen -create -alg ES256
# This is a test public/private key def and added for testing .
JWKS_TEST_KEY = """
    {
        "keys": [
            {
                "kty": "EC",
                "key_ops": [
                    "verify",
                    "sign"
                ],
                "kid": "2aedafba-8170-4064-b704-ce92b7c89cc6",
                "crv": "P-256",
                "x": "6r8PYwqfZbq_QzoMA4tzJJsYUIIXdeyPA27qTgEJCDw=",
                "y": "Cf2clfAfFuuCB06NMfIat9ultkMyrMQO9Hd2H7O9ZVE=",
                "d": "N1vu0UQUp0vLfaNeM0EDbl4quvvL6m_ltjoAXXzkI3U="
            }
        ]
    }
"""

USE_JWKS_TEST_KEY = os.getenv("USE_JWKS_TEST_KEY", "false").lower() == "true"
PUB_JWKS = JWKS_TEST_KEY if USE_JWKS_TEST_KEY else os.getenv("PUB_JWKS")

DATAPUNT_AUTHZ = {
    "ALWAYS_OK": True if DEBUG else False,  # disable authz. tests will fail...
    # "ALWAYS_OK": False,
    "JWKS": PUB_JWKS,
    "JWKS_URL": os.getenv("KEYCLOAK_JWKS_URL"),
    "FORCED_ANONYMOUS_ROUTES": ["/status/health"],
}

STORAGE_ACCOUNT_CONTAINER_ZIP_QUEUE_JOBS_NAME = "zip-queue-jobs"

STORAGE_ACCOUNT_CONTAINER_NAME = "downloads"
TEMP_URL_EXPIRY_DAYS = 7
if TEMP_URL_EXPIRY_DAYS > 7:
    raise ValueError("TEMP_URL_EXPIRY_DAYS must be 7 days or less")

# Application definition
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "corsheaders",
]
LOCAL_APPS = [
    "iiif",
    "health",
    "zip_consumer",
    "auth_mail",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "authorization_django.authorization_middleware",
]

ROOT_URLCONF = "main.urls"

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

WSGI_APPLICATION = "main.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases


DATABASE_HOST = os.getenv("DATABASE_HOST", "database")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "dev")
DATABASE_OPTIONS = {"sslmode": "allow", "connect_timeout": 5}
if "azure.com" in DATABASE_HOST:
    DATABASE_PASSWORD = azure.auth.db_password
    DATABASE_OPTIONS["sslmode"] = "require"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.getenv("DATABASE_NAME", "dev"),
        "USER": os.getenv("DATABASE_USER", "dev"),
        "PASSWORD": DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "CONN_MAX_AGE": 20,
        "PORT": os.getenv("DATABASE_PORT", "5432"),
        "OPTIONS": DATABASE_OPTIONS,
    },
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_IMAGE = os.path.join(STATIC_URL, "example.jpg")


# Django Logging settings
base_log_fmt = {"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s"}
log_fmt = base_log_fmt.copy()
log_fmt["message"] = "%(message)s"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "formatters": {
        "json": {"format": json.dumps(log_fmt)},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "iiif": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "main": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": os.getenv(
                "DJANGO_LOG_LEVEL", "ERROR" if "pytest" in sys.argv[0] else "INFO"
            ).upper(),
            "propagate": False,
        },
        # Log all unhandled exceptions
        "django.request": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        "opencensus": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "azure.core.pipeline.policies.http_logging_policy": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv(
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
)

if APPLICATIONINSIGHTS_CONNECTION_STRING:
    MIDDLEWARE.append("opencensus.ext.django.middleware.OpencensusMiddleware")
    OPENCENSUS = {
        "TRACE": {
            "SAMPLER": "opencensus.trace.samplers.ProbabilitySampler(rate=1)",
            "EXPORTER": f"""opencensus.ext.azure.trace_exporter.AzureExporter(
                connection_string='{APPLICATIONINSIGHTS_CONNECTION_STRING}', 
                service_name='app-iiif-auth-proxy'
            )""",
        }
    }
    config_integration.trace_integrations(["logging"])
    LOGGING["handlers"]["azure"] = {
        "level": "DEBUG",
        "class": "opencensus.ext.azure.log_exporter.AzureLogHandler",
        "connection_string": APPLICATIONINSIGHTS_CONNECTION_STRING,
        "formatter": "json",
    }
    LOGGING["root"]["handlers"].append("azure")
    for logger_name, logger_details in LOGGING["loggers"].items():
        LOGGING["loggers"][logger_name]["handlers"].append("azure")
