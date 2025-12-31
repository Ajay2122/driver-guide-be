"""
View for getting driver-specific logs
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.dateparse import parse_date

from ..models import Driver, DailyLog
from ..mixins import StandardResponseMixin
from ..exceptions import DriverNotFound
from ..serializers import DailyLogListSerializer


@api_view(['GET'])
def get_driver_logs(request, driver_id):
    """
    Get logs for a specific driver
    GET /api/v1/drivers/{driver_id}/logs
    """
    try:
        driver = Driver.objects.get(pk=driver_id)
    except Driver.DoesNotExist:
        raise DriverNotFound()
    
    logs = DailyLog.objects.filter(driver=driver)
    
    # Apply filters
    start_date = request.query_params.get('startDate')
    end_date = request.query_params.get('endDate')
    
    if start_date:
        start_date = parse_date(start_date)
        if start_date:
            logs = logs.filter(date__gte=start_date)
    if end_date:
        end_date = parse_date(end_date)
        if end_date:
            logs = logs.filter(date__lte=end_date)
    
    logs = logs.order_by('-date').select_related('driver')
    
    # Paginate
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(logs, request)
    
    if page is not None:
            serializer = DailyLogListSerializer(page, many=True)
            paginated_response = paginator.get_paginated_response(serializer.data)
            return Response({
                'status': 'success',
                'data': {
                    'logs': serializer.data,
                    'pagination': {
                        'currentPage': int(request.query_params.get('page', 1)),
                        'totalPages': paginator.page.paginator.num_pages if paginator.page else 1,
                        'totalItems': paginator.page.paginator.count if paginator.page else len(serializer.data),
                        'itemsPerPage': paginator.page_size
                    }
                },
                'message': 'Driver logs fetched successfully'
            }, status=status.HTTP_200_OK)
    
    serializer = DailyLogListSerializer(logs, many=True)
    return Response({
        'status': 'success',
        'data': {
            'logs': serializer.data,
            'pagination': {
                'currentPage': 1,
                'totalPages': 1,
                'totalItems': len(serializer.data),
                'itemsPerPage': len(serializer.data)
            }
        },
        'message': 'Driver logs fetched successfully'
    }, status=status.HTTP_200_OK)


