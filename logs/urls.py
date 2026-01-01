from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewset import DriverViewSet, DailyLogViewSet
from .views.stats import get_driver_stats, compliance_check, dashboard_stats
from .views.driver_logs import get_driver_logs
from .views.gps import (
    geocode_location_view,
    reverse_geocode_view,
    batch_geocode_view,
    calculate_distance_view,
    calculate_route_distance_view,
    get_log_route_view
)
class OptionalSlashRouter(DefaultRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = '/?'  # Makes trailing slash optional

router = OptionalSlashRouter()
# router = DefaultRouter()
router.register(r'drivers', DriverViewSet, basename='drivers')
router.register(r'logs', DailyLogViewSet, basename='dailylog')

urlpatterns = [
    path('', include(router.urls)),
    path('drivers/<uuid:driver_id>/stats/', get_driver_stats, name='driver-stats'),
    path('drivers/<uuid:driver_id>/logs/', get_driver_logs, name='driver-logs'),
    path('logs/compliance-check/', compliance_check, name='compliance-check'),
    path('logs/<uuid:log_id>/route/', get_log_route_view, name='log-route'),
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    
    # GPS & Geocoding endpoints
    path('gps/geocode/', geocode_location_view, name='geocode'),
    path('gps/reverse-geocode/', reverse_geocode_view, name='reverse-geocode'),
    path('gps/batch-geocode/', batch_geocode_view, name='batch-geocode'),
    path('gps/calculate-distance/', calculate_distance_view, name='calculate-distance'),
    path('gps/calculate-route-distance/', calculate_route_distance_view, name='calculate-route-distance'),
]
