"""
Schedules views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ShopSchedule
from .serializers import ShopScheduleSerializer


class ShopScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ShopSchedule
    """
    queryset = ShopSchedule.objects.all()
    serializer_class = ShopScheduleSerializer
    permission_classes = [IsAuthenticated]
