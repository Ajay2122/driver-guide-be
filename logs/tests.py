from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
import uuid

from .models import Driver, DailyLog
from .serializers import DriverSerializer, DailyLogSerializer, DutyStatusSerializer
from .services import (
    calculate_duration,
    calculate_hours_from_duty_statuses,
    validate_11_hour_driving_limit,
    validate_14_hour_window,
    validate_10_hour_rest,
    check_hos_compliance
)
from .exceptions import DriverNotFound, LogNotFound


class DriverModelTest(TestCase):
    """Test Driver model"""
    
    def setUp(self):
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Los Angeles Terminal",
            main_office_address="123 Main St, Los Angeles, CA 90001"
        )
    
    def test_driver_creation(self):
        """Test driver can be created"""
        self.assertIsNotNone(self.driver.id)
        self.assertEqual(self.driver.name, "John Smith")
        self.assertEqual(self.driver.license_number, "DL-12345678")
        self.assertTrue(isinstance(self.driver.id, uuid.UUID))
    
    def test_driver_str_representation(self):
        """Test driver string representation"""
        expected = "John Smith (DL-12345678)"
        self.assertEqual(str(self.driver), expected)
    
    def test_driver_unique_license_number(self):
        """Test license number must be unique"""
        with self.assertRaises(Exception):
            Driver.objects.create(
                name="Another Driver",
                license_number="DL-12345678",  # Same license number
                home_terminal="Houston Terminal",
                main_office_address="456 Oak Ave"
            )
    
    def test_driver_timestamps(self):
        """Test created_at and updated_at are set"""
        self.assertIsNotNone(self.driver.created_at)
        self.assertIsNotNone(self.driver.updated_at)


class DailyLogModelTest(TestCase):
    """Test DailyLog model"""
    
    def setUp(self):
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Los Angeles Terminal",
            main_office_address="123 Main St, Los Angeles, CA 90001"
        )
        
        self.duty_statuses = [
            {
                "status": "off-duty",
                "startHour": 0,
                "startMinute": 0,
                "endHour": 6,
                "endMinute": 0
            },
            {
                "status": "driving",
                "startHour": 6,
                "startMinute": 0,
                "endHour": 17,
                "endMinute": 0,
                "location": "I-95"
            },
            {
                "status": "off-duty",
                "startHour": 17,
                "startMinute": 0,
                "endHour": 24,
                "endMinute": 0
            }
        ]
        
        self.daily_log = DailyLog.objects.create(
            driver=self.driver,
            date=date.today(),
            duty_statuses=self.duty_statuses,
            hours_off_duty=Decimal('13.00'),
            hours_sleeper=Decimal('0.00'),
            hours_driving=Decimal('11.00'),
            hours_on_duty=Decimal('0.00'),
            hours_total=Decimal('24.00'),
            total_miles=450,
            vehicle_numbers="TRK-1001"
        )
    
    def test_daily_log_creation(self):
        """Test daily log can be created"""
        self.assertIsNotNone(self.daily_log.id)
        self.assertEqual(self.daily_log.driver, self.driver)
        self.assertEqual(self.daily_log.date, date.today())
        self.assertEqual(len(self.daily_log.duty_statuses), 3)
    
    def test_daily_log_str_representation(self):
        """Test daily log string representation"""
        expected = f"John Smith - {date.today()}"
        self.assertEqual(str(self.daily_log), expected)
    
    def test_daily_log_unique_constraint(self):
        """Test driver can only have one log per date"""
        with self.assertRaises(Exception):
            DailyLog.objects.create(
                driver=self.driver,
                date=date.today(),  # Same date
                duty_statuses=self.duty_statuses,
                hours_off_duty=Decimal('13.00'),
                hours_sleeper=Decimal('0.00'),
                hours_driving=Decimal('11.00'),
                hours_on_duty=Decimal('0.00'),
                hours_total=Decimal('24.00')
            )
    
    def test_daily_log_cascade_delete(self):
        """Test deleting driver deletes associated logs"""
        log_id = self.daily_log.id
        self.driver.delete()
        self.assertFalse(DailyLog.objects.filter(id=log_id).exists())


