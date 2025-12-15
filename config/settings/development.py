"""
Development settings
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

# Email - Uses SMTP from base.py by default
# Uncomment below to print emails to console instead of sending:
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable HTTPS redirect in development
SECURE_SSL_REDIRECT = False

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Logging - More verbose in development
# LOGGING['root']['level'] = 'DEBUG'
# LOGGING['loggers']['django']['level'] = 'DEBUG'

