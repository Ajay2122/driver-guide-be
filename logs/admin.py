from django.contrib import admin
from .models import Driver, DailyLog, LocationCache


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['name', 'license_number', 'home_terminal', 'created_at']
    search_fields = ['name', 'license_number']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ['driver', 'date', 'hours_driving', 'hours_total', 'is_compliant', 'created_at']
    list_filter = ['date', 'is_compliant', 'created_at']
    search_fields = ['driver__name', 'driver__license_number']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'


@admin.register(LocationCache)
class LocationCacheAdmin(admin.ModelAdmin):
    list_display = ['location_name', 'latitude', 'longitude', 'created_at']
    search_fields = ['location_name', 'formatted_address']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
