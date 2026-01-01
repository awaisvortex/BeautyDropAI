from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'services'

router = DefaultRouter()
router.register(r'services', views.ServiceViewSet, basename='service')
router.register(r'deals', views.DealViewSet, basename='deal')

urlpatterns = router.urls

