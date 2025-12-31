# Driver's Daily Log - Backend API

A Django REST Framework-based backend API for managing driver daily logs with HOS (Hours of Service) compliance, GPS geocoding, and route tracking capabilities.

## Features

### Core Functionality
- **Driver Management API** - CRUD operations for driver profiles
- **Daily Log Management** - Create, retrieve, update, delete logs
- **HOS Compliance Validation** - Automatic compliance checking
- **GPS Geocoding** - Free OpenStreetMap Nominatim integration
- **Route Calculations** - Distance and driving segment calculations
- **Location Caching** - Performance optimization for geocoding
- **Statistics & Analytics** - Driver and fleet-wide metrics

### Technical Features
- RESTful API architecture
- Django ORM for database operations
- Automatic coordinate geocoding
- Caching system for geocoded locations
- Rate limiting for external API calls
- Comprehensive API documentation
- Admin panel for data management

## Technology Stack

- **Framework:** Django 4.2
- **API Framework:** Django REST Framework
- **Database:** SQLite (default) / PostgreSQL (production)
- **Geocoding:** OpenStreetMap Nominatim (free, no API key)
- **Language:** Python 3.8+
- **CORS:** django-cors-headers

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

## Installation

### 1. Navigate to Project Directory
```bash
cd BusLogs
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Apply Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 7. Start Development Server
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## Project Structure

```
BusLogs/
├── BusLogs/              # Project settings
│   ├── settings.py       # Django settings
│   ├── urls.py          # Root URL configuration
│   └── wsgi.py          # WSGI application
├── logs/                 # Main application
│   ├── models.py        # Database models
│   ├── serializers.py   # DRF serializers
│   ├── views/           # API views
│   │   ├── drivers.py   # Driver endpoints
│   │   ├── logs.py      # Log endpoints
│   │   └── gps.py       # GPS endpoints
│   ├── urls.py          # App URL routing
│   ├── admin.py         # Admin configuration
│   ├── gps_service.py   # Geocoding service
│   └── tests.py         # Unit tests
├── db.sqlite3           # Database file
├── manage.py            # Django CLI
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Configuration

### Environment Variables

Create a `.env` file in the project root (optional):

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
```

### CORS Configuration

Edit `BusLogs/settings.py`:

```python
INSTALLED_APPS = [
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
]
```

### Database Configuration

**SQLite (Default - Development):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**PostgreSQL (Production):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'driverlog_db',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## API Endpoints

### Base URL
```
http://localhost:8000/api/v1
```

### Driver Management

#### List All Drivers
```http
GET /api/v1/drivers/
```

**Query Parameters:**
- `search` - Search by name or license number
- `ordering` - Sort field (e.g., `name`, `-created_at`)
- `page` - Page number for pagination

**Response:**
```json
{
  "status": "success",
  "data": {
    "drivers": [
      {
        "id": "uuid",
        "name": "John Doe",
        "licenseNumber": "DL-12345678",
        "homeTerminal": "Los Angeles Terminal",
        "mainOfficeAddress": "123 Main St, LA, CA",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z"
      }
    ]
  },
  "message": "Drivers retrieved successfully"
}
```

#### Create Driver
```http
POST /api/v1/drivers/
Content-Type: application/json

{
  "name": "John Doe",
  "licenseNumber": "DL-12345678",
  "homeTerminal": "Los Angeles Terminal",
  "mainOfficeAddress": "123 Main St, LA, CA"
}
```

#### Get Single Driver
```http
GET /api/v1/drivers/{id}/
```

#### Update Driver
```http
PATCH /api/v1/drivers/{id}/
Content-Type: application/json

{
  "name": "John Smith"
}
```

#### Delete Driver
```http
DELETE /api/v1/drivers/{id}/
```

### Daily Logs Management

#### List All Logs
```http
GET /api/v1/logs/
```

**Query Parameters:**
- `driver_id` - Filter by driver
- `start_date` - Filter from date (YYYY-MM-DD)
- `end_date` - Filter to date (YYYY-MM-DD)
- `compliant` - Filter by compliance (true/false)
- `limit` - Limit results

#### Create Log
```http
POST /api/v1/logs/
Content-Type: application/json

