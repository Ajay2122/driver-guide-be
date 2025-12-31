"""
GPS and Geocoding API Views
Provides endpoints for geocoding, distance calculation, and route generation
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404

from ..models import DailyLog
from ..mixins import StandardResponseMixin
from ..gps_service import (
    geocode_location,
    reverse_geocode,
    batch_geocode,
    calculate_distance,
    calculate_route_stats,
    get_coordinates_from_input
)


class GPSResponseMixin(StandardResponseMixin):
    """Mixin for GPS API responses"""
    pass


response_mixin = GPSResponseMixin()


@api_view(['POST'])
def geocode_location_view(request):
    """
    POST /api/v1/gps/geocode
    Convert location name to GPS coordinates using FREE OpenStreetMap Nominatim API
    
    Request body:
    {
        "location": "Los Angeles"
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "location": "Los Angeles",
            "coordinates": {"lat": 34.0522, "lng": -118.2437},
            "formattedAddress": "Los Angeles, CA, USA"
        }
    }
    """
    location_name = request.data.get('location')
    
    if not location_name:
        return response_mixin.error_response(
            message="Location name is required",
            errors={'location': ['This field is required']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    # Try to get coordinates
    coordinates = geocode_location(location_name)
    
    if coordinates:
        return response_mixin.success_response(
            data={
                'location': location_name,
                'coordinates': {
                    'lat': coordinates['lat'],
                    'lng': coordinates['lng']
                },
                'formattedAddress': coordinates.get('formatted_address', '')
            },
            message="Location geocoded successfully"
        )
    else:
        return response_mixin.error_response(
            message="Location not found. Please enter:\n- Location name (e.g., 'Los Angeles')\n- GPS coordinates (e.g., '34.0522, -118.2437')",
            errors={'location': ['Location not found']},
            status_code=http_status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
def reverse_geocode_view(request):
    """
    POST /api/v1/gps/reverse-geocode
    Convert GPS coordinates to address
    
    Request body:
    {
        "lat": 34.0522,
        "lng": -118.2437
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "coordinates": {"lat": 34.0522, "lng": -118.2437},
            "address": "Los Angeles, CA, USA",
            "city": "Los Angeles",
            "state": "CA",
            "country": "USA"
        }
    }
    """
    lat = request.data.get('lat')
    lng = request.data.get('lng')
    
    if lat is None or lng is None:
        return response_mixin.error_response(
            message="Both lat and lng are required",
            errors={'coordinates': ['Latitude and longitude are required']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return response_mixin.error_response(
            message="Invalid coordinates",
            errors={'coordinates': ['Latitude and longitude must be numbers']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    # Validate ranges
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return response_mixin.error_response(
            message="Invalid coordinate ranges",
            errors={'coordinates': ['Latitude must be between -90 and 90, longitude between -180 and 180']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    address_info = reverse_geocode(lat, lng)
    
    if address_info:
        return response_mixin.success_response(
            data={
                'coordinates': {'lat': lat, 'lng': lng},
                **address_info
            },
            message="Reverse geocoding successful"
        )
    else:
        return response_mixin.error_response(
            message="Address not found for coordinates",
            status_code=http_status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
def batch_geocode_view(request):
    """
    POST /api/v1/gps/batch-geocode
    Geocode multiple locations at once (with rate limiting)
    
    Request body:
    {
        "locations": ["Los Angeles", "San Francisco", "Houston"]
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "results": [
                {
                    "location": "Los Angeles",
                    "coordinates": {"lat": 34.0522, "lng": -118.2437},
                    "status": "found"
                },
                ...
            ],
            "successCount": 3,
            "failureCount": 0
        }
    }
    """
    locations = request.data.get('locations', [])
    
    if not locations or not isinstance(locations, list):
        return response_mixin.error_response(
            message="Locations array is required",
            errors={'locations': ['Must be a non-empty array of location names']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    results = batch_geocode(locations)
    
    success_count = sum(1 for r in results if r['status'] == 'found')
    failure_count = len(results) - success_count
    
    return response_mixin.success_response(
        data={
            'results': results,
            'successCount': success_count,
            'failureCount': failure_count
        },
        message=f"Batch geocoding completed ({success_count} found, {failure_count} not found)"
    )


@api_view(['POST'])
def calculate_distance_view(request):
    """
    POST /api/v1/gps/calculate-distance
    Calculate distance between two GPS coordinates
    
    Request body:
    {
        "origin": {"lat": 34.0522, "lng": -118.2437},
        "destination": {"lat": 37.7749, "lng": -122.4194},
        "unit": "miles"  // optional: "miles" or "kilometers"
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "distance": 382.7,
            "unit": "miles",
            "origin": {"lat": 34.0522, "lng": -118.2437},
            "destination": {"lat": 37.7749, "lng": -122.4194}
        }
    }
    """
    origin = request.data.get('origin')
    destination = request.data.get('destination')
    unit = request.data.get('unit', 'miles')
    
    # Validate inputs
    if not origin or not destination:
        return response_mixin.error_response(
            message="Origin and destination are required",
            errors={'coordinates': ['Both origin and destination coordinates are required']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    if unit not in ['miles', 'kilometers']:
        return response_mixin.error_response(
            message="Invalid unit",
            errors={'unit': ['Unit must be either "miles" or "kilometers"']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    try:
        origin_lat = float(origin.get('lat'))
        origin_lng = float(origin.get('lng'))
        dest_lat = float(destination.get('lat'))
        dest_lng = float(destination.get('lng'))
    except (ValueError, TypeError, AttributeError):
        return response_mixin.error_response(
            message="Invalid coordinates",
            errors={'coordinates': ['Coordinates must be valid numbers']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    distance = calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng, unit)
    
    return response_mixin.success_response(
        data={
            'distance': distance,
            'unit': unit,
            'origin': origin,
            'destination': destination
        },
        message="Distance calculated successfully"
    )


@api_view(['POST'])
def calculate_route_distance_view(request):
    """
    POST /api/v1/gps/calculate-route-distance
    Calculate total route distance from multiple waypoints
    
    Request body:
    {
        "waypoints": [
            {"lat": 34.0522, "lng": -118.2437},
            {"lat": 35.3733, "lng": -119.0187},
            {"lat": 37.7749, "lng": -122.4194}
        ],
        "unit": "miles"  // optional
    }
    
    Response:
    {
        "status": "success",
        "data": {
            "totalDistance": 495.2,
            "unit": "miles",
            "segments": [
                {
                    "from": {"lat": 34.0522, "lng": -118.2437},
                    "to": {"lat": 35.3733, "lng": -119.0187},
                    "distance": 112.5
                },
                ...
            ],
            "waypointCount": 3
        }
    }
    """
    waypoints = request.data.get('waypoints', [])
    unit = request.data.get('unit', 'miles')
    
    if not waypoints or len(waypoints) < 2:
        return response_mixin.error_response(
            message="At least 2 waypoints are required",
            errors={'waypoints': ['Must provide at least 2 waypoints']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    if unit not in ['miles', 'kilometers']:
        unit = 'miles'
    
    segments = []
    total_distance = 0.0
    
    try:
        for i in range(len(waypoints) - 1):
            from_point = waypoints[i]
            to_point = waypoints[i + 1]
            
            distance = calculate_distance(
                float(from_point['lat']),
                float(from_point['lng']),
                float(to_point['lat']),
                float(to_point['lng']),
                unit
            )
            
            total_distance += distance
            
            segments.append({
                'from': from_point,
                'to': to_point,
                'distance': distance
            })
    except (ValueError, TypeError, KeyError):
        return response_mixin.error_response(
            message="Invalid waypoint coordinates",
            errors={'waypoints': ['Each waypoint must have valid lat and lng']},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )
    
    return response_mixin.success_response(
        data={
            'totalDistance': round(total_distance, 1),
            'unit': unit,
            'segments': segments,
            'waypointCount': len(waypoints)
        },
        message="Route distance calculated successfully"
    )


@api_view(['GET'])
def get_log_route_view(request, log_id):
    """
    GET /api/v1/logs/{log_id}/route
    Get route data for a specific daily log with driving segments
    
    Response:
    {
        "status": "success",
        "data": {
            "logId": "uuid",
            "date": "2024-01-15",
            "driver": {...},
            "locations": [...],
            "drivingSegments": [
                {
                    "start": {"lat": 34.0522, "lng": -118.2437},
                    "startStatus": "on-duty",
                    "end": {"lat": 37.7749, "lng": -122.4194},
                    "endStatus": "driving",
                    "distance": 382.7
                }
            ],
            "routeStats": {
                "totalDrivingDistance": 382.7,
                "totalLocations": 2,
                ...
            }
        }
    }
    """
    # Get the daily log
    daily_log = get_object_or_404(DailyLog.objects.select_related('driver'), pk=log_id)
    
    # Extract duty statuses with coordinates
    duty_statuses = daily_log.duty_statuses
    statuses_with_coords = [s for s in duty_statuses if s.get('coordinates')]
    
    # Calculate route statistics
    route_stats = calculate_route_stats(duty_statuses)
    
    # Build location list
    locations = []
    for status in statuses_with_coords:
        coords = status.get('coordinates', {})
        locations.append({
            'status': status.get('status'),
            'location': status.get('location', ''),
            'coordinates': coords,
            'time': f"{str(status.get('startHour', 0)).zfill(2)}:{str(status.get('startMinute', 0)).zfill(2)}"
        })
    
    return response_mixin.success_response(
        data={
            'logId': str(daily_log.id),
            'date': daily_log.date.isoformat(),
            'driver': {
                'id': str(daily_log.driver.id),
                'name': daily_log.driver.name
            },
            'locations': locations,
            'drivingSegments': route_stats['drivingSegments'],
            'routeStats': {
                'totalDrivingDistance': route_stats['totalDrivingDistance'],
                'totalLocations': route_stats['totalLocations'],
                'drivingLocations': route_stats['drivingLocations'],
                'onDutyLocations': route_stats['onDutyLocations'],
                'offDutyLocations': route_stats['offDutyLocations'],
                'sleeperLocations': route_stats['sleeperLocations']
            }
        },
        message="Route data fetched successfully"
    )

