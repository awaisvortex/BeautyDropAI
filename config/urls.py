"""
URL configuration for salon booking system.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API v1 endpoints
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/clients/', include('apps.clients.urls')),
    path('api/v1/customers/', include('apps.customers.urls')),
    path('api/v1/shops/', include('apps.shops.urls')),
    path('api/v1/widgets/', include('apps.widget.urls')),
    path('api/v1/services/', include('apps.services.urls')),
    path('api/v1/schedules/', include('apps.schedules.urls')),
    path('api/v1/staff/', include('apps.staff.urls')),
    path('api/v1/bookings/', include('apps.bookings.urls')),
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/calendars/', include('apps.calendars.urls')),
    path('api/v1/agent/', include('apps.agent.urls')),
    path('api/v1/scraper/', include('apps.scraper.urls')),
    
    # Media proxy for serving GCS images
    path('api/media/', include('apps.core.urls')),
    
    # Webhooks (no version prefix for webhooks)
    path('api/payments/', include('apps.payments.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
