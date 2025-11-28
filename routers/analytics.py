from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from database import get_db
from routers.dependency import get_current_user
import models
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/date-range")
def get_available_date_range(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the date range of available assay data.
    Returns the oldest and newest assay dates.
    """
    query = db.query(
        func.min(models.AssayResult.created).label('oldest'),
        func.max(models.AssayResult.created).label('newest')
    ).filter(models.AssayResult.finalresult != 0)

    # Role-based filtering
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != -2
        )

    result = query.first()

    if not result.oldest or not result.newest:
        # No data available
        now = datetime.now()
        return {
            "oldest": now.strftime("%Y-%m-%d"),
            "newest": now.strftime("%Y-%m-%d")
        }

    return {
        "oldest": result.oldest.strftime("%Y-%m-%d"),
        "newest": result.newest.strftime("%Y-%m-%d")
    }


@router.get("/dashboard")
def get_dashboard_metrics(
    period: str = "month",  # week, month, year
    offset: int = 0,  # 0 = current, -1 = previous, 1 = next
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard metrics for the specified period.
    - period: "week", "month", or "year"
    - offset: 0 for current period, -1 for previous, 1 for next, etc.
    - Admin/Boss/Worker: See all results
    - Customers: Only see their own results
    """
    # Calculate date range based on period and offset
    now = datetime.now()

    if period == "week":
        # Week starts on Monday (0) and ends on Sunday (6)
        weekday = now.weekday()
        start_of_current_week = now - timedelta(days=weekday)
        start_of_current_week = start_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)

        date_from_obj = start_of_current_week + timedelta(weeks=offset)
        date_to_obj = date_from_obj + timedelta(days=7)

    elif period == "month":
        # Get first day of the current month, then apply offset
        if offset == 0:
            date_from_obj = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Calculate the target month
            target_month = now.month + offset
            target_year = now.year

            while target_month < 1:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1

            date_from_obj = datetime(target_year, target_month, 1)

        # Get first day of next month
        if date_from_obj.month == 12:
            date_to_obj = datetime(date_from_obj.year + 1, 1, 1)
        else:
            date_to_obj = datetime(date_from_obj.year, date_from_obj.month + 1, 1)

    elif period == "year":
        target_year = now.year + offset
        date_from_obj = datetime(target_year, 1, 1)
        date_to_obj = datetime(target_year + 1, 1, 1)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use 'week', 'month', or 'year'"
        )

    query = db.query(models.AssayResult).filter(
        models.AssayResult.finalresult != 0,
        models.AssayResult.created >= date_from_obj,
        models.AssayResult.created < date_to_obj
    )

    # Role-based filtering
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != -2
        )

    # Get metrics
    total_assays = query.count()

    # Get unique customers - use a separate query with func.count(func.distinct())
    if current_user.role == 'customer':
        total_customers = 1
    else:
        customer_count_query = db.query(func.count(func.distinct(models.AssayResult.customer))).filter(
            models.AssayResult.finalresult != 0,
            models.AssayResult.created >= date_from_obj,
            models.AssayResult.created < date_to_obj
        )
        total_customers = customer_count_query.scalar() or 0

    return {
        "total_assays": total_assays,
        "total_customers": total_customers,
        "date_range": {
            "from": date_from_obj.strftime("%Y-%m-%d"),
            "to": (date_to_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        }
    }


@router.get("/efficiency")
def get_efficiency_metrics(
    period: str = "month",  # week, month, year
    offset: int = 0,  # 0 = current, -1 = previous, 1 = next
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get efficiency metrics for the specified period.
    - period: "week", "month", or "year"
    - offset: 0 for current period, -1 for previous, 1 for next, etc.
    - Admin/Boss/Worker: See all results
    - Customers: Only see their own results
    """
    # Calculate date range based on period and offset
    now = datetime.now()

    if period == "week":
        weekday = now.weekday()
        start_of_current_week = now - timedelta(days=weekday)
        start_of_current_week = start_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)

        date_from_obj = start_of_current_week + timedelta(weeks=offset)
        date_to_obj = date_from_obj + timedelta(days=7)

    elif period == "month":
        if offset == 0:
            date_from_obj = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            target_month = now.month + offset
            target_year = now.year

            while target_month < 1:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1

            date_from_obj = datetime(target_year, target_month, 1)

        if date_from_obj.month == 12:
            date_to_obj = datetime(date_from_obj.year + 1, 1, 1)
        else:
            date_to_obj = datetime(date_from_obj.year, date_from_obj.month + 1, 1)

    elif period == "year":
        target_year = now.year + offset
        date_from_obj = datetime(target_year, 1, 1)
        date_to_obj = datetime(target_year + 1, 1, 1)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use 'week', 'month', or 'year'"
        )

    query = db.query(models.AssayResult).filter(
        models.AssayResult.finalresult != 0,
        models.AssayResult.created >= date_from_obj,
        models.AssayResult.created < date_to_obj
    )

    # Role-based filtering
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != -2
        )

    results = query.all()
    total_processed = len(results)

    if total_processed == 0:
        return {
            "average_processing_time": 0,
            "average_sample_weight": 0,
            "average_return_weight": 0,
            "average_loss_percentage": 0,
            "total_processed": 0
        }

    # Calculate processing time (difference between created and returndate)
    processing_times = []
    for r in results:
        if r.returndate and r.created:
            delta = r.returndate - r.created
            processing_times.append(delta.total_seconds() / 3600)  # Convert to hours

    average_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

    # Calculate weights
    sample_weights = [r.sampleweight for r in results if r.sampleweight]
    return_weights = [r.samplereturn for r in results if r.samplereturn]

    average_sample_weight = sum(sample_weights) / len(sample_weights) if sample_weights else 0
    average_return_weight = sum(return_weights) / len(return_weights) if return_weights else 0

    # Calculate loss percentage
    loss_percentages = [r.loss for r in results if r.loss is not None]
    average_loss_percentage = sum(loss_percentages) / len(loss_percentages) if loss_percentages else 0

    return {
        "average_processing_time": average_processing_time,
        "average_sample_weight": average_sample_weight,
        "average_return_weight": average_return_weight,
        "average_loss_percentage": average_loss_percentage,
        "total_processed": total_processed
    }


@router.get("/trend")
def get_trend_data(
    period: str = "month",  # week, month, year
    offset: int = 0,  # 0 = current, -1 = previous, 1 = next
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get trend data showing total assays processed over time for the specified period.
    - For week: Returns daily data (7 days)
    - For month: Returns daily data (~30 days)
    - For year: Returns monthly data (12 months)
    """
    now = datetime.now()

    if period == "week":
        weekday = now.weekday()
        start_of_current_week = now - timedelta(days=weekday)
        start_of_current_week = start_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)

        date_from_obj = start_of_current_week + timedelta(weeks=offset)
        date_to_obj = date_from_obj + timedelta(days=7)

        # Generate daily data for the week
        trend_data = []
        for i in range(7):
            day_start = date_from_obj + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            query = db.query(func.count(models.AssayResult.id)).filter(
                models.AssayResult.finalresult != 0,
                models.AssayResult.created >= day_start,
                models.AssayResult.created < day_end
            )

            if current_user.role == 'customer':
                query = query.filter(
                    models.AssayResult.customer == current_user.id,
                    models.AssayResult.finalresult != -2
                )

            count = query.scalar() or 0
            trend_data.append({
                "label": day_start.strftime("%a"),  # Mon, Tue, etc.
                "value": count
            })

    elif period == "month":
        if offset == 0:
            date_from_obj = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            target_month = now.month + offset
            target_year = now.year

            while target_month < 1:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1

            date_from_obj = datetime(target_year, target_month, 1)

        if date_from_obj.month == 12:
            date_to_obj = datetime(date_from_obj.year + 1, 1, 1)
        else:
            date_to_obj = datetime(date_from_obj.year, date_from_obj.month + 1, 1)

        # Generate daily data for the month
        days_in_month = (date_to_obj - date_from_obj).days
        trend_data = []

        for i in range(days_in_month):
            day_start = date_from_obj + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            query = db.query(func.count(models.AssayResult.id)).filter(
                models.AssayResult.finalresult != 0,
                models.AssayResult.created >= day_start,
                models.AssayResult.created < day_end
            )

            if current_user.role == 'customer':
                query = query.filter(
                    models.AssayResult.customer == current_user.id,
                    models.AssayResult.finalresult != -2
                )

            count = query.scalar() or 0
            trend_data.append({
                "label": str(day_start.day),
                "value": count
            })

    elif period == "year":
        target_year = now.year + offset
        date_from_obj = datetime(target_year, 1, 1)
        date_to_obj = datetime(target_year + 1, 1, 1)

        # Generate monthly data for the year
        trend_data = []
        for month in range(1, 13):
            month_start = datetime(target_year, month, 1)
            if month == 12:
                month_end = datetime(target_year + 1, 1, 1)
            else:
                month_end = datetime(target_year, month + 1, 1)

            query = db.query(func.count(models.AssayResult.id)).filter(
                models.AssayResult.finalresult != 0,
                models.AssayResult.created >= month_start,
                models.AssayResult.created < month_end
            )

            if current_user.role == 'customer':
                query = query.filter(
                    models.AssayResult.customer == current_user.id,
                    models.AssayResult.finalresult != -2
                )

            count = query.scalar() or 0
            trend_data.append({
                "label": month_start.strftime("%b"),  # Jan, Feb, etc.
                "value": count
            })
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Use 'week', 'month', or 'year'"
        )

    return trend_data


