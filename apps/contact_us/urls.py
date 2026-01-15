"""
URL configuration for contact us app.
"""
from django.urls import path
from .views import ContactQueryView

urlpatterns = [
    path('', ContactQueryView.as_view(), name='contact-query-create'),
]