class ServiceFunctionsTest(TestCase):
    """Test HOS compliance service functions"""
    
    def test_calculate_duration_simple(self):
        """Test simple duration calculation"""
        duration = calculate_duration(6, 0, 17, 0)
        self.assertEqual(duration, 11.0)
    
    def test_calculate_duration_with_minutes(self):
        """Test duration calculation with minutes"""
        duration = calculate_duration(6, 30, 17, 45)
        self.assertEqual(duration, 11.25)
    
    def test_calculate_duration_midnight_crossing(self):
        """Test duration calculation crossing midnight"""
        duration = calculate_duration(22, 0, 6, 0)  # 10 PM to 6 AM
        self.assertEqual(duration, 8.0)
    
    def test_calculate_duration_end_at_midnight(self):
        """Test duration calculation ending at midnight (24:00)"""
        duration = calculate_duration(0, 0, 24, 0)
        self.assertEqual(duration, 24.0)
    
    def test_calculate_hours_from_duty_statuses(self):
        """Test hours calculation from duty statuses"""
        duty_statuses = [
            {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 6, "endMinute": 0},
            {"status": "driving", "startHour": 6, "startMinute": 0, "endHour": 17, "endMinute": 0},
            {"status": "off-duty", "startHour": 17, "startMinute": 0, "endHour": 24, "endMinute": 0}
        ]
        
        hours = calculate_hours_from_duty_statuses(duty_statuses)
        self.assertEqual(hours['offDuty'], 13.0)
        self.assertEqual(hours['driving'], 11.0)
        self.assertEqual(hours['total'], 24.0)
    
    def test_validate_11_hour_driving_limit_compliant(self):
        """Test 11-hour driving limit validation - compliant"""
        duty_statuses = [
            {"status": "driving", "startHour": 6, "startMinute": 0, "endHour": 17, "endMinute": 0}
        ]
        is_valid, violations = validate_11_hour_driving_limit(duty_statuses)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)
    
    def test_validate_11_hour_driving_limit_violation(self):
        """Test 11-hour driving limit validation - violation"""
        duty_statuses = [
            {"status": "driving", "startHour": 0, "startMinute": 0, "endHour": 12, "endMinute": 0}  # 12 hours
        ]
        is_valid, violations = validate_11_hour_driving_limit(duty_statuses)
        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 1)
        self.assertIn('11_HOUR_DRIVING_LIMIT', violations[0]['rule'])
    
    def test_validate_14_hour_window_compliant(self):
        """Test 14-hour window validation - compliant"""
        duty_statuses = [
            {"status": "on-duty", "startHour": 6, "startMinute": 0, "endHour": 7, "endMinute": 0},
            {"status": "driving", "startHour": 7, "startMinute": 0, "endHour": 20, "endMinute": 0}  # 13 hours total
        ]
        is_valid, violations = validate_14_hour_window(duty_statuses)
        self.assertTrue(is_valid)
    
    def test_validate_14_hour_window_violation(self):
        """Test 14-hour window validation - violation"""
        duty_statuses = [
            {"status": "on-duty", "startHour": 6, "startMinute": 0, "endHour": 7, "endMinute": 0},
            {"status": "driving", "startHour": 7, "startMinute": 0, "endHour": 22, "endMinute": 0}  # 15 hours total
        ]
        is_valid, violations = validate_14_hour_window(duty_statuses)
        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 1)
        self.assertIn('14_HOUR_WINDOW', violations[0]['rule'])
    
    def test_validate_10_hour_rest_compliant(self):
        """Test 10-hour rest validation - compliant"""
        duty_statuses = [
            {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 10, "endMinute": 0}
        ]
        is_valid, violations = validate_10_hour_rest(duty_statuses)
        self.assertTrue(is_valid)
    
    def test_validate_10_hour_rest_violation(self):
        """Test 10-hour rest validation - violation"""
        duty_statuses = [
            {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 9, "endMinute": 0}  # Only 9 hours
        ]
        is_valid, violations = validate_10_hour_rest(duty_statuses)
        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 1)
        self.assertIn('10_HOUR_REST', violations[0]['rule'])
    
    def test_check_hos_compliance_compliant(self):
        """Test full HOS compliance check - compliant"""
        duty_statuses = [
            {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 10, "endMinute": 0},
            {"status": "driving", "startHour": 10, "startMinute": 0, "endHour": 21, "endMinute": 0},
            {"status": "off-duty", "startHour": 21, "startMinute": 0, "endHour": 24, "endMinute": 0}
        ]
        
        result = check_hos_compliance(duty_statuses)
        self.assertTrue(result['isCompliant'])
        self.assertEqual(len(result['violations']), 0)
        self.assertEqual(result['hours']['total'], 24.0)
    
    def test_check_hos_compliance_violations(self):
        """Test full HOS compliance check - with violations"""
        duty_statuses = [
            {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 6, "endMinute": 0},
            {"status": "driving", "startHour": 6, "startMinute": 0, "endHour": 19, "endMinute": 0},  # 13 hours driving
            {"status": "off-duty", "startHour": 19, "startMinute": 0, "endHour": 24, "endMinute": 0}
        ]
        
        result = check_hos_compliance(duty_statuses)
        self.assertFalse(result['isCompliant'])
        self.assertGreater(len(result['violations']), 0)


