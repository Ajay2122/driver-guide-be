"""
Custom exceptions and exception handler for the Driver Log System API
"""
from rest_framework.exceptions import APIException, ValidationError
from rest_framework import status
from rest_framework.response import Response


class DriverNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Driver not found'
    default_code = 'driver_not_found'


class LogNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Daily log not found'
    default_code = 'log_not_found'


class DuplicateLogError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'A log for this driver on this date already exists'
    default_code = 'duplicate_log'


def custom_exception_handler(exc, context):
    """
    Custom exception handler to provide consistent error response format
    """
    from rest_framework.views import exception_handler
    
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Customize the response format
    if response is not None:
        custom_response_data = {
            'status': 'error',
            'message': str(exc.detail) if hasattr(exc, 'detail') else str(exc),
        }
        
        # Add errors field for validation errors
        if isinstance(exc, ValidationError):
            if isinstance(exc.detail, dict):
                custom_response_data['errors'] = exc.detail
            else:
                custom_response_data['errors'] = {'non_field_errors': exc.detail}
        
        # Add code if available
        if hasattr(exc, 'default_code'):
            custom_response_data['code'] = exc.default_code
        
        response.data = custom_response_data
        response.status_code = exc.status_code if hasattr(exc, 'status_code') else response.status_code
    
    return response

