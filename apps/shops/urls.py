from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'shops'

router = DefaultRouter()
router.register(r'', views.ShopViewSet, basename='shop')

urlpatterns = router.urls
