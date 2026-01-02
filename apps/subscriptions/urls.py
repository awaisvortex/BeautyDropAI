"""
Subscription URL patterns.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'subscriptions'

# Create router for viewsets
router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='plan')
router.register(r'', views.SubscriptionViewSet, basename='subscription')
router.register(r'payments', views.PaymentViewSet, basename='payment')

urlpatterns = router.urls
