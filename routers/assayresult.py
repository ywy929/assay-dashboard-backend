import os
import time
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from database import get_db
from routers.dependency import get_current_user, get_admin_user, get_staff_user
import models, schemas
from typing import List, Optional
from datetime import datetime, timedelta
from routers.notifications import send_push_notification, send_not_ready_notification
from utils import build_assay_response

router = APIRouter()


def not_deleted_filter():
    """Filter to exclude deleted records (handles NULL values as not deleted)"""
    return or_(models.AssayResult.deleted == False, models.AssayResult.deleted == None)


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
    query = db.query(models.AssayResult).filter(not_deleted_filter())

    # If user is a regular customer or test customer, filter by their ID and only show results with finalresult
    # Admin, boss, and worker can see all results
    # testworker can only see testcustomer data
    # Customers should not see:
    # - Results with finalresult = 0 (no result yet)
    # - Results with finalresult = -2 (Redo status)
    # - Results with ready = false (manual hide)
    if current_user.role in ['customer', 'testcustomer']:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True,
            models.AssayResult.created >= thirty_days_ago
        )
    elif current_user.role == 'testworker':
        # testworker can only see testcustomer data
        testcustomer_ids = db.query(models.User.id).filter(models.User.role == 'testcustomer').subquery()
        query = query.filter(models.AssayResult.customer.in_(testcustomer_ids))

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
    query = db.query(models.AssayResult).filter(
        models.AssayResult.id == result_id,
        not_deleted_filter()
    )

    # If user is a regular customer or test customer, filter by their ID and only show results with finalresult
    # Customers should not see results with finalresult = 0 or -2 (Redo) or ready = false
    # testworker can only see testcustomer data
    if current_user.role in ['customer', 'testcustomer']:
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True
        )
    elif current_user.role == 'testworker':
        # testworker can only see testcustomer data
        testcustomer_ids = db.query(models.User.id).filter(models.User.role == 'testcustomer').subquery()
        query = query.filter(models.AssayResult.customer.in_(testcustomer_ids))

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
    fineness_min: Optional[float] = None,
    fineness_max: Optional[float] = None,
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
    query = db.query(models.AssayResult).filter(not_deleted_filter())

    # Role-based filtering
    if current_user.role in ['customer', 'testcustomer']:
        # Customers can only see their own results from the past 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        query = query.filter(
            models.AssayResult.customer == current_user.id,
            models.AssayResult.finalresult != 0,
            models.AssayResult.finalresult != -2,
            models.AssayResult.ready == True,
            models.AssayResult.created >= thirty_days_ago
        )
    elif current_user.role == 'testworker':
        # testworker can only see testcustomer data
        testcustomer_ids = db.query(models.User.id).filter(models.User.role == 'testcustomer').subquery()
        query = query.filter(models.AssayResult.customer.in_(testcustomer_ids))

    # Apply search filters - only if values are provided and not empty
    if itemcode and itemcode.strip():
        query = query.filter(models.AssayResult.itemcode.ilike(f"%{itemcode.strip()}%"))

    # Customer name filter only for admin/boss/worker/testworker
    if customer_name and customer_name.strip() and current_user.role in ['admin', 'boss', 'worker', 'testworker']:
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

    # Fineness range filter (only for admin/boss/worker/testworker)
    if fineness_min is not None and current_user.role in ['admin', 'boss', 'worker', 'testworker']:
        query = query.filter(models.AssayResult.finalresult >= fineness_min)
    if fineness_max is not None and current_user.role in ['admin', 'boss', 'worker', 'testworker']:
        query = query.filter(models.AssayResult.finalresult <= fineness_max)

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
    results = db.query(models.AssayResult).filter(not_deleted_filter()).order_by(models.AssayResult.created.desc()).all()
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
        .filter(models.AssayResult.customer == user_id, not_deleted_filter())
        .order_by(models.AssayResult.created.desc())
        .all()
    )
    return results


