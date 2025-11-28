"""
Schedules utilities
"""
from datetime import datetime, timedelta


def get_date_range(start_date, end_date):
    """
    Get list of dates between start and end
    """
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates
