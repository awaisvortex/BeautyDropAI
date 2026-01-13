"""
Django base settings for Beauty Drop AI.
"""
import os
import ssl
from pathlib import Path
from datetime import timedelta
import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
    'channels',
    
    # Local apps
    'apps.core',
    'apps.authentication',
    'apps.payments',
    'apps.clients',
    'apps.customers',
    'apps.shops',
    'apps.services',
    'apps.schedules',
    'apps.staff',
    'apps.bookings',
    'apps.subscriptions',
    'apps.notifications',
    'apps.calendars',
    'apps.agent',
    'apps.voice',
    'apps.scraper',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.authentication.middleware.ClerkAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
    }
}

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.authentication.auth_backends.ClerkJWTAuthentication',  # Clerk Bearer token
        'apps.authentication.auth_backends.ClerkUserIdAuthentication',  # Swagger dev auth
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'apps.core.schema.CustomAutoSchema',
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# DRF Spectacular (API Documentation)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Beauty Drop AI API',
    'DESCRIPTION': 'AI-powered beauty salon booking marketplace with smart scheduling, payments, and service management. Authentication via Clerk.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Authentication', 'description': 'User endpoints (Clerk-authenticated)'},
        {'name': 'System', 'description': 'System health and status'},
        {'name': 'Shops - Public', 'description': 'Public shop discovery and search'},
        {'name': 'Shops - Client', 'description': 'Salon owner shop management'},
        {'name': 'Services - Public', 'description': 'Public service browsing'},
        {'name': 'Services - Client', 'description': 'Salon owner service management'},
        {'name': 'Staff - Public', 'description': 'Public staff member browsing'},
        {'name': 'Staff - Client', 'description': 'Salon owner staff management'},
        {'name': 'Staff Dashboard', 'description': 'Staff member self-service dashboard'},
        {'name': 'Schedules - Client', 'description': 'Salon owner schedule management'},
        {'name': 'Schedules - Public', 'description': 'Public availability checking'},
        {'name': 'Bookings - Customer', 'description': 'Customer booking management'},
        {'name': 'Bookings - Client', 'description': 'Salon owner booking management'},
        {'name': 'Subscriptions - Public', 'description': 'Public subscription plan browsing'},
        {'name': 'Subscriptions - Client', 'description': 'Client subscription management'},
        {'name': 'Subscriptions - Admin', 'description': 'Admin subscription plan management'},
        {'name': 'Calendars', 'description': 'Google Calendar integration for booking sync'},
        {'name': 'AI Agent', 'description': 'AI-powered chat assistant for booking and shop management'},
        {'name': 'Scraper', 'description': 'Website scraping for shop creation from URLs'},
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'Production: Clerk JWT token from Authorization header'
            },
            'ClerkUserAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-Clerk-User-ID',
                'description': 'Development/Testing: Enter your clerk_user_id (e.g., user_2abc123...)'
            }
        }
    },
    'SECURITY': [
        {'BearerAuth': []},
        {'ClerkUserAuth': []}
    ],
    'ENUM_NAME_OVERRIDES': {
        'StatusB86Enum': 'BookingStatusEnum',
        'Status728Enum': 'SubscriptionStatusEnum',
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# Clerk Configuration
CLERK_SECRET_KEY = env('CLERK_SECRET_KEY')
CLERK_PUBLISHABLE_KEY = env('CLERK_PUBLISHABLE_KEY')
CLERK_API_URL = env('CLERK_API_URL', default='https://api.clerk.com/v1')
CLERK_WEBHOOK_SECRET = env('CLERK_WEBHOOK_SECRET', default='')

# Stripe Configuration
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')

# Stripe Connect (for marketplace payments to shop owners)
STRIPE_CONNECT_CLIENT_ID = env('STRIPE_CONNECT_CLIENT_ID', default='')
STRIPE_CONNECT_WEBHOOK_SECRET = env('STRIPE_CONNECT_WEBHOOK_SECRET', default='')

# Frontend URLs for subscription redirects
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')

# Google Calendar Configuration (OAuth 2.0)
GOOGLE_CALENDAR_CLIENT_ID = env('GOOGLE_CALENDAR_CLIENT_ID', default='')
GOOGLE_CALENDAR_CLIENT_SECRET = env('GOOGLE_CALENDAR_CLIENT_SECRET', default='')

# Firebase Configuration (for Cloud Messaging push notifications)
# Path to Firebase service account JSON file
FIREBASE_CREDENTIALS_PATH = env('FIREBASE_CREDENTIALS_PATH', default='')

# OpenAI Configuration (for AI Agent)
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')
OPENAI_MODEL = env('OPENAI_MODEL', default='gpt-4-turbo-preview')

# Firecrawl Configuration (for AI Scraper)
FIRECRAWL_API_KEY = env('FIRECRAWL_API_KEY', default=None)

# Pinecone Configuration (for AI Agent knowledge base)
PINECONE_API_KEY = env('PINECONE_API_KEY', default='')
PINECONE_INDEX_NAME = env('PINECONE_INDEX_NAME', default='beautydrop-knowledge')

# Google Cloud Storage Configuration (for image uploads)
GCS_BUCKET_NAME = env('GCS_BUCKET_NAME', default='')
GCS_PROJECT_ID = env('GCS_PROJECT_ID', default='')
GCS_CREDENTIALS_PATH = env('GCS_CREDENTIALS_PATH', default='')

# Backend URL (for generating proxy URLs)
BACKEND_URL = env('BACKEND_URL', default='http://localhost:8004')



# Redis Configuration
REDIS_URL = env('REDIS_URL')

# Parse Redis URL to check if SSL is needed
from urllib.parse import urlparse as _urlparse_cache
_redis_parsed_cache = _urlparse_cache(REDIS_URL)
_redis_use_ssl = _redis_parsed_cache.scheme == 'rediss'

if _redis_use_ssl:
    # SSL connection for Cloud Redis (Upstash, Cloud Memorystore, etc.)
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'ssl_cert_reqs': ssl.CERT_NONE
                }
            }
        }
    }
else:
    # Non-SSL connection (local development)
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }

# Channel Layers (for WebSocket support)
# Parse Redis URL to handle SSL properly for Cloud Memorystore
import ssl
from urllib.parse import urlparse

_redis_parsed = urlparse(REDIS_URL)
_redis_host = _redis_parsed.hostname or 'localhost'
_redis_port = _redis_parsed.port or 6379
_redis_password = _redis_parsed.password
_redis_ssl = _redis_parsed.scheme == 'rediss'

if _redis_ssl:
    # SSL connection for Cloud Memorystore
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [{
                    'address': f'rediss://{_redis_host}:{_redis_port}',
                    'password': _redis_password,
                    'ssl_cert_reqs': None,  # Skip cert verification for Cloud Memorystore
                }],
            },
        },
    }
else:
    # Non-SSL connection (local development)
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [REDIS_URL],
            },
        },
    }

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Celery Configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery SSL configuration for rediss:// URLs (e.g., Upstash, Cloud Memorystore)
if _redis_ssl:
    CELERY_BROKER_USE_SSL = {
        'ssl_cert_reqs': ssl.CERT_NONE,  # Skip cert verification for managed Redis
    }
    CELERY_REDIS_BACKEND_USE_SSL = {
        'ssl_cert_reqs': ssl.CERT_NONE,
    }


# Email Configuration - Mailgun SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.mailgun.org')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='BeautyDrop <noreply@beautydrop.ai>')

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