class BatchMarkReadyRequest(BaseModel):
    assay_ids: List[int]
    ready: bool


@router.put("/batch-mark-ready")
def batch_mark_assay_ready(
    data: BatchMarkReadyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set ready status for multiple assays at once.
    Accepts an explicit ready flag (true/false) instead of toggling.
    Creates notifications and sends push for each assay that becomes ready.
    """
    if current_user.role not in ['admin', 'worker', 'testworker', 'boss']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff can change assay ready status"
        )

    results = []
    total_notifications_sent = 0

    for assay_id in data.assay_ids:
        if current_user.role == 'testworker':
            testcustomer_ids = db.query(models.User.id).filter(models.User.role == 'testcustomer').subquery()
            assay = db.query(models.AssayResult).filter(
                models.AssayResult.id == assay_id,
                models.AssayResult.customer.in_(testcustomer_ids),
                not_deleted_filter()
            ).first()
        else:
            assay = db.query(models.AssayResult).filter(
                models.AssayResult.id == assay_id,
                not_deleted_filter()
            ).first()

        if not assay:
            results.append({"assay_id": assay_id, "status": "not_found"})
            continue

        was_ready = assay.ready
        assay.ready = data.ready
        assay.modified = datetime.now()

        notifications_sent = 0
        if assay.ready and not was_ready:
            notification = models.Notification(
                user_id=assay.customer,
                assay_id=assay.id,
                title="Assay Ready",
                message=f"Your assay {assay.itemcode} result is ready",
                read=False,
                created=datetime.now()
            )
            db.add(notification)

            push_tokens = db.query(models.PushToken).filter(
                models.PushToken.user_id == assay.customer
            ).all()

            for push_token in push_tokens:
                send_push_notification(
                    expo_push_token=push_token.token,
                    title="Assay Ready",
                    body=f"Your assay {assay.itemcode} result is ready",
                    data={
                        "assay_id": assay.id,
                        "itemcode": assay.itemcode,
                        "formcode": assay.formcode
                    },
                    device_token=push_token.device_token,
                    device_type=push_token.device_type,
                    assay_id=assay.id,
                )
            notifications_sent = len(push_tokens)
        elif not assay.ready and was_ready:
            # Revert: delete old "Assay Ready" in-app notifications
            db.query(models.Notification).filter(
                models.Notification.assay_id == assay.id,
                models.Notification.user_id == assay.customer
            ).delete()

            # Create new "Assay Not Ready" in-app notification
            notification = models.Notification(
                user_id=assay.customer,
                assay_id=assay.id,
                title="Assay Not Ready",
                message=f"Your assay {assay.itemcode} is no longer ready",
                read=False,
                created=datetime.now()
            )
            db.add(notification)

            # Send visible "not ready" push notification
            push_tokens = db.query(models.PushToken).filter(
                models.PushToken.user_id == assay.customer
            ).all()
            for push_token in push_tokens:
                send_not_ready_notification(
                    expo_push_token=push_token.token,
                    assay_id=assay.id,
                    itemcode=assay.itemcode,
                    device_token=push_token.device_token,
                    device_type=push_token.device_type,
                )
            notifications_sent = len(push_tokens)

        total_notifications_sent += notifications_sent
        results.append({
            "assay_id": assay_id,
            "ready": assay.ready,
            "notifications_sent": notifications_sent
        })

    db.commit()

    return {
        "results": results,
        "total_updated": len([r for r in results if r.get("status") != "not_found"]),
        "total_notifications_sent": total_notifications_sent
    }


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
    if current_user.role not in ['admin', 'worker', 'testworker', 'boss']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin, worker, testworker, and boss can change assay ready status"
        )

    # Get the assay - testworker can only modify testcustomer assays
    if current_user.role == 'testworker':
        testcustomer_ids = db.query(models.User.id).filter(models.User.role == 'testcustomer').subquery()
        assay = db.query(models.AssayResult).filter(
            models.AssayResult.id == assay_id,
            models.AssayResult.customer.in_(testcustomer_ids),
            not_deleted_filter()
        ).first()
    else:
        assay = db.query(models.AssayResult).filter(
            models.AssayResult.id == assay_id,
            not_deleted_filter()
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
            message=f"Your assay {assay.itemcode} result is ready",
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
                body=f"Your assay {assay.itemcode} result is ready",
                data={
                    "assay_id": assay.id,
                    "itemcode": assay.itemcode,
                    "formcode": assay.formcode
                },
                device_token=push_token.device_token,
                device_type=push_token.device_type,
                assay_id=assay.id,
            )

        db.commit()

        return {
            "message": "Assay marked as ready and customer notified",
            "assay_id": assay.id,
            "notifications_sent": len(push_tokens),
            "ready": True
        }
    else:
        # Revert: delete old "Assay Ready" in-app notifications
        if not assay.ready and was_ready:
            db.query(models.Notification).filter(
                models.Notification.assay_id == assay.id,
                models.Notification.user_id == assay.customer
            ).delete()

            # Create new "Assay Not Ready" in-app notification
            notification = models.Notification(
                user_id=assay.customer,
                assay_id=assay.id,
                title="Assay Not Ready",
                message=f"Your assay {assay.itemcode} is no longer ready",
                read=False,
                created=datetime.now()
            )
            db.add(notification)

            # Send visible "not ready" push notification
            push_tokens = db.query(models.PushToken).filter(
                models.PushToken.user_id == assay.customer
            ).all()
            for push_token in push_tokens:
                send_not_ready_notification(
                    expo_push_token=push_token.token,
                    assay_id=assay.id,
                    itemcode=assay.itemcode,
                    device_token=push_token.device_token,
                    device_type=push_token.device_type,
                )

        db.commit()

        return {
            "message": "Assay marked as not ready",
            "assay_id": assay.id,
            "ready": False
        }


@router.post("/upload-return-photo")
def upload_return_photo(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_staff_user),
):
    """
    Upload a photo for sample return documentation.
    Resizes to max 1200px width, saves as JPEG.
    Available to: admin, worker, boss, testworker
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are allowed"
        )

    # Read file content
    contents = file.file.read()

    # Validate file size (max 10MB raw upload)
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )

    # Resize and compress using Pillow
    from PIL import Image

    img = Image.open(BytesIO(contents))

    # Convert RGBA to RGB if needed (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if wider than 1200px
    max_width = 1200
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Generate unique filename
    timestamp = int(time.time())
    filename = f"return_{timestamp}_{file.filename.split('.')[0]}.jpg"

    # Save to uploads/returns/
    upload_dir = "uploads/returns"
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    img.save(filepath, "JPEG", quality=75)

    return {"filename": filename}


@router.put("/batch-return")
def record_batch_return(
    request: schemas.BatchReturnRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_staff_user),
):
    """
    Record sample return for an entire batch (formcode).
    Sets returndate, collector, incharge, and optional return_photo for all items.
    Available to: admin, worker, boss, testworker
    testworker can only update batches belonging to testcustomer users.
    """
    # Build base query for the formcode
    query = db.query(models.AssayResult).filter(
        models.AssayResult.formcode == request.formcode,
        not_deleted_filter()
    )

    # testworker restriction: only update batches belonging to testcustomer
    if current_user.role == "testworker":
        testcustomer_ids = [
            u.id for u in db.query(models.User.id).filter(
                models.User.role == "testcustomer"
            ).all()
        ]
        query = query.filter(models.AssayResult.customer.in_(testcustomer_ids))

    assays = query.all()

    if not assays:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assay results found for this formcode"
        )

    now = datetime.now()
    for assay in assays:
        assay.returndate = now
        assay.collector = request.collector
        assay.incharge = request.incharge
        assay.modified = now
        if request.return_photo:
            assay.return_photo = request.return_photo

    db.commit()

    return {
        "message": f"Sample return recorded for formcode {request.formcode}",
        "updated_count": len(assays)
    }