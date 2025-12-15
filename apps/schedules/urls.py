from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'schedules'

router = DefaultRouter()
router.register(r'shop-schedules', views.ShopScheduleViewSet, basename='shop-schedule')
router.register(r'time-slots', views.TimeSlotViewSet, basename='time-slot')
router.register(r'holidays', views.HolidayViewSet, basename='holiday')

urlpatterns = router.urls