@router.get("/customers/top")
def get_top_customers(
    limit: int = 10,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top customers by number of assays.
    Admin/Boss/Worker only - customers will see empty list.
    """
    if current_user.role == 'customer':
        return []

    # Query to get top customers with their statistics
    top_customers = (
        db.query(
            models.User.name.label('customer_name'),
            func.count(models.AssayResult.id).label('total_assays'),
            func.sum(models.AssayResult.sampleweight).label('total_weight'),
            func.avg(models.AssayResult.finalresult).label('average_fineness')
        )
        .join(models.AssayResult, models.User.id == models.AssayResult.customer)
        .filter(
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.finalresult > 0
        )
        .group_by(models.User.id, models.User.name)
        .order_by(func.count(models.AssayResult.id).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "customer_name": customer.customer_name,
            "total_assays": customer.total_assays,
            "total_weight": float(customer.total_weight or 0),
            "average_fineness": float(customer.average_fineness or 0)
        }
        for customer in top_customers
    ]


@router.get("/trends/daily")
def get_daily_trends(
    days: int = 30,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily trends for the specified number of days.
    - Admin/Boss/Worker: See all results
    - Customers: Only see their own results
    """
    date_from = datetime.now() - timedelta(days=days)

    query = db.query(
        func.date(models.AssayResult.created).label('date'),
        func.count(models.AssayResult.id).label('total_assays'),
        func.sum(models.AssayResult.sampleweight).label('total_weight'),
        func.avg(models.AssayResult.finalresult).label('average_fineness')
    ).filter(
        models.AssayResult.created >= date_from,
        models.AssayResult.finalresult != 0
    )

    # Role-based filtering
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != -2
        )

    trends = query.group_by(func.date(models.AssayResult.created)).order_by(func.date(models.AssayResult.created)).all()

    return [
        {
            "date": trend.date.strftime("%Y-%m-%d"),
            "total_assays": trend.total_assays,
            "total_weight": float(trend.total_weight or 0),
            "average_fineness": float(trend.average_fineness or 0)
        }
        for trend in trends
    ]