class DriverSerializerTest(TestCase):
    """Test Driver serializer"""
    
    def setUp(self):
        self.driver_data = {
            "name": "John Smith",
            "licenseNumber": "DL-12345678",
            "homeTerminal": "Los Angeles Terminal",
            "mainOfficeAddress": "123 Main St, Los Angeles, CA 90001"
        }
    
    def test_driver_serializer_valid_data(self):
        """Test serializer with valid data"""
        serializer = DriverSerializer(data=self.driver_data)
        self.assertTrue(serializer.is_valid())
    
    def test_driver_serializer_create(self):
        """Test serializer creates driver"""
        serializer = DriverSerializer(data=self.driver_data)
        self.assertTrue(serializer.is_valid())
        driver = serializer.save()
        self.assertEqual(driver.name, "John Smith")
        self.assertEqual(driver.license_number, "DL-12345678")
    
    def test_driver_serializer_license_number_unique(self):
        """Test serializer validates unique license number"""
        Driver.objects.create(
            name="Existing Driver",
            license_number="DL-12345678",
            home_terminal="Terminal",
            main_office_address="Address"
        )
        
        serializer = DriverSerializer(data=self.driver_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('licenseNumber', serializer.errors)


class DailyLogSerializerTest(TestCase):
    """Test DailyLog serializer"""
    
    def setUp(self):
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Los Angeles Terminal",
            main_office_address="123 Main St"
        )
        
        self.log_data = {
            "driverId": str(self.driver.id),
            "date": str(date.today()),
            "dutyStatuses": [
                {
                    "status": "off-duty",
                    "startHour": 0,
                    "startMinute": 0,
                    "endHour": 10,
                    "endMinute": 0
                },
                {
                    "status": "driving",
                    "startHour": 10,
                    "startMinute": 0,
                    "endHour": 21,
                    "endMinute": 0,
                    "location": "I-95"
                },
                {
                    "status": "off-duty",
                    "startHour": 21,
                    "startMinute": 0,
                    "endHour": 24,
                    "endMinute": 0
                }
            ],
            "totalMiles": 450,
            "vehicleNumbers": "TRK-1001"
        }
    
    def test_daily_log_serializer_valid_data(self):
        """Test serializer with valid data"""
        serializer = DailyLogSerializer(data=self.log_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
    
    def test_daily_log_serializer_future_date(self):
        """Test serializer rejects future date"""
        self.log_data['date'] = str(date.today() + timedelta(days=1))
        serializer = DailyLogSerializer(data=self.log_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('date', serializer.errors)
    
    def test_daily_log_serializer_invalid_hours(self):
        """Test serializer rejects invalid hours (not 24)"""
        # Remove one duty status to make total != 24
        self.log_data['dutyStatuses'] = [
            {"status": "driving", "startHour": 0, "startMinute": 0, "endHour": 12, "endMinute": 0}
        ]
        serializer = DailyLogSerializer(data=self.log_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('dutyStatuses', serializer.errors)


class DriverAPITest(APITestCase):
    """Test Driver API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Los Angeles Terminal",
            main_office_address="123 Main St, Los Angeles, CA 90001"
        )
        self.driver_data = {
            "name": "Jane Doe",
            "licenseNumber": "DL-87654321",
            "homeTerminal": "Houston Terminal",
            "mainOfficeAddress": "456 Oak Ave, Houston, TX 77001"
        }
    
    def test_create_driver(self):
        """Test POST /api/v1/drivers"""
        response = self.client.post('/api/v1/drivers/', self.driver_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['name'], 'Jane Doe')
    
    def test_list_drivers(self):
        """Test GET /api/v1/drivers"""
        response = self.client.get('/api/v1/drivers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('drivers', response.data['data'])
        self.assertEqual(len(response.data['data']['drivers']), 1)
    
    def test_retrieve_driver(self):
        """Test GET /api/v1/drivers/{id}"""
        response = self.client.get(f'/api/v1/drivers/{self.driver.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['name'], 'John Smith')
    
    def test_retrieve_driver_not_found(self):
        """Test GET /api/v1/drivers/{id} with invalid ID"""
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/v1/drivers/{fake_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_update_driver(self):
        """Test PUT /api/v1/drivers/{id}"""
        update_data = self.driver_data.copy()
        update_data['licenseNumber'] = self.driver.license_number
        response = self.client.put(f'/api/v1/drivers/{self.driver.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], 'Jane Doe')
    
    def test_partial_update_driver(self):
        """Test PATCH /api/v1/drivers/{id}"""
        response = self.client.patch(
            f'/api/v1/drivers/{self.driver.id}/',
            {'name': 'John Updated'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], 'John Updated')
    
    def test_delete_driver(self):
        """Test DELETE /api/v1/drivers/{id}"""
        response = self.client.delete(f'/api/v1/drivers/{self.driver.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Driver.objects.filter(id=self.driver.id).exists())
    
    def test_search_drivers(self):
        """Test search functionality"""
        Driver.objects.create(
            name="Jane Doe",
            license_number="DL-99999999",
            home_terminal="Houston",
            main_office_address="123 Street"
        )
        
        response = self.client.get('/api/v1/drivers/?search=Jane')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['drivers']), 1)
        self.assertEqual(response.data['data']['drivers'][0]['name'], 'Jane Doe')
    
    def test_driver_pagination(self):
        """Test driver list pagination"""
        # Create multiple drivers
        for i in range(25):
            Driver.objects.create(
                name=f"Driver {i}",
                license_number=f"DL-{i:08d}",
                home_terminal="Terminal",
                main_office_address="Address"
            )
        
        response = self.client.get('/api/v1/drivers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('pagination', response.data['data'])
        self.assertEqual(len(response.data['data']['drivers']), 20)  # Default page size


class DailyLogAPITest(APITestCase):
    """Test DailyLog API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Los Angeles Terminal",
            main_office_address="123 Main St"
        )
        
        self.log_data = {
            "driverId": str(self.driver.id),
            "date": str(date.today()),
            "dutyStatuses": [
                {
                    "status": "off-duty",
                    "startHour": 0,
                    "startMinute": 0,
                    "endHour": 10,
                    "endMinute": 0
                },
                {
                    "status": "driving",
                    "startHour": 10,
                    "startMinute": 0,
                    "endHour": 21,
                    "endMinute": 0,
                    "location": "I-95"
                },
                {
                    "status": "off-duty",
                    "startHour": 21,
                    "startMinute": 0,
                    "endHour": 24,
                    "endMinute": 0
                }
            ],
            "totalMiles": 450,
            "vehicleNumbers": "TRK-1001",
            "remarks": "Normal operations"
        }
        
        self.daily_log = DailyLog.objects.create(
            driver=self.driver,
            date=date.today() - timedelta(days=1),
            duty_statuses=self.log_data['dutyStatuses'],
            hours_off_duty=Decimal('13.00'),
            hours_sleeper=Decimal('0.00'),
            hours_driving=Decimal('11.00'),
            hours_on_duty=Decimal('0.00'),
            hours_total=Decimal('24.00'),
            total_miles=450
        )
    
    def test_create_log(self):
        """Test POST /api/v1/logs"""
        # Use yesterday's date to avoid conflict
        self.log_data['date'] = str(date.today() - timedelta(days=2))
        response = self.client.post('/api/v1/logs/', self.log_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('hours', response.data['data'])
    
    def test_create_log_duplicate_date(self):
        """Test creating log with duplicate date fails"""
        self.log_data['date'] = str(date.today() - timedelta(days=1))
        response = self.client.post('/api/v1/logs/', self.log_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_logs(self):
        """Test GET /api/v1/logs"""
        response = self.client.get('/api/v1/logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('logs', response.data['data'])
    
    def test_filter_logs_by_driver(self):
        """Test filtering logs by driver"""
        response = self.client.get(f'/api/v1/logs/?driver_id={self.driver.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['logs']), 1)
    
    def test_filter_logs_by_date_range(self):
        """Test filtering logs by date range"""
        start_date = str(date.today() - timedelta(days=2))
        end_date = str(date.today())
        response = self.client.get(f'/api/v1/logs/?start_date={start_date}&end_date={end_date}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_log(self):
        """Test GET /api/v1/logs/{id}"""
        response = self.client.get(f'/api/v1/logs/{self.daily_log.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['id'], str(self.daily_log.id))
    
    def test_update_log(self):
        """Test PUT /api/v1/logs/{id}"""
        update_data = self.log_data.copy()
        update_data['date'] = str(date.today() - timedelta(days=3))
        update_data['remarks'] = 'Updated remarks'
        response = self.client.put(f'/api/v1/logs/{self.daily_log.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['remarks'], 'Updated remarks')
    
    def test_delete_log(self):
        """Test DELETE /api/v1/logs/{id}"""
        log_id = self.daily_log.id
        response = self.client.delete(f'/api/v1/logs/{log_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(DailyLog.objects.filter(id=log_id).exists())


class DriverLogsAPITest(APITestCase):
    """Test driver-specific logs endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Terminal",
            main_office_address="Address"
        )
        
        # Create multiple logs for this driver
        for i in range(3):
            DailyLog.objects.create(
                driver=self.driver,
                date=date.today() - timedelta(days=i+1),
                duty_statuses=[{"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 24, "endMinute": 0}],
                hours_off_duty=Decimal('24.00'),
                hours_total=Decimal('24.00')
            )
    
    def test_get_driver_logs(self):
        """Test GET /api/v1/drivers/{id}/logs"""
        response = self.client.get(f'/api/v1/drivers/{self.driver.id}/logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(len(response.data['data']['logs']), 3)
    
    def test_get_driver_logs_with_date_filter(self):
        """Test GET /api/v1/drivers/{id}/logs with date filter"""
        start_date = str(date.today() - timedelta(days=2))
        response = self.client.get(f'/api/v1/drivers/{self.driver.id}/logs/?startDate={start_date}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['data']['logs']), 3)


class StatisticsAPITest(APITestCase):
    """Test statistics endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.driver = Driver.objects.create(
            name="John Smith",
            license_number="DL-12345678",
            home_terminal="Terminal",
            main_office_address="Address"
        )
        
        # Create logs for statistics
        for i in range(5):
            DailyLog.objects.create(
                driver=self.driver,
                date=date.today() - timedelta(days=i+1),
                duty_statuses=[
                    {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 10, "endMinute": 0},
                    {"status": "driving", "startHour": 10, "startMinute": 0, "endHour": 21, "endMinute": 0},
                    {"status": "off-duty", "startHour": 21, "startMinute": 0, "endHour": 24, "endMinute": 0}
                ],
                hours_off_duty=Decimal('13.00'),
                hours_driving=Decimal('11.00'),
                hours_total=Decimal('24.00'),
                total_miles=450,
                is_compliant=True
            )
    
    def test_get_driver_stats(self):
        """Test GET /api/v1/drivers/{id}/stats"""
        response = self.client.get(f'/api/v1/drivers/{self.driver.id}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('summary', response.data['data'])
        self.assertIn('compliance', response.data['data'])
    
    def test_compliance_check(self):
        """Test POST /api/v1/logs/compliance-check"""
        data = {
            "dutyStatuses": [
                {"status": "off-duty", "startHour": 0, "startMinute": 0, "endHour": 10, "endMinute": 0},
                {"status": "driving", "startHour": 10, "startMinute": 0, "endHour": 21, "endMinute": 0},
                {"status": "off-duty", "startHour": 21, "startMinute": 0, "endHour": 24, "endMinute": 0}
            ]
        }
        response = self.client.post('/api/v1/logs/compliance-check/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('isCompliant', response.data['data'])
        self.assertIn('violations', response.data['data'])
    
    def test_compliance_check_violation(self):
        """Test compliance check with violation"""
        data = {
            "dutyStatuses": [
                {"status": "driving", "startHour": 0, "startMinute": 0, "endHour": 12, "endMinute": 0}  # 12 hours
            ]
        }
        response = self.client.post('/api/v1/logs/compliance-check/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['data']['isCompliant'])
        self.assertGreater(len(response.data['data']['violations']), 0)
    
    def test_dashboard_stats(self):
        """Test GET /api/v1/dashboard/stats"""
        response = self.client.get('/api/v1/dashboard/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('totalDrivers', response.data['data'])
        self.assertIn('totalLogs', response.data['data'])
        self.assertIn('complianceRate', response.data['data'])


class ErrorHandlingTest(APITestCase):
    """Test error handling"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_404_driver_not_found(self):
        """Test 404 error for non-existent driver"""
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/v1/drivers/{fake_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'error')
    
    def test_400_validation_error(self):
        """Test 400 error for validation failures"""
        invalid_data = {
            "name": "A",  # Too short
            "licenseNumber": "DL-123",
            "homeTerminal": "T",
            "mainOfficeAddress": "A"
        }
        response = self.client.post('/api/v1/drivers/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('errors', response.data)
