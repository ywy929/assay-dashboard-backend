"""
Date calculation utilities for analytics.
"""
from datetime import datetime, timedelta
from fastapi import HTTPException, status


def calculate_period_range(period: str, offset: int = 0) -> tuple[datetime, datetime]:
    """
    Calculate date range based on period and offset.

    Args:
        period: "week", "month", or "year"
        offset: 0 for current period, -1 for previous, 1 for next, etc.

    Returns:
        Tuple of (date_from, date_to) datetime objects

    Raises:
        HTTPException if invalid period provided
    """
    now = datetime.now()

    if period == "week":
        weekday = now.weekday()
        start_of_current_week = now - timedelta(days=weekday)
        start_of_current_week = start_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)

        date_from = start_of_current_week + timedelta(weeks=offset)
        date_to = date_from + timedelta(days=7)

    elif period == "month":
        if offset == 0:
            date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            target_month = now.month + offset
            target_year = now.year

            while target_month < 1:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1

            date_from = datetime(target_year, target_month, 1)

        if date_from.month == 12:
            date_to = datetime(date_from.year + 1, 1, 1)
        else:
            date_to = datetime(date_from.year, date_from.month + 1, 1)

    elif period == "year":
        target_year = now.year + offset
        date_from = datetime(target_year, 1, 1)
        date_to = datetime(target_year + 1, 1, 1)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use 'week', 'month', or 'year'"
        )

    return date_from, date_to
