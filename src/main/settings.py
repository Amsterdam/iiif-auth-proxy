"""
Django settings for iiif_auth_proxy project.

Generated by 'django-admin startproject' using Django 2.1.8.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
from distutils.util import strtobool

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

ALLOWED_HOSTS = ['*']
CORS_ORIGIN_ALLOW_ALL = True

STADSARCHIEF_META_SERVER_BASE_URL = os.getenv('STADSARCHIEF_META_SERVER_BASE_URL', "http://iiif-metadata-server-api.service.consul")
STADSARCHIEF_META_SERVER_PORT = os.getenv('STADSARCHIEF_META_SERVER_PORT', "8183")  # This port is static within the network
ACCESS_PUBLIC = 'PUBLIC'
ACCESS_RESTRICTED = 'RESTRICTED'
COPYRIGHT_YES = "J"
COPYRIGHT_NO = "N"
BOUWDOSSIER_PUBLIC_SCOPE = 'BD/P'  # BouwDossiers_Public_Read. Access to anybody with e-mail link
BOUWDOSSIER_READ_SCOPE = 'BD/R'  # BouwDossiers_Read. Access to civil servants of Amsterdam Municipality
BOUWDOSSIER_EXTENDED_SCOPE = 'BD/X'  # BouwDossiers_eXtended. Access civil servants of Amsterdam Municipality with special rights.
IIIF_BASE_URL = os.getenv('IIIF_BASE_URL', 'http://iiif.service.consul')
IIIF_PORT = os.getenv('IIIF_PORT', "8149")  # This port is static within the network
EDEPOT_BASE_URL = os.getenv('EDEPOT_BASE_URL', 'https://bwt.uitplaatsing.shcp03.archivingondemand.nl/rest/')
WABO_BASE_URL = os.getenv('WABO_BASE_URL', 'https://conversiestraatwabo.amsterdam.nl/webDAV/')
HCP_AUTHORIZATION=os.getenv('HCP_AUTHORIZATION')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = 'HS256'
SENDGRID_KEY = os.getenv('SENDGRID_KEY', 'mock_key')
ZIP_COLLECTION_NAME = 'zip_queue'
LOGIN_ORIGIN_URL_TLD_WHITELIST = ['data.amsterdam.nl', 'acc.data.amsterdam.nl']
if strtobool(os.getenv('ALLOW_LOCALHOST_LOGIN_URL', 'false')):
    LOGIN_ORIGIN_URL_TLD_WHITELIST += ['localhost', '127.0.0.1']


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

USE_JWKS_TEST_KEY = os.getenv('USE_JWKS_TEST_KEY', 'false').lower() == 'true'
PUB_JWKS = JWKS_TEST_KEY if USE_JWKS_TEST_KEY else os.getenv('PUB_JWKS')

DATAPUNT_AUTHZ = {
    # 'ALWAYS_OK': True if DEBUG else False,  # disable authz. tests will fail...
    'ALWAYS_OK': False,
    'JWKS': PUB_JWKS,
    "JWKS_URL": os.getenv("KEYCLOAK_JWKS_URL"),
    'FORCED_ANONYMOUS_ROUTES': ['/status/health']
}

OBJECT_STORE = {
    'auth_version': '2.0',
    'authurl': os.getenv('OS_AUTH_URL'),
    'user': os.getenv('OS_USERNAME', 'iiif'),
    'key': os.getenv('OS_PASSWORD', 'insecure'),
    'tenant_name': os.getenv('OS_TENANT_NAME', 'insecure'),
    'os_options': {
        'tenant_id': os.getenv('OS_TENANT_ID'),
        'region_name': 'NL',
    }
}
OS_CONTAINER_NAME = os.getenv('OS_CONTAINER_NAME', 'downloads_acceptance')
OS_TEMP_URL_KEY = os.getenv('OS_TEMP_URL_KEY', 'insecure')
OS_TLD = os.getenv('OS_TLD', 'objectstore.eu')
TEMP_URL_EXPIRY_DAYS = 7
OS_LARGE_FILE_SIZE = 5368709120  # 5GB
OS_LARGE_FILE_OPTIONS = {'object_dd_threads': 20, 'segment_size': 262144000, 'use_slo': True}

INGRESS_CONSUMER_CLASSES = [
    'iiif.ingress_zip_consumer.ZipConsumer',  # worker to zip files, upload to object store and email user
]
INGRESS_DISABLE_ALL_AUTH_PERMISSION_CHECKS = True  # No endpoint is used, so no checks are needed

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'iiif',
    'health',
    'corsheaders',
    'ingress',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'authorization_django.authorization_middleware',
]

ROOT_URLCONF = 'main.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'main.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.getenv("DATABASE_NAME", "iiif_auth_proxy"),
        "USER": os.getenv("DATABASE_USER", "dev"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", "dev"),
        "HOST": os.getenv("DATABASE_HOST", "database"),
        "CONN_MAX_AGE": 20,
        "PORT": os.getenv("DATABASE_PORT", "5432"),
    },
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'

SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        ignore_errors=['ExpiredSignatureError'],
    )