@router.get("/trends/monthly")
def get_monthly_trends(
    months: int = 12,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get monthly trends for the specified number of months.
    - Admin/Boss/Worker: See all results
    - Customers: Only see their own results
    """
    date_from = datetime.now() - timedelta(days=months * 30)

    query = db.query(
        extract('year', models.AssayResult.created).label('year'),
        extract('month', models.AssayResult.created).label('month'),
        func.count(models.AssayResult.id).label('total_assays'),
        func.sum(models.AssayResult.sampleweight).label('total_weight'),
        func.count(func.distinct(models.AssayResult.customer)).label('total_customers'),
        func.avg(models.AssayResult.finalresult).label('average_fineness')
    ).filter(
        models.AssayResult.created >= date_from,
        models.AssayResult.finalresult != 0
    )

    # Role-based filtering
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != -2
        )

    trends = (
        query.group_by(
            extract('year', models.AssayResult.created),
            extract('month', models.AssayResult.created)
        )
        .order_by(
            extract('year', models.AssayResult.created),
            extract('month', models.AssayResult.created)
        )
        .all()
    )

    return [
        {
            "year": int(trend.year),
            "month": int(trend.month),
            "total_assays": trend.total_assays,
            "total_weight": float(trend.total_weight or 0),
            "total_customers": trend.total_customers if current_user.role != 'customer' else 1,
            "average_fineness": float(trend.average_fineness or 0)
        }
        for trend in trends
    ]


@router.get("/daily-report")
def get_daily_report(
    timeframe: str = "today",  # today, week, month, year
    offset: int = 0,  # 0 = current, -1 = previous period, -2 = 2 periods ago, etc.
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily report showing billing/coupon breakdown by area (BW and PG).
    Admin/Boss only - mimics the Python assayreport.py functionality.

    Parameters:
    - timeframe: today, week, month, year
    - offset: 0 for current period, -1 for previous, -2 for 2 periods ago, etc.

    Returns:
    - Date of the report
    - Period total assays
    - Month's total assays (with BW/PG breakdown)
    - BW area breakdown (billing/coupon matrix)
    - PG area breakdown (billing/coupon matrix)
    """
    # Only admin and boss can access this report
    if current_user.role not in ['admin', 'boss']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and boss can access daily reports"
        )

    # Calculate date ranges based on timeframe and offset
    now = datetime.now()

    if timeframe == "today":
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = period_start + timedelta(days=offset)
        period_end = period_start + timedelta(days=1)
    elif timeframe == "week":
        # Start of week (Monday)
        days_since_monday = now.weekday()
        period_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = period_start + timedelta(weeks=offset)
        period_end = period_start + timedelta(days=7)
    elif timeframe == "month":
        # Start of month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Apply offset by adding/subtracting months
        target_month = period_start.month + offset
        target_year = period_start.year

        # Handle year wrapping
        while target_month < 1:
            target_month += 12
            target_year -= 1
        while target_month > 12:
            target_month -= 12
            target_year += 1

        period_start = datetime(target_year, target_month, 1, 0, 0, 0, 0)

        # Start of next month
        if period_start.month == 12:
            period_end = datetime(period_start.year + 1, 1, 1)
        else:
            period_end = datetime(period_start.year, period_start.month + 1, 1)
    elif timeframe == "year":
        # Start of year
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_start = datetime(period_start.year + offset, 1, 1, 0, 0, 0, 0)
        # Start of next year
        period_end = datetime(period_start.year + 1, 1, 1)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timeframe. Use: today, week, month, or year"
        )

    # Calculate date ranges for period
    period_data_start = period_start
    period_data_end = period_end

    # For "month total", always use current month regardless of timeframe
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # First day of next month
    if month_start.month == 12:
        month_end = datetime(month_start.year + 1, 1, 1)
    else:
        month_end = datetime(month_start.year, month_start.month + 1, 1)

    def calculate_area_breakdown(area_code: str, date_start: datetime, date_end: datetime):
        """Calculate the billing/coupon breakdown for a specific area."""
        # Query assay results joined with user data
        results = (
            db.query(models.User.billing, models.User.coupon)
            .join(models.AssayResult, models.User.id == models.AssayResult.customer)
            .filter(
                models.AssayResult.created >= date_start,
                models.AssayResult.created < date_end,
                models.User.area == area_code
            )
            .all()
        )

        # Initialize counters
        billing_coupon = 0
        billing_no_coupon = 0
        no_billing_coupon = 0
        no_billing_no_coupon = 0

        # Count each combination
        for billing, coupon in results:
            if billing and coupon:
                billing_coupon += 1
            elif billing and not coupon:
                billing_no_coupon += 1
            elif not billing and coupon:
                no_billing_coupon += 1
            else:  # not billing and not coupon
                no_billing_no_coupon += 1

        # Calculate totals
        billing_total = billing_coupon + billing_no_coupon
        no_billing_total = no_billing_coupon + no_billing_no_coupon
        coupon_total = billing_coupon + no_billing_coupon
        no_coupon_total = billing_no_coupon + no_billing_no_coupon
        total = len(results)

        return {
            "billing_coupon": billing_coupon,
            "billing_no_coupon": billing_no_coupon,
            "no_billing_coupon": no_billing_coupon,
            "no_billing_no_coupon": no_billing_no_coupon,
            "billing_total": billing_total,
            "no_billing_total": no_billing_total,
            "coupon_total": coupon_total,
            "no_coupon_total": no_coupon_total,
            "total": total
        }

    # Get period data for BW and PG (based on selected timeframe)
    bw_data_period = calculate_area_breakdown("BW", period_data_start, period_data_end)
    pg_data_period = calculate_area_breakdown("PG", period_data_start, period_data_end)

    # Get month's data for BW and PG (always current month for reference)
    bw_data_month = calculate_area_breakdown("BW", month_start, month_end)
    pg_data_month = calculate_area_breakdown("PG", month_start, month_end)

    # Calculate totals
    period_total = bw_data_period["total"] + pg_data_period["total"]
    month_total = bw_data_month["total"] + pg_data_month["total"]
    bw_month_total = bw_data_month["total"]
    pg_month_total = pg_data_month["total"]

    return {
        "date": period_start.strftime("%Y-%m-%d"),
        "today_total": period_total,  # Actually the period total based on timeframe
        "month_total": month_total,
        "bw_data": bw_data_period,  # Data for the selected period
        "pg_data": pg_data_period,  # Data for the selected period
        "bw_month_total": bw_month_total,
        "pg_month_total": pg_month_total
    }
