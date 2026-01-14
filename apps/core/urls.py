"""
URL configuration for core app media proxy.
"""
from django.urls import path
from apps.core.views import (
    ShopCoverImageProxyView,
    WidgetBannerImageProxyView,
    WidgetLogoImageProxyView
)

urlpatterns = [
    path('shops/covers/<str:filename>', ShopCoverImageProxyView.as_view(), name='shop_cover_proxy'),
    path('widgets/banners/<str:filename>', WidgetBannerImageProxyView.as_view(), name='widget_banner_proxy'),
    path('widgets/logos/<str:filename>', WidgetLogoImageProxyView.as_view(), name='widget_logo_proxy'),
]
