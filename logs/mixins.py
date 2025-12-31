"""
Response mixins for consistent API response format
"""
from rest_framework.response import Response


class StandardResponseMixin:
    """
    Mixin to provide consistent API response format:
    {
        "status": "success|error",
        "data": {...},
        "message": "..."
    }
    """
    
    def success_response(self, data=None, message="Operation successful", status_code=200):
        """Return a success response"""
        return Response({
            'status': 'success',
            'data': data,
            'message': message
        }, status=status_code)
    
    def error_response(self, message="Operation failed", errors=None, status_code=400):
        """Return an error response"""
        response_data = {
            'status': 'error',
            'message': message
        }
        if errors:
            response_data['errors'] = errors
        return Response(response_data, status=status_code)
    
    def list_response(self, queryset, serializer_class, message="Data fetched successfully", items_key='items'):
        """Return a paginated list response"""
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_class(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            
            # Get pagination info from paginated_response
            paginator = self.paginator
            page_number = int(self.request.query_params.get(paginator.page_query_param, 1))
            total_pages = paginator.page.paginator.num_pages if paginator.page else 1
            total_count = paginator.page.paginator.count if paginator.page else len(serializer.data)
            page_size = paginator.page_size if hasattr(paginator, 'page_size') else (self.pagination_class.page_size if hasattr(self, 'pagination_class') else len(serializer.data))
            
            # Transform paginated response to match our format
            data_dict = {
                items_key: serializer.data,
                'pagination': {
                    'currentPage': page_number,
                    'totalPages': total_pages,
                    'totalItems': total_count,
                    'itemsPerPage': page_size
                }
            }
            
            return Response({
                'status': 'success',
                'data': data_dict,
                'message': message
            })
        
        serializer = serializer_class(queryset, many=True)
        data_dict = {
            items_key: serializer.data,
            'pagination': {
                'currentPage': 1,
                'totalPages': 1,
                'totalItems': len(serializer.data),
                'itemsPerPage': len(serializer.data)
            }
        }
        return Response({
            'status': 'success',
            'data': data_dict,
            'message': message
        })

