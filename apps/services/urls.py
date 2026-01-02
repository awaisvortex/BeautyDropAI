from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'services'

router = DefaultRouter()
# Register deals FIRST so /deals/ doesn't get matched by the empty-prefix service viewset
router.register(r'deals', views.DealViewSet, basename='deal')
router.register(r'', views.ServiceViewSet, basename='service')

urlpatterns = router.urls

