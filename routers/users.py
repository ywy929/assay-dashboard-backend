from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db
from config import settings
import models, schemas
from typing import List
from routers.dependency import get_admin_user, get_current_user, get_staff_user
import hashlib
import os

router = APIRouter()

@router.get("/all", response_model=List[schemas.UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    """
    Retrieve all users (Admin only)
    """
    all_users = db.query(models.User).all()
    return all_users


@router.get("/me", response_model=schemas.UserResponse)
def get_own_profile(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's own profile
    """
    return current_user


@router.get("/names")
def get_all_user_names(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get list of all user names for autocomplete
    Admin: sees all users
    Boss/Worker: sees only customers with assay results
    """
    # Base query for user names
    query = db.query(models.User.id, models.User.name, models.User.role)
    
    # Admin sees all users
    if current_user.role == 'admin':
        users = query.order_by(models.User.name).all()
        return [{"id": user.id, "name": user.name, "role": user.role} for user in users]
    
    # Boss/Worker sees only customers with assay results
    elif current_user.role in ['boss', 'worker']:
        customers = (
            query.join(models.AssayResult, models.User.id == models.AssayResult.customer)
            .filter(models.User.role == 'customer')
            .distinct()
            .order_by(models.User.name)
            .all()
        )
        return [{"id": user.id, "name": user.name, "role": user.role} for user in customers]
    
    # Others don't have access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to access user names"
    )

@router.get("/customers/names")
def get_customer_names(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get list of customer names for autocomplete (Admin/Boss/Worker only)
    Returns only customers with at least one assay result
    """
    # Only admin, boss, and worker can access customer names
    if current_user.role not in ['admin', 'boss', 'worker']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access customer names"
        )

    # Get unique customer names from users who have assay results
    customers = (
        db.query(models.User.id, models.User.name)
        .join(models.AssayResult, models.User.id == models.AssayResult.customer)
        .filter(models.User.role == 'customer')
        .distinct()
        .order_by(models.User.name)
        .all()
    )

    return [{"id": customer.id, "name": customer.name} for customer in customers]


@router.get("/customers", response_model=schemas.PaginatedCustomers)
def get_customers(
    search: str = Query(None, description="Search by name, phone, or email"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_staff_user)
):
    """
    Get paginated list of customers with optional search
    Available to: admin, worker, boss
    """
    # Base query for customers only
    query = db.query(models.User).filter(models.User.role == 'customer')

    # Apply search filter if provided
    if search:
        search_filter = or_(
            models.User.name.ilike(f"%{search}%"),
            models.User.phone.ilike(f"%{search}%"),
            models.User.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # Get total count
    total = query.count()

    # Get paginated customers
    customers = query.order_by(models.User.name).offset(offset).limit(limit).all()

    # Add total_assays count for each customer
    customer_responses = []
    for customer in customers:
        assay_count = db.query(func.count(models.AssayResult.id)).filter(
            models.AssayResult.customer == customer.id
        ).scalar()

        customer_dict = {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "area": customer.area,
            "billing": customer.billing,
            "coupon": customer.coupon,
            "created": customer.created,
            "total_assays": assay_count
        }
        customer_responses.append(schemas.CustomerResponse(**customer_dict))

    # Calculate has_more
    has_more = (offset + limit) < total

    return schemas.PaginatedCustomers(
        items=customer_responses,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more
    )


@router.get("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer_detail(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_staff_user)
):
    """
    Get detailed information about a specific customer
    Available to: admin, worker, boss
    """
    # Get customer
    customer = db.query(models.User).filter(
        models.User.id == customer_id,
        models.User.role == 'customer'
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Get total assays count
    assay_count = db.query(func.count(models.AssayResult.id)).filter(
        models.AssayResult.customer == customer.id
    ).scalar()

    return schemas.CustomerResponse(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        area=customer.area,
        billing=customer.billing,
        coupon=customer.coupon,
        created=customer.created,
        total_assays=assay_count
    )


@router.post("/change-password")
def change_user_password(
    request: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_staff_user)
):
    """
    Change password for any user
    Available to: admin, worker, boss
    - Admin/worker/boss can change customer passwords
    - Users can change their own password
    """
    # Get the target user
    target_user = db.query(models.User).filter(models.User.id == request.user_id).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Permission check
    # Staff can change customer passwords or their own password
    if target_user.role == 'customer' or target_user.id == current_user.id:
        # Allowed
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to change this user's password"
        )

    # Validate password length
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    # Generate new salt and hash using settings
    salt = os.urandom(settings.SALT_SIZE)
    pwhash = hashlib.pbkdf2_hmac('sha256', request.new_password.encode('utf-8'), salt, settings.ITERATIONS, dklen=settings.HASH_SIZE)

    # Update user password
    target_user.salt = salt
    target_user.pwhash = pwhash

    db.commit()

    return {"message": "Password changed successfully"}


@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    """
    Get user by ID (Admin only)
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user