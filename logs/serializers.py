from rest_framework import serializers
from django.utils import timezone
from .models import Driver, DailyLog
from .services import calculate_hours_from_duty_statuses, check_hos_compliance
from .gps_service import get_coordinates_from_input, calculate_route_stats


class DutyStatusSerializer(serializers.Serializer):
    """Serializer for duty status objects with GPS coordinates support"""
    status = serializers.ChoiceField(choices=['off-duty', 'sleeper', 'driving', 'on-duty'])
    startHour = serializers.IntegerField(min_value=0, max_value=23)
    startMinute = serializers.IntegerField(min_value=0, max_value=59)
    endHour = serializers.IntegerField(min_value=0, max_value=24)
    endMinute = serializers.IntegerField(min_value=0, max_value=59)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    coordinates = serializers.DictField(required=False, allow_null=True, help_text="GPS coordinates {lat, lng}")
    autoGeocoded = serializers.BooleanField(required=False, default=False, help_text="Whether coordinates were auto-geocoded")


class DriverSerializer(serializers.ModelSerializer):
    """Serializer for Driver model"""
    
    class Meta:
        model = Driver
        fields =['id', 'name', 'licenseNumber', 'homeTerminal', 'mainOfficeAddress', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt']
    
    # Convert snake_case to camelCase for API
    licenseNumber = serializers.CharField(source='license_number')
    homeTerminal = serializers.CharField(source='home_terminal')
    mainOfficeAddress = serializers.CharField(source='main_office_address')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    def validate_licenseNumber(self, value):
        """Validate license number uniqueness"""
        if self.instance and self.instance.license_number == value:
            return value
        if Driver.objects.filter(license_number=value).exists():
            raise serializers.ValidationError("License number already exists")
        return value


class DailyLogSerializer(serializers.ModelSerializer):
    """Serializer for DailyLog model with full representation"""
    driver = DriverSerializer(read_only=True)
    driverId = serializers.UUIDField(source='driver_id', write_only=True, required=False)
    dutyStatuses = serializers.JSONField(source='duty_statuses')
    hours = serializers.SerializerMethodField()
    autoGeocode = serializers.BooleanField(write_only=True, required=False, default=False)
    
    class Meta:
        model = DailyLog
        fields = ['id', 'driverId', 'driver', 'date', 'dutyStatuses', 'remarks',
                  'shippingDocuments', 'coDriverName', 'vehicleNumbers', 'totalMiles',"autoGeocode",
                  'totalMilesToday', 'totalMilesYesterday', 'hours', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt']
    
    # Convert snake_case to camelCase
    shippingDocuments = serializers.CharField(source='shipping_documents', required=False, allow_blank=True, allow_null=True)
    coDriverName = serializers.CharField(source='co_driver_name', required=False, allow_blank=True, allow_null=True)
    vehicleNumbers = serializers.CharField(source='vehicle_numbers', required=False, allow_blank=True, allow_null=True)
    totalMiles = serializers.IntegerField(source='total_miles', required=False, default=0)
    totalMilesToday = serializers.IntegerField(source='total_miles_today', required=False, default=0)
    totalMilesYesterday = serializers.IntegerField(source='total_miles_yesterday', required=False, default=0)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    def get_hours(self, obj):
        """Calculate hours from duty statuses"""
        return {
            'offDuty': float(obj.hours_off_duty),
            'sleeper': float(obj.hours_sleeper),
            'driving': float(obj.hours_driving),
            'onDuty': float(obj.hours_on_duty),
            'total': float(obj.hours_total)
        }
    
    def validate_date(self, value):
        """Validate date is not in the future"""
        if value > timezone.now().date():
            raise serializers.ValidationError("Date cannot be in the future")
        return value
    
    def validate_dutyStatuses(self, value):
        """Validate duty statuses structure and calculate hours"""
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("dutyStatuses must be a non-empty array")
        
        # Validate each duty status
        duty_status_serializer = DutyStatusSerializer(data=value, many=True)
        if not duty_status_serializer.is_valid():
            raise serializers.ValidationError(duty_status_serializer.errors)
        
        # Calculate hours
        hours = calculate_hours_from_duty_statuses(value)
        
        # Validate total hours equals 24
        if abs(hours['total'] - 24.0) > 0.01:  # Allow small floating point differences
            raise serializers.ValidationError(
                f"Total hours must equal 24.0, got {hours['total']}"
            )
        
        # Store calculated hours in context for use in create/update
        self.context['calculated_hours'] = hours
        
        return value
    
    def validate(self, attrs):
        """Additional cross-field validation"""
        # Check if driver and date combination already exists
        driver_id = attrs.get('driver_id') or (self.instance.driver_id if self.instance else None)
        date = attrs.get('date') or (self.instance.date if self.instance else None)
        
        if driver_id and date:
            existing_log = DailyLog.objects.filter(
                driver_id=driver_id,
                date=date
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_log.exists():
                raise serializers.ValidationError({
                    'date': ['A log for this driver on this date already exists']
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create daily log with calculated hours and optional auto-geocoding"""
        driver_id = validated_data.pop('driver_id')
        duty_statuses = validated_data.pop('duty_statuses')
        auto_geocode = validated_data.pop('autoGeocode', False) if 'autoGeocode' in self.initial_data else False
        calculated_hours = self.context.get('calculated_hours', {})
        
        # Auto-geocode locations if requested
        if auto_geocode:
            duty_statuses = self._auto_geocode_duty_statuses(duty_statuses)
        
        # Calculate route statistics
        route_stats = calculate_route_stats(duty_statuses)
        
        # Get compliance status
        compliance_result = check_hos_compliance(duty_statuses)
        
        daily_log = DailyLog.objects.create(
            driver_id=driver_id,
            duty_statuses=duty_statuses,
            hours_off_duty=calculated_hours.get('offDuty', 0),
            hours_sleeper=calculated_hours.get('sleeper', 0),
            hours_driving=calculated_hours.get('driving', 0),
            hours_on_duty=calculated_hours.get('onDuty', 0),
            hours_total=calculated_hours.get('total', 24),
            is_compliant=compliance_result['isCompliant'],
            violations=compliance_result['violations'],
            total_driving_distance=route_stats.get('totalDrivingDistance', 0),
            route_stats=route_stats,
            **validated_data
        )
        
        return daily_log
    
    def _auto_geocode_duty_statuses(self, duty_statuses):
        """Auto-geocode duty statuses that have location but no coordinates"""
        geocoded_statuses = []
        
        for status in duty_statuses:
            # If has location but no coordinates, geocode it
            if status.get('location') and not status.get('coordinates'):
                coords = get_coordinates_from_input(status['location'])
                if coords:
                    status['coordinates'] = coords
                    status['autoGeocoded'] = True
            
            geocoded_statuses.append(status)
        
        return geocoded_statuses
    
    def update(self, instance, validated_data):
        """Update daily log with recalculated hours and optional auto-geocoding"""
        if 'driver_id' in validated_data:
            instance.driver_id = validated_data.pop('driver_id')
        
        auto_geocode = validated_data.pop('autoGeocode', False) if 'autoGeocode' in self.initial_data else False
        
        if 'duty_statuses' in validated_data:
            duty_statuses = validated_data['duty_statuses']
            
            # Auto-geocode locations if requested
            if auto_geocode:
                duty_statuses = self._auto_geocode_duty_statuses(duty_statuses)
                validated_data['duty_statuses'] = duty_statuses
            
            calculated_hours = self.context.get('calculated_hours', {})
            compliance_result = check_hos_compliance(duty_statuses)
            
            # Calculate route statistics
            route_stats = calculate_route_stats(duty_statuses)
            
            instance.hours_off_duty = calculated_hours.get('offDuty', 0)
            instance.hours_sleeper = calculated_hours.get('sleeper', 0)
            instance.hours_driving = calculated_hours.get('driving', 0)
            instance.hours_on_duty = calculated_hours.get('onDuty', 0)
            instance.hours_total = calculated_hours.get('total', 24)
            instance.is_compliant = compliance_result['isCompliant']
            instance.violations = compliance_result['violations']
            instance.total_driving_distance = route_stats.get('totalDrivingDistance', 0)
            instance.route_stats = route_stats
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class DailyLogListSerializer(serializers.ModelSerializer):
    """Serializer for DailyLog list view with nested driver info"""
    driver = DriverSerializer(read_only=True)
    hours = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyLog
        fields = ['id', 'driver', 'date', 'dutyStatuses', 'remarks',
                  'shippingDocuments', 'coDriverName', 'vehicleNumbers', 'totalMiles',
                  'totalMilesToday', 'totalMilesYesterday', 'hours', 'createdAt', 'updatedAt']
    
    dutyStatuses = serializers.JSONField(source='duty_statuses')
    shippingDocuments = serializers.CharField(source='shipping_documents', read_only=True)
    coDriverName = serializers.CharField(source='co_driver_name', read_only=True)
    vehicleNumbers = serializers.CharField(source='vehicle_numbers', read_only=True)
    totalMiles = serializers.IntegerField(source='total_miles', read_only=True)
    totalMilesToday = serializers.IntegerField(source='total_miles_today', read_only=True)
    totalMilesYesterday = serializers.IntegerField(source='total_miles_yesterday', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    
    def get_hours(self, obj):
        """Get hours from model"""
        return {
            'offDuty': float(obj.hours_off_duty),
            'sleeper': float(obj.hours_sleeper),
            'driving': float(obj.hours_driving),
            'onDuty': float(obj.hours_on_duty),
            'total': float(obj.hours_total)
        }


class DailyLogCreateSerializer(DailyLogSerializer):
    """Serializer for creating daily logs with validation"""
    driverId = serializers.UUIDField(source='driver_id', write_only=True, required=True)
    
    def create(self, validated_data):
        """Override create to handle driverId and auto-geocoding"""
        driver_id = validated_data.pop('driver_id')
        duty_statuses = validated_data.pop('duty_statuses')
        auto_geocode = validated_data.pop('autoGeocode', False) if 'autoGeocode' in self.initial_data else False
        calculated_hours = self.context.get('calculated_hours', {})
        
        # Check if driver exists
        try:
            driver = Driver.objects.get(pk=driver_id)
        except Driver.DoesNotExist:
            raise serializers.ValidationError({'driverId': ['Driver not found']})
        
        # Auto-geocode locations if requested
        if auto_geocode:
            duty_statuses = self._auto_geocode_duty_statuses(duty_statuses)
        
        # Calculate route statistics
        route_stats = calculate_route_stats(duty_statuses)
        
        # Get compliance status
        compliance_result = check_hos_compliance(duty_statuses)
        
        daily_log = DailyLog.objects.create(
            driver=driver,
            duty_statuses=duty_statuses,
            hours_off_duty=calculated_hours.get('offDuty', 0),
            hours_sleeper=calculated_hours.get('sleeper', 0),
            hours_driving=calculated_hours.get('driving', 0),
            hours_on_duty=calculated_hours.get('onDuty', 0),
            hours_total=calculated_hours.get('total', 24),
            is_compliant=compliance_result['isCompliant'],
            violations=compliance_result['violations'],
            total_driving_distance=route_stats.get('totalDrivingDistance', 0),
            route_stats=route_stats,
            **validated_data
        )
        
        return daily_log


# GPS/Geocoding Serializers

class GeocodeRequestSerializer(serializers.Serializer):
    """Serializer for geocoding requests"""
    location = serializers.CharField(required=True, help_text="Location name to geocode")


class GeocodeResponseSerializer(serializers.Serializer):
    """Serializer for geocoding responses"""
    location = serializers.CharField()
    coordinates = serializers.DictField()
    formattedAddress = serializers.CharField()


class ReverseGeocodeRequestSerializer(serializers.Serializer):
    """Serializer for reverse geocoding requests"""
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)


class DistanceRequestSerializer(serializers.Serializer):
    """Serializer for distance calculation requests"""
    origin = serializers.DictField(required=True)
    destination = serializers.DictField(required=True)
    unit = serializers.ChoiceField(choices=['miles', 'kilometers'], default='miles', required=False)


class BatchGeocodeRequestSerializer(serializers.Serializer):
    """Serializer for batch geocoding requests"""
    locations = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        help_text="Array of location names to geocode"
    )
