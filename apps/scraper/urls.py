"""
URL routing for Scraper API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScraperViewSet

router = DefaultRouter()
router.register(r'', ScraperViewSet, basename='scraper')

urlpatterns = [
    path('', include(router.urls)),
]
