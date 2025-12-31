"""
HOS (Hours of Service) compliance validation services
Implements FMCSA regulations for driver log compliance
"""
from decimal import Decimal
from typing import List, Dict, Tuple


def calculate_duration(start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> float:
    """
    Calculate duration in hours between two times.
    Handles midnight crossing.
    
    Args:
        start_hour: Start hour (0-23)
        start_minute: Start minute (0-59)
        end_hour: End hour (0-24, where 24 means midnight of next day)
        end_minute: End minute (0-59)
    
    Returns:
        Duration in hours as float (rounded to 2 decimals)
    """
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute
    
    # Handle crossing midnight
    if end_minutes < start_minutes:
        end_minutes += 24 * 60
    
    duration_minutes = end_minutes - start_minutes
    duration_hours = duration_minutes / 60.0
    
    return round(duration_hours, 2)


def calculate_hours_from_duty_statuses(duty_statuses: List[Dict]) -> Dict[str, float]:
    """
    Calculate total hours for each duty status type from duty status array.
    
    Args:
        duty_statuses: List of duty status dictionaries
    
    Returns:
        Dictionary with hours for each status type
    """
    hours = {
        'offDuty': 0.0,
        'sleeper': 0.0,
        'driving': 0.0,
        'onDuty': 0.0,
        'total': 0.0
    }
    
    for status in duty_statuses:
        status_type = status.get('status', '').lower()
        start_hour = status.get('startHour', 0)
        start_minute = status.get('startMinute', 0)
        end_hour = status.get('endHour', 24)
        end_minute = status.get('endMinute', 0)
        
        duration = calculate_duration(start_hour, start_minute, end_hour, end_minute)
        
        if status_type == 'off-duty':
            hours['offDuty'] += duration
        elif status_type == 'sleeper':
            hours['sleeper'] += duration
        elif status_type == 'driving':
            hours['driving'] += duration
        elif status_type == 'on-duty':
            hours['onDuty'] += duration
        
        hours['total'] += duration
    
    # Round all values
    for key in hours:
        hours[key] = round(hours[key], 2)
    
    return hours


def validate_11_hour_driving_limit(duty_statuses: List[Dict]) -> Tuple[bool, List[Dict]]:
    """
    Validate 11-hour driving limit rule.
    Cannot drive beyond 11 hours after 10 consecutive hours off duty.
    
    Args:
        duty_statuses: List of duty status dictionaries
    
    Returns:
        Tuple of (is_valid, violations_list)
    """
    hours = calculate_hours_from_duty_statuses(duty_statuses)
    violations = []
    
    if hours['driving'] > 11.0:
        violations.append({
            'rule': '11_HOUR_DRIVING_LIMIT',
            'description': f"Driving time ({hours['driving']}h) exceeds 11-hour limit",
            'severity': 'critical'
        })
        return False, violations
    
    return True, []


def validate_14_hour_window(duty_statuses: List[Dict]) -> Tuple[bool, List[Dict]]:
    """
    Validate 14-hour driving window rule.
    Cannot drive beyond the 14th consecutive hour after coming on duty.
    
    Args:
        duty_statuses: List of duty status dictionaries
    
    Returns:
        Tuple of (is_valid, violations_list)
    """
    hours = calculate_hours_from_duty_statuses(duty_statuses)
    violations = []
    
    # Calculate on-duty time (driving + on-duty)
    on_duty_hours = hours['driving'] + hours['onDuty']
    
    if on_duty_hours > 14.0:
        violations.append({
            'rule': '14_HOUR_WINDOW',
            'description': f"On-duty time ({on_duty_hours}h) exceeds 14-hour window",
            'severity': 'critical'
        })
        return False, violations
    
    return True, []


def validate_10_hour_rest(duty_statuses: List[Dict]) -> Tuple[bool, List[Dict]]:
    """
    Validate 10-hour rest requirement.
    Must have at least 10 hours off duty (off-duty + sleeper).
    
    Args:
        duty_statuses: List of duty status dictionaries
    
    Returns:
        Tuple of (is_valid, violations_list)
    """
    hours = calculate_hours_from_duty_statuses(duty_statuses)
    violations = []
    
    rest_hours = hours['offDuty'] + hours['sleeper']
    
    if rest_hours < 10.0:
        violations.append({
            'rule': '10_HOUR_REST',
            'description': f"Rest time ({rest_hours}h) is less than required 10 hours",
            'severity': 'critical'
        })
        return False, violations
    
    return True, []


def check_hos_compliance(duty_statuses: List[Dict]) -> Dict:
    """
    Main HOS compliance check function.
    Validates all FMCSA rules and returns compliance status.
    
    Args:
        duty_statuses: List of duty status dictionaries
    
    Returns:
        Dictionary with compliance status, hours, violations, and warnings
    """
    hours = calculate_hours_from_duty_statuses(duty_statuses)
    all_violations = []
    warnings = []
    
    # Validate 11-hour driving limit
    is_valid_11hr, violations_11hr = validate_11_hour_driving_limit(duty_statuses)
    all_violations.extend(violations_11hr)
    
    # Validate 14-hour window
    is_valid_14hr, violations_14hr = validate_14_hour_window(duty_statuses)
    all_violations.extend(violations_14hr)
    
    # Validate 10-hour rest
    is_valid_10hr, violations_10hr = validate_10_hour_rest(duty_statuses)
    all_violations.extend(violations_10hr)
    
    # Check if total hours equals 24
    if hours['total'] != 24.0:
        warnings.append({
            'type': 'TOTAL_HOURS_MISMATCH',
            'description': f"Total hours ({hours['total']}h) should equal 24 hours"
        })
    
    is_compliant = len(all_violations) == 0
    
    return {
        'isCompliant': is_compliant,
        'hours': hours,
        'violations': all_violations,
        'warnings': warnings
    }

