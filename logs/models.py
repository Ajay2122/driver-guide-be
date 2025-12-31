import uuid
from django.db import models
from django.core.validators import MinLengthValidator, MaxLengthValidator


class Driver(models.Model):
    """Driver model for storing driver information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(2), MaxLengthValidator(255)]
    )
    license_number = models.CharField(
        max_length=100,
        unique=True,
        validators=[MinLengthValidator(5), MaxLengthValidator(100)]
    )
    home_terminal = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(2), MaxLengthValidator(255)]
    )
    main_office_address = models.TextField(
        validators=[MinLengthValidator(5), MaxLengthValidator(500)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drivers'
        indexes = [
            models.Index(fields=['license_number']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.license_number})"


class DailyLog(models.Model):
    """Daily log model for tracking driver hours and duty statuses"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name='daily_logs'
    )
    date = models.DateField()
    duty_statuses = models.JSONField(help_text="Array of duty status objects")
    remarks = models.TextField(blank=True, null=True)
    shipping_documents = models.CharField(max_length=255, blank=True, null=True)
    co_driver_name = models.CharField(max_length=255, blank=True, null=True)
    vehicle_numbers = models.CharField(max_length=255, blank=True, null=True)
    total_miles = models.IntegerField(default=0)
    total_miles_today = models.IntegerField(default=0)
    total_miles_yesterday = models.IntegerField(default=0)
    
    # Hours tracking
    hours_off_duty = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    hours_sleeper = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    hours_driving = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    hours_on_duty = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    hours_total = models.DecimalField(max_digits=5, decimal_places=2, default=24.00)
    
    # Compliance tracking (optional)
    is_compliant = models.BooleanField(null=True, blank=True)
    violations = models.JSONField(default=list, blank=True, help_text="Array of violation objects")
    
    # GPS/Route tracking
    total_driving_distance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Total miles driven (calculated from GPS coordinates)"
    )
    route_stats = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Route statistics (segments, location counts, etc.)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_logs'
        constraints = [
            models.UniqueConstraint(fields=['driver', 'date'], name='unique_driver_date')
        ]
        indexes = [
            models.Index(fields=['driver']),
            models.Index(fields=['date']),
            models.Index(fields=['driver', 'date']),
        ]
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.driver.name} - {self.date}"


class LocationCache(models.Model):
    """Cache for geocoded locations to reduce API calls"""
    location_name = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text="Location name (e.g., 'Los Angeles Terminal')"
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Longitude coordinate"
    )
    formatted_address = models.TextField(
        blank=True,
        help_text="Full formatted address from geocoding service"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'location_cache'
        indexes = [
            models.Index(fields=['location_name']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.location_name} ({self.latitude}, {self.longitude})"
