from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'widget'

router = DefaultRouter()
router.register(r'', views.WidgetConfigurationViewSet, basename='widget')

urlpatterns = router.urls
