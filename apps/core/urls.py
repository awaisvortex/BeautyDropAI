"""
URL configuration for core app media proxy.
"""
from django.urls import path
from apps.core.views import ShopCoverImageProxyView

urlpatterns = [
    path('shops/covers/<str:filename>', ShopCoverImageProxyView.as_view(), name='shop_cover_proxy'),
]
