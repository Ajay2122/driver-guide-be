from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework
from django_filters import CharFilter, UUIDFilter, DateFilter, BooleanFilter
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Sum, Avg, Count

from .models import Driver, DailyLog
from .serializers import (
    DriverSerializer,
    DailyLogSerializer,
    DailyLogListSerializer,
    DailyLogCreateSerializer
)
from .mixins import StandardResponseMixin
from .exceptions import DriverNotFound, LogNotFound


class DriverFilter(rest_framework.FilterSet):
    """Filter for Driver model"""
    search = CharFilter(method='filter_search')
    
    class Meta:
        model = Driver
        fields = ['name', 'license_number']
    
    def filter_search(self, queryset, name, value):
        """Search by name or license number"""
        return queryset.filter(
            Q(name__icontains=value) | Q(license_number__icontains=value)
        )


class DriverViewSet(viewsets.ModelViewSet, StandardResponseMixin):
    """
    ViewSet for Driver CRUD operations
    GET /api/v1/drivers - List all drivers
    POST /api/v1/drivers - Create a driver
    GET /api/v1/drivers/{id} - Get driver by ID
    PUT /api/v1/drivers/{id} - Update driver (full)
    PATCH /api/v1/drivers/{id} - Update driver (partial)
    DELETE /api/v1/drivers/{id} - Delete driver
    """
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DriverFilter
    search_fields = ['name', 'license_number']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def list(self, request, *args, **kwargs):
        """List all drivers with pagination and search"""
        queryset = self.filter_queryset(self.get_queryset())
        return self.list_response(queryset, DriverSerializer, "Drivers fetched successfully", items_key='drivers')
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single driver"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.success_response(
                data=serializer.data,
                message="Driver fetched successfully"
            )
        except Driver.DoesNotExist:
            raise DriverNotFound()
    
    def create(self, request, *args, **kwargs):
        """Create a new driver"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            driver = serializer.save()
            response_serializer = DriverSerializer(driver)
            return self.success_response(
                data=response_serializer.data,
                message="Driver created successfully",
                status_code=status.HTTP_201_CREATED
            )
        return self.error_response(
            message="Validation failed",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def update(self, request, *args, **kwargs):
        """Update a driver (full update)"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            if serializer.is_valid():
                driver = serializer.save()
                response_serializer = DriverSerializer(driver)
                return self.success_response(
                    data=response_serializer.data,
                    message="Driver updated successfully"
                )
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Driver.DoesNotExist:
            raise DriverNotFound()
    
    def partial_update(self, request, *args, **kwargs):
        """Update a driver (partial update)"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                driver = serializer.save()
                response_serializer = DriverSerializer(driver)
                return self.success_response(
                    data=response_serializer.data,
                    message="Driver updated successfully"
                )
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Driver.DoesNotExist:
            raise DriverNotFound()
    
    def destroy(self, request, *args, **kwargs):
        """Delete a driver"""
        try:
            instance = self.get_object()
            instance.delete()
            return self.success_response(
                data=None,
                message="Driver deleted successfully"
            )
        except Driver.DoesNotExist:
            raise DriverNotFound()


class DailyLogFilter(rest_framework.FilterSet):
    """Filter for DailyLog model"""
    driver_id = UUIDFilter(field_name='driver_id')
    start_date = DateFilter(field_name='date', lookup_expr='gte')
    end_date = DateFilter(field_name='date', lookup_expr='lte')
    compliant = BooleanFilter(field_name='is_compliant')
    
    class Meta:
        model = DailyLog
        fields = ['driver_id', 'date', 'is_compliant']


class DailyLogViewSet(viewsets.ModelViewSet, StandardResponseMixin):
    """
    ViewSet for DailyLog CRUD operations
    GET /api/v1/logs - List all logs
    POST /api/v1/logs - Create a log
    GET /api/v1/logs/{id} - Get log by ID
    PUT /api/v1/logs/{id} - Update log (full)
    PATCH /api/v1/logs/{id} - Update log (partial)
    DELETE /api/v1/logs/{id} - Delete log
    """
    queryset = DailyLog.objects.select_related('driver').all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DailyLogFilter
    ordering_fields = ['date', 'created_at']
    ordering = ['-date', '-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return DailyLogCreateSerializer
        elif self.action == 'list':
            return DailyLogListSerializer
        return DailyLogSerializer
    
    def list(self, request, *args, **kwargs):
        """List all logs with filtering"""
        queryset = self.filter_queryset(self.get_queryset())
        return self.list_response(queryset, DailyLogListSerializer, "Logs fetched successfully", items_key='logs')
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single log"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.success_response(
                data=serializer.data,
                message="Log fetched successfully"
            )
        except DailyLog.DoesNotExist:
            raise LogNotFound()
    
    def create(self, request, *args, **kwargs):
        """Create a new daily log"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            daily_log = serializer.save()
            response_serializer = DailyLogSerializer(daily_log)
            return self.success_response(
                data=response_serializer.data,
                message="Log created successfully",
                status_code=status.HTTP_201_CREATED
            )
        return self.error_response(
            message="Validation failed",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def update(self, request, *args, **kwargs):
        """Update a log (full update)"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            if serializer.is_valid():
                daily_log = serializer.save()
                response_serializer = DailyLogSerializer(daily_log)
                return self.success_response(
                    data=response_serializer.data,
                    message="Log updated successfully"
                )
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DailyLog.DoesNotExist:
            raise LogNotFound()
    
    def partial_update(self, request, *args, **kwargs):
        """Update a log (partial update)"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                daily_log = serializer.save()
                response_serializer = DailyLogSerializer(daily_log)
                return self.success_response(
                    data=response_serializer.data,
                    message="Log updated successfully"
                )
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except DailyLog.DoesNotExist:
            raise LogNotFound()
    
    def destroy(self, request, *args, **kwargs):
        """Delete a log"""
        try:
            instance = self.get_object()
            instance.delete()
            return self.success_response(
                data=None,
                message="Log deleted successfully"
            )
        except DailyLog.DoesNotExist:
            raise LogNotFound()
    
