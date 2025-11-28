from rest_framework import viewsets
from .models import Notification


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notification model.
    """
    queryset = Notification.objects.all()
    # Add serializer_class when you create serializers
