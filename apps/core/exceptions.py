"""
Custom exceptions and exception handler
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class InvalidOperation(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid operation.'
    default_code = 'invalid_operation'


class ResourceConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Resource conflict.'
    default_code = 'resource_conflict'


def custom_exception_handler(exc, context):
    """
    Custom exception handler that adds additional context
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'error': True,
            'message': response.data.get('detail', str(exc)),
            'status_code': response.status_code,
        }
        
        # Add field errors if present
        if isinstance(response.data, dict) and 'detail' not in response.data:
            custom_response_data['errors'] = response.data
        
        response.data = custom_response_data

    return response
