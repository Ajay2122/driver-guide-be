"""
Statistics and analytics views for the Driver Log System
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Sum, Avg, Count
from django.utils.dateparse import parse_date

from ..models import Driver, DailyLog
from ..mixins import StandardResponseMixin
from ..exceptions import DriverNotFound
from ..services import check_hos_compliance
from ..serializers import DailyLogListSerializer


@api_view(['GET'])
def get_driver_stats(request, driver_id):
    """
    Get statistics for a specific driver
    GET /api/v1/drivers/{driver_id}/stats
    """
    try:
        driver = Driver.objects.get(pk=driver_id)
    except Driver.DoesNotExist:
        raise DriverNotFound()
    
    # Get query parameters
    start_date = request.query_params.get('startDate')
    end_date = request.query_params.get('endDate')
    period = request.query_params.get('period', '30days')
    
    # Calculate date range based on period
    if period == '7days':
        default_start = timezone.now().date() - timedelta(days=7)
    elif period == '90days':
        default_start = timezone.now().date() - timedelta(days=90)
    else:  # 30days default
        default_start = timezone.now().date() - timedelta(days=30)
    
    start_date = parse_date(start_date) if start_date else default_start
    end_date = parse_date(end_date) if end_date else timezone.now().date()
    
    # Get logs in date range
    logs = DailyLog.objects.filter(
        driver=driver,
        date__gte=start_date,
        date__lte=end_date
    )
    
    # Calculate statistics
    total_logs = logs.count()
    
    # Aggregate hours and miles
    aggregates = logs.aggregate(
        total_driving_hours=Sum('hours_driving'),
        total_miles=Sum('total_miles'),
        avg_driving_hours=Avg('hours_driving')
    )
    # Calculate average miles separately
    total_miles_sum = aggregates['total_miles'] or 0
    avg_miles = float(total_miles_sum) / total_logs if total_logs > 0 else 0
    
    # Compliance statistics
    compliant_logs = logs.filter(is_compliant=True).count()
    violation_logs = logs.filter(is_compliant=False).count()
    compliance_rate = (compliant_logs / total_logs * 100) if total_logs > 0 else 0
    
    # Get violations
    violations_list = []
    for log in logs.filter(is_compliant=False):
        if log.violations:
            for violation in log.violations:
                violations_list.append({
                    'date': str(log.date),
                    'logId': str(log.id),
                    'violationType': violation.get('rule', ''),
                    'description': violation.get('description', '')
                })
    
    # Weekly breakdown
    weekly_breakdown = []
    current_date = start_date
    week_num = 1
    
    while current_date <= end_date:
        week_end = min(current_date + timedelta(days=6), end_date)
        week_logs = logs.filter(date__gte=current_date, date__lte=week_end)
        
        # Calculate total hours manually since F() expressions can be complex
        total_hours = sum([float(log.hours_driving) + float(log.hours_on_duty) for log in week_logs])
        week_agg = week_logs.aggregate(
            driving_hours=Sum('hours_driving'),
            total_miles=Sum('total_miles')
        )
        
        week_str = current_date.strftime('%Y-W%W')
        weekly_breakdown.append({
            'week': week_str,
            'totalHours': round(total_hours, 2),
            'drivingHours': float(week_agg['driving_hours'] or 0),
            'totalMiles': int(week_agg['total_miles'] or 0)
        })
        
        current_date = week_end + timedelta(days=1)
        week_num += 1
        
        if week_num > 20:  # Safety limit
            break
    
    response_data = {
        'driverId': str(driver.id),
        'period': {
            'startDate': str(start_date),
            'endDate': str(end_date)
        },
        'summary': {
            'totalLogs': total_logs,
            'totalDrivingHours': float(aggregates['total_driving_hours'] or 0),
            'totalMiles': int(aggregates['total_miles'] or 0),
            'averageDailyDriving': round(float(aggregates['avg_driving_hours'] or 0), 2),
            'averageDailyMiles': round(avg_miles, 2),
            'complianceRate': round(compliance_rate, 1)
        },
        'compliance': {
            'compliantDays': compliant_logs,
            'violationDays': violation_logs,
            'violations': violations_list[:10]  # Limit to 10 most recent
        },
        'weeklyBreakdown': weekly_breakdown
    }
    
    return Response({
        'status': 'success',
        'data': response_data,
        'message': 'Statistics fetched successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def compliance_check(request):
    """
    Check HOS compliance for given duty statuses
    POST /api/v1/logs/compliance-check
    """
    duty_statuses = request.data.get('dutyStatuses', [])
    
    if not duty_statuses or not isinstance(duty_statuses, list):
        return Response({
            'status': 'error',
            'message': 'dutyStatuses must be a non-empty array'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Use service to check compliance
    compliance_result = check_hos_compliance(duty_statuses)
    
    return Response({
        'status': 'success',
        'data': compliance_result,
        'message': 'Compliance check completed'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def dashboard_stats(request):
    """
    Get dashboard statistics across all drivers
    GET /api/v1/dashboard/stats
    """
    # Get query parameters
    start_date = request.query_params.get('startDate')
    end_date = request.query_params.get('endDate')
    
    if start_date:
        start_date = parse_date(start_date)
    else:
        start_date = timezone.now().date() - timedelta(days=30)
    
    if end_date:
        end_date = parse_date(end_date)
    else:
        end_date = timezone.now().date()
    
    # Get logs in date range
    logs = DailyLog.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    
    # Overall statistics
    total_drivers = Driver.objects.count()
    total_logs = logs.count()
    compliant_logs = logs.filter(is_compliant=True).count()
    violation_logs = logs.filter(is_compliant=False).count()
    compliance_rate = (compliant_logs / total_logs * 100) if total_logs > 0 else 0
    
    # Recent activity
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    logs_today = DailyLog.objects.filter(date=today).count()
    logs_this_week = DailyLog.objects.filter(date__gte=week_start).count()
    logs_this_month = DailyLog.objects.filter(date__gte=month_start).count()
    
    # Top violations
    violation_types = {}
    for log in logs.filter(is_compliant=False):
        if log.violations:
            for violation in log.violations:
                violation_type = violation.get('rule', 'Unknown')
                violation_types[violation_type] = violation_types.get(violation_type, 0) + 1
    
    top_violations = [
        {'type': k, 'count': v}
        for k, v in sorted(violation_types.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    response_data = {
        'totalDrivers': total_drivers,
        'totalLogs': total_logs,
        'compliantLogs': compliant_logs,
        'violationLogs': violation_logs,
        'complianceRate': round(compliance_rate, 1),
        'recentActivity': {
            'logsToday': logs_today,
            'logsThisWeek': logs_this_week,
            'logsThisMonth': logs_this_month
        },
        'topViolations': top_violations
    }
    
    return Response({
        'status': 'success',
        'data': response_data,
        'message': 'Dashboard statistics fetched successfully'
    }, status=status.HTTP_200_OK)

