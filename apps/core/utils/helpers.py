"""
Helper utilities
"""
from typing import Dict, Any
import random
import string


def generate_random_string(length: int = 10) -> str:
    """
    Generate a random string of specified length
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def format_error_response(message: str, errors: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Format error response
    """
    response = {
        'error': True,
        'message': message,
    }
    if errors:
        response['errors'] = errors
    return response


def format_success_response(message: str, data: Any = None) -> Dict[str, Any]:
    """
    Format success response
    """
    response = {
        'success': True,
        'message': message,
    }
    if data is not None:
        response['data'] = data
    return response