{
  "driverId": "driver-uuid",
  "date": "2025-01-01",
  "dutyStatuses": [
    {
      "status": "off-duty",
      "startHour": 0,
      "startMinute": 0,
      "endHour": 6,
      "endMinute": 0
    },
    {
      "status": "driving",
      "startHour": 7,
      "startMinute": 0,
      "endHour": 17,
      "endMinute": 0,
      "location": "Los Angeles, CA"
    }
  ],
  "remarks": "Regular route",
  "vehicleNumbers": "TRUCK-001",
  "totalMiles": 450,
  "autoGeocode": true
}
```

#### Get Single Log
```http
GET /api/v1/logs/{id}/
```

#### Update Log
```http
PATCH /api/v1/logs/{id}/
```

#### Delete Log
```http
DELETE /api/v1/logs/{id}/
```

### GPS & Geocoding

#### Geocode Location
```http
POST /api/v1/gps/geocode/
Content-Type: application/json

{
  "location": "Los Angeles, CA"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "location": "Los Angeles, CA",
    "coordinates": {
      "lat": 34.0522,
      "lng": -118.2437
    },
    "formattedAddress": "Los Angeles, California, United States"
  },
  "message": "Location geocoded successfully"
}
```

#### Reverse Geocode
```http
POST /api/v1/gps/reverse-geocode/
Content-Type: application/json

{
  "lat": 34.0522,
  "lng": -118.2437
}
```

#### Batch Geocode
```http
POST /api/v1/gps/batch-geocode/
Content-Type: application/json

{
  "locations": ["Los Angeles, CA", "San Francisco, CA"]
}
```

#### Calculate Distance
```http
POST /api/v1/gps/calculate-distance/
Content-Type: application/json

{
  "origin": {"lat": 34.0522, "lng": -118.2437},
  "destination": {"lat": 37.7749, "lng": -122.4194},
  "unit": "miles"
}
```

#### Get Log Route
```http
GET /api/v1/logs/{logId}/route/
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "logId": "uuid",
    "date": "2025-01-01",
    "driver": {...},
    "locations": [...],
    "drivingSegments": [
      {
        "from": {...},
        "to": {...},
        "distance": 350.5
      }
    ],
    "routeStats": {
      "totalDrivingDistance": 350.5,
      "totalSegments": 3
    }
  },
  "message": "Route retrieved successfully"
}
```

## Database Models

### Driver
- `id` - UUID (Primary Key)
- `name` - String
- `licenseNumber` - String (Unique)
- `homeTerminal` - String
- `mainOfficeAddress` - String
- `createdAt` - DateTime
- `updatedAt` - DateTime

### DailyLog
- `id` - UUID (Primary Key)
- `driver` - ForeignKey to Driver
- `date` - Date
- `dutyStatuses` - JSON
- `remarks` - Text
- `shippingDocuments` - String
- `coDriverName` - String
- `vehicleNumbers` - String
- `totalMiles` - Integer
- `totalMilesToday` - Integer
- `totalMilesYesterday` - Integer
- `totalDrivingDistance` - Decimal
- `routeStats` - JSON
- `hours` - JSON (calculated)
- `compliance` - JSON (calculated)
- `created` - DateTime
- `updated` - DateTime

### LocationCache
- `id` - UUID (Primary Key)
- `locationName` - String (Unique)
- `latitude` - Decimal
- `longitude` - Decimal
- `formattedAddress` - String
- `createdAt` - DateTime
- `lastUsed` - DateTime

## Admin Panel

Access the Django admin panel at `http://localhost:8000/admin`

**Features:**
- View and edit all drivers
- View and edit all logs
- View geocoding cache
- Clear old cache entries
- User management

**Login:**
Use the superuser credentials created during installation.

## GPS Geocoding Service

### OpenStreetMap Nominatim

The application uses free OpenStreetMap Nominatim service:

**Features:**
- No API key required
- 100% free
- Unlimited requests (with rate limiting)
- Global coverage

**Rate Limiting:**
- 1 request per second (as per Nominatim policy)
- Automatic retry with backoff
- Caching to reduce API calls

**Caching Strategy:**
- All geocoded locations cached in database
- Cache never expires (can be cleared manually)
- Reduces external API calls by 90%+

## Testing

### Run All Tests
```bash
python manage.py test
```

### Run Specific Test
```bash
python manage.py test logs.tests.TestDriverAPI
```

