from rest_framework import viewsets
from .models import Client


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Client model.
    """
    queryset = Client.objects.all()
    # Add serializer_class when you create serializers
