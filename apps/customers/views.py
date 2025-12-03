from rest_framework import viewsets
from .models import Customer


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Customer model.
    """
    queryset = Customer.objects.all()
    # Add serializer_class when you create serializers
