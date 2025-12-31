from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from routers.dependency import get_current_user, get_admin_user
import models, schemas
from typing import List, Optional
from datetime import datetime, timedelta
from routers.notifications import send_push_notification
from utils import build_assay_response

router = APIRouter()


@router.get("/my-results")
def get_my_assay_results(
    limit: int = 20,
    offset: int = 0,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get assay results with pagination.
    - Regular users (customers): Only see their own results with finalresult > 0
    - Admin/Boss/Worker: See all results
    """
    query = db.query(models.AssayResult)

    # If user is a regular customer, filter by their ID and only show results with finalresult
    # Admin, boss, and worker can see all results
    # Customers should not see:
    # - Results with finalresult = 0 (no result yet)
    # - Results with finalresult = -2 (Redo status)
    # - Results with ready = false (manual hide)
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True
        )

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    results = (
        query.order_by(models.AssayResult.created.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Build response items
    items = [build_assay_response(result) for result in results]

    # Return paginated response
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }


@router.get("/my-results/{result_id}", response_model=schemas.AssayResultResponse)
def get_my_assay_result_by_id(
    result_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific assay result by ID.
    - Regular users (customers): Only see their own results with finalresult > 0
    - Admin/Boss/Worker: Can view any result
    """
    query = db.query(models.AssayResult).filter(models.AssayResult.id == result_id)

    # If user is a regular customer, filter by their ID and only show results with finalresult
    # Customers should not see results with finalresult = 0 or -2 (Redo) or ready = false
    if current_user.role == 'customer':
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True
        )

    result = query.first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay result not found or you don't have permission to view it"
        )

    return build_assay_response(result)


@router.get("/search")
def search_assay_results(
    itemcode: Optional[str] = None,
    customer_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search assay results with various filters.
    - Customers: Only see their own results (customer_name filter ignored)
    - Admin/Boss/Worker: Can search all results with customer_name filter
    """
    query = db.query(models.AssayResult)

    # Role-based filtering
    if current_user.role == 'customer':
        # Customers can only see their own results
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True
        )

    # Apply search filters - only if values are provided and not empty
    if itemcode and itemcode.strip():
        query = query.filter(models.AssayResult.itemcode.ilike(f"%{itemcode.strip()}%"))

    # Customer name filter only for admin/boss/worker
    if customer_name and customer_name.strip() and current_user.role in ['admin', 'boss', 'worker']:
        # Join with User table to filter by customer name
        query = query.join(models.User, models.AssayResult.customer == models.User.id)
        query = query.filter(models.User.name.ilike(f"%{customer_name.strip()}%"))

    # Date range filters
    if date_from and date_from.strip():
        try:
            date_from_obj = datetime.strptime(date_from.strip(), "%Y-%m-%d")
            query = query.filter(models.AssayResult.created >= date_from_obj)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use YYYY-MM-DD"
            )

    if date_to and date_to.strip():
        try:
            date_to_obj = datetime.strptime(date_to.strip(), "%Y-%m-%d")
            # Add one day to include the entire date_to day
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(models.AssayResult.created < date_to_obj)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use YYYY-MM-DD"
            )

    # Get total count before pagination
    total = query.count()

    # Apply pagination and ordering
    results = (
        query.order_by(models.AssayResult.created.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Build response items
    items = [build_assay_response(result) for result in results]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }


@router.get("/all", response_model=List[schemas.AssayResultResponse])
def get_all_assay_results(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    """
    Get all assay results from all users (Admin only)
    """
    results = db.query(models.AssayResult).order_by(models.AssayResult.created.desc()).all()
    return results


@router.get("/user/{user_id}", response_model=List[schemas.AssayResultResponse])
def get_user_assay_results(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    """
    Get all assay results for a specific user (Admin only)
    """
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    results = (
        db.query(models.AssayResult)
        .filter(models.AssayResult.customer == user_id)
        .order_by(models.AssayResult.created.desc())
        .all()
    )
    return results


@router.put("/{assay_id}/mark-ready")
def mark_assay_ready(
    assay_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle an assay's ready status for customer pickup/viewing.
    Only admin, worker, and boss can change assay ready status.
    When marking as ready, this will create a notification for the customer and send a push notification.
    """
    # Check permissions
    if current_user.role not in ['admin', 'worker', 'boss']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin, worker, and boss can change assay ready status"
        )

    # Get the assay
    assay = db.query(models.AssayResult).filter(
        models.AssayResult.id == assay_id
    ).first()

    if not assay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay not found"
        )

    # Toggle ready status
    was_ready = assay.ready
    assay.ready = not assay.ready
    assay.modified = datetime.now()

    # Only notify customer when marking as ready (not when unmarking)
    if assay.ready and not was_ready:
        # Create notification for the customer
        notification = models.Notification(
            user_id=assay.customer,
            assay_id=assay.id,
            title="Assay Ready",
            message=f"Your assay {assay.itemcode} is ready for pickup",
            read=False,
            created=datetime.now()
        )
        db.add(notification)

        # Get customer's push tokens
        push_tokens = db.query(models.PushToken).filter(
            models.PushToken.user_id == assay.customer
        ).all()

        # Send push notifications
        for push_token in push_tokens:
            send_push_notification(
                expo_push_token=push_token.token,
                title="Assay Ready",
                body=f"Your assay {assay.itemcode} is ready for pickup",
                data={
                    "assay_id": assay.id,
                    "itemcode": assay.itemcode,
                    "formcode": assay.formcode
                }
            )

        db.commit()

        return {
            "message": "Assay marked as ready and customer notified",
            "assay_id": assay.id,
            "notifications_sent": len(push_tokens),
            "ready": True
        }
    else:
        # Just update the status without notification
        db.commit()

        return {
            "message": "Assay marked as not ready",
            "assay_id": assay.id,
            "ready": False
        }