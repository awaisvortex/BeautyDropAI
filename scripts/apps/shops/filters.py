"""
Shops filters
"""
import django_filters
from .models import Shop


class ShopFilter(django_filters.FilterSet):
    """
    Filter for Shop
    """
    class Meta:
        model = Shop
        fields = ['is_active']
