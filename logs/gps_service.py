"""
GPS and Geocoding Services
Uses FREE OpenStreetMap Nominatim API (no API key required)
"""
import requests
import time
import math
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from .models import LocationCache


# Configuration
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "DriverLogApp/1.0"  # Required by Nominatim
RATE_LIMIT_DELAY = 1.1  # seconds (Nominatim requires max 1 req/sec)


def geocode_location(location_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Geocode a location name to GPS coordinates using FREE OpenStreetMap Nominatim API.
    
    Args:
        location_name: Location name to geocode (e.g., "Los Angeles")
        use_cache: Whether to use database cache (default: True)
    
    Returns:
        Dict with 'lat', 'lng', 'formatted_address' or None if not found
    """
    if not location_name or not location_name.strip():
        return None
    
    location_name = location_name.strip().lower()
    
    # Check database cache first
    if use_cache:
        try:
            cached_location = LocationCache.objects.filter(
                location_name__iexact=location_name
            ).first()
            
            if cached_location:
                return {
                    'lat': float(cached_location.latitude),
                    'lng': float(cached_location.longitude),
                    'formatted_address': cached_location.formatted_address
                }
        except Exception as e:
            print(f"Cache lookup error: {e}")
    
    # Call Nominatim API
    try:
        url = f"{NOMINATIM_BASE_URL}/search"
        params = {
            'q': location_name,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        headers = {
            'User-Agent': USER_AGENT
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            coordinates = {
                'lat': float(result['lat']),
                'lng': float(result['lon']),
                'formatted_address': result.get('display_name', '')
            }
            
            # Save to cache
            if use_cache:
                try:
                    LocationCache.objects.update_or_create(
                        location_name=location_name,
                        defaults={
                            'latitude': coordinates['lat'],
                            'longitude': coordinates['lng'],
                            'formatted_address': coordinates['formatted_address']
                        }
                    )
                except Exception as e:
                    print(f"Cache save error: {e}")
            
            # Respect rate limit
            time.sleep(RATE_LIMIT_DELAY)
            
            return coordinates
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Geocoding error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected geocoding error: {e}")
        return None


def reverse_geocode(lat: float, lng: float) -> Optional[Dict]:
    """
    Reverse geocode GPS coordinates to address using FREE OpenStreetMap Nominatim API.
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        Dict with address information or None if not found
    """
    try:
        url = f"{NOMINATIM_BASE_URL}/reverse"
        params = {
            'lat': lat,
            'lon': lng,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': USER_AGENT
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data:
            address = data.get('address', {})
            return {
                'address': data.get('display_name', ''),
                'city': address.get('city', address.get('town', address.get('village', ''))),
                'state': address.get('state', ''),
                'country': address.get('country', ''),
                'zip_code': address.get('postcode', '')
            }
        
        # Respect rate limit
        time.sleep(RATE_LIMIT_DELAY)
        
        return None
        
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return None


def batch_geocode(locations: List[str], use_cache: bool = True) -> List[Dict]:
    """
    Geocode multiple locations with rate limiting.
    
    Args:
        locations: List of location names
        use_cache: Whether to use database cache
    
    Returns:
        List of results with 'location', 'coordinates', 'status'
    """
    results = []
    
    for location in locations:
        result = {
            'location': location,
            'coordinates': None,
            'status': 'not_found'
        }
        
        coords = geocode_location(location, use_cache=use_cache)
        if coords:
            result['coordinates'] = coords
            result['status'] = 'found'
        
        results.append(result)
    
    return results


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float, unit: str = 'miles') -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula.
    
    Args:
        lat1, lng1: First coordinate
        lat2, lng2: Second coordinate
        unit: 'miles' or 'kilometers' (default: 'miles')
    
    Returns:
        Distance in specified unit (rounded to 1 decimal place)
    """
    # Earth's radius
    R = 3959 if unit == 'miles' else 6371  # miles or kilometers
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return round(distance, 1)


def calculate_route_stats(duty_statuses: List[Dict], unit: str = 'miles') -> Dict:
    """
    Calculate route statistics from duty statuses with GPS coordinates.
    
    Implements corrected logic: Lines drawn FROM last known location (any status)
    TO driving destination.
    
    Args:
        duty_statuses: List of duty status dictionaries with coordinates
        unit: Distance unit ('miles' or 'kilometers')
    
    Returns:
        Dictionary with route statistics including driving segments and total distance
    """
    stats = {
        'totalDrivingDistance': 0.0,
        'totalLocations': 0,
        'drivingLocations': 0,
        'onDutyLocations': 0,
        'offDutyLocations': 0,
        'sleeperLocations': 0,
        'drivingSegments': []
    }
    
    last_known_coord = None
    last_known_status = None
    
    for status in duty_statuses:
        coordinates = status.get('coordinates')
        
        if coordinates and 'lat' in coordinates and 'lng' in coordinates:
            stats['totalLocations'] += 1
            
            # Count by status type
            status_type = status.get('status', '').lower()
            if status_type == 'driving':
                stats['drivingLocations'] += 1
                
                # Calculate distance FROM last known location TO this driving location
                if last_known_coord:
                    distance = calculate_distance(
                        last_known_coord['lat'],
                        last_known_coord['lng'],
                        coordinates['lat'],
                        coordinates['lng'],
                        unit=unit
                    )
                    
                    stats['totalDrivingDistance'] += distance
                    stats['drivingSegments'].append({
                        'start': last_known_coord,
                        'startStatus': last_known_status,
                        'end': coordinates,
                        'endStatus': 'driving',
                        'distance': distance
                    })
            elif status_type == 'on-duty':
                stats['onDutyLocations'] += 1
            elif status_type == 'off-duty':
                stats['offDutyLocations'] += 1
            elif status_type == 'sleeper':
                stats['sleeperLocations'] += 1
            
            # Update last known location (for ANY status type)
            last_known_coord = coordinates
            last_known_status = status_type
    
    stats['totalDrivingDistance'] = round(stats['totalDrivingDistance'], 1)
    
    return stats


def parse_coordinates(input_string: str) -> Optional[Dict]:
    """
    Parse coordinate string (e.g., "34.0522, -118.2437") into lat/lng dict.
    
    Args:
        input_string: String containing coordinates
    
    Returns:
        Dict with 'lat' and 'lng' or None if invalid
    """
    try:
        parts = input_string.split(',')
        if len(parts) == 2:
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            
            # Validate ranges
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        return None
    except (ValueError, AttributeError):
        return None


def get_coordinates_from_input(input_string: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Get coordinates from user input (either name or coordinates).
    
    Args:
        input_string: Location name or coordinate string
        use_cache: Whether to use cache for geocoding
    
    Returns:
        Dict with 'lat', 'lng', and optionally 'formatted_address'
    """
    if not input_string or not input_string.strip():
        return None
    
    # Try to parse as coordinates first
    coords = parse_coordinates(input_string)
    if coords:
        return coords
    
    # If not coordinates, try geocoding the location name
    return geocode_location(input_string, use_cache=use_cache)