### Test Coverage
```bash
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

## Deployment

### Production Checklist

1. **Update Settings:**
```python
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = 'generate-new-secure-key'
```

2. **Use PostgreSQL:**
```bash
pip install psycopg2-binary
```

3. **Collect Static Files:**
```bash
python manage.py collectstatic
```

4. **Use Gunicorn:**
```bash
pip install gunicorn
gunicorn BusLogs.wsgi:application
```

5. **Set up Nginx:**
Configure Nginx as reverse proxy.

### Deployment Options

**Platform as a Service:**
- Heroku
- AWS Elastic Beanstalk
- DigitalOcean App Platform
- Google Cloud Run

**Container Deployment:**
- Docker + Docker Compose
- Kubernetes

**Traditional Server:**
- Ubuntu + Nginx + Gunicorn
- Systemd for process management

## Performance Optimization

### Database Indexing
```python
class Meta:
    indexes = [
        models.Index(fields=['driver', 'date']),
        models.Index(fields=['date']),
    ]
```

### Query Optimization
- Use `select_related()` for foreign keys
- Use `prefetch_related()` for reverse relations
- Add database indexes for frequently queried fields

### Caching
- Location geocoding cache
- Redis for session/query caching (optional)

## Security

### Best Practices

1. **Secret Key:** Use environment variable
2. **Database Credentials:** Never commit to version control
3. **CORS:** Whitelist specific origins only
4. **HTTPS:** Use SSL certificates in production
5. **Rate Limiting:** Implement API rate limiting
6. **Authentication:** Add JWT or OAuth for production

## Troubleshooting

### Migration Errors
```bash
python manage.py makemigrations --empty logs
python manage.py migrate --fake logs zero
python manage.py migrate
```

### Port Already in Use
```bash
lsof -ti:8000 | xargs kill -9
python manage.py runserver
```

### Database Locked (SQLite)
```bash
rm db.sqlite3
python manage.py migrate
```

### Geocoding Fails
- Check internet connection
- Verify Nominatim is accessible
- Check rate limiting logs
- Try manual curl test

## Monitoring & Logging

### Enable Logging
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
```

## Improvement Points

### High Priority

1. **Authentication & Authorization**
   - JWT token authentication
   - OAuth integration
   - Role-based permissions (Driver, Manager, Admin)
   - Session management

2. **API Rate Limiting**
   - Implement throttling for all endpoints
   - Per-user rate limits
   - Protection against abuse

3. **Asynchronous Processing**
   - Celery for background tasks
   - Async geocoding for batch operations
   - Scheduled compliance reports

4. **Advanced Filtering**
   - Complex query filters
   - Full-text search
   - Date range aggregations

### Medium Priority

5. **WebSocket Support**
   - Real-time log updates
   - Live notifications
   - Multi-user collaboration

6. **File Upload**
   - Document attachments
   - Image uploads (receipts, signatures)
   - S3 integration for storage

7. **Email Notifications**
   - Compliance violation alerts
   - Daily summary emails
   - Report generation and delivery

8. **API Versioning**
   - Version management (v1, v2)
   - Backward compatibility
   - Deprecation warnings

### Low Priority

9. **GraphQL Support**
   - GraphQL endpoint alongside REST
   - Flexible querying
   - Reduced over-fetching

10. **Advanced Analytics**
    - Machine learning for pattern detection
    - Predictive maintenance
    - Route optimization algorithms

11. **Multi-tenancy**
    - Support multiple companies
    - Data isolation
    - Company-specific settings

12. **Audit Logging**
    - Track all data changes
    - User activity logs
    - Compliance audit trail

## Dependencies

```
Django==4.2.0
djangorestframework==3.14.0
django-cors-headers==4.0.0
requests==2.31.0
python-decouple==3.8
```

## Development Tools

### Django Shell
```bash
python manage.py shell
```

### Database Shell
```bash
python manage.py dbshell
```

### Create App
```bash
python manage.py startapp app_name
```

### Check for Issues
```bash
python manage.py check
```

## Contributing

1. Create feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## License

This project is proprietary software for driver log management.

## Related Documentation

- Frontend Application: `../driver-log-app/README.md`
- API Specification: `../BACKEND_API_SPECIFICATION.md`
- GPS Features: `./GPS_FEATURES_DOCUMENTATION.md`
- Full Stack Guide: `../FULL_STACK_INTEGRATION_GUIDE.md`
- Quick Start: `../QUICK_START.md`

## Support

For issues or questions:
- Check troubleshooting section
- Review Django logs
- Test endpoints with curl or Postman
- Check database for data integrity

## Version

**Current Version:** 1.0.0

## Author

Driver's Daily Log Backend API - HOS Compliance Management System
