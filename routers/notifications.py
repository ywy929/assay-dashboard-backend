from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import List, Optional
from datetime import datetime
import models
from routers.dependency import get_db, get_current_user
from pydantic import BaseModel
from config import settings
import requests
from services.apns import send_apns_alert
from services.fcm import send_fcm_notification as send_fcm_direct

router = APIRouter(
    tags=["notifications"]
)


# ----------------------------------------------------------------------
# SCHEMAS
# ----------------------------------------------------------------------

class PushTokenCreate(BaseModel):
    token: str
    device_token: Optional[str] = None  # Native APNs/FCM token
    device_type: str  # ios, android, web


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    read: bool
    created: datetime
    assay_id: int
    itemcode: str | None = None
    formcode: int | None = None

    class Config:
        from_attributes = True


class NotificationStats(BaseModel):
    total: int
    unread: int


# ----------------------------------------------------------------------
# PUSH NOTIFICATION HELPER
# ----------------------------------------------------------------------

def send_push_notification(
    expo_push_token: str,
    title: str,
    body: str,
    data: dict = None,
    device_token: str = None,
    device_type: str = None,
    assay_id: int = None,
):
    """
    Send push notification. Routes to the appropriate service:
    - iOS with native token → APNs directly
    - Android with native token → FCM V1 directly
    - Fallback → Expo Push API
    """
    # iOS with native token → send via APNs directly
    if device_token and device_type == "ios" and settings.APNS_KEY_ID:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] Using APNs for device_token={device_token[:8]}..., assay_id={assay_id}")
        collapse_id = f"assay-ready-{assay_id}" if assay_id else None
        return send_apns_alert(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
            collapse_id=collapse_id,
        )

    # Android with native token → send via FCM V1 directly
    if device_token and device_type == "android" and settings.FCM_SERVICE_ACCOUNT_PATH:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] Using FCM direct for device_token={device_token[:20]}..., assay_id={assay_id}")
        return send_fcm_direct(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
        )

    # Fallback → send via Expo Push API
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] Using Expo fallback (device_token={device_token}, device_type={device_type})")
    try:
        message = {
            "to": expo_push_token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
            "channelId": "default",
        }

        response = requests.post(
            "https://exp.host/--/api/v2/push/send",
            headers={
                "Accept": "application/json",
                "Accept-encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
            json=message,
        )

        result = response.json()
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] Expo response: {result}")
        return result
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] Error sending push notification: {e}")
        return None


def send_not_ready_notification(
    expo_push_token: str,
    assay_id: int,
    itemcode: str = None,
    device_token: str = None,
    device_type: str = None,
):
    """
    Send a visible 'Assay Not Ready' notification when a worker reverts
    an assay from ready back to not-ready.
    """
    title = "Assay Not Ready"
    body = f"Your assay {itemcode} is no longer ready" if itemcode else "Your assay is no longer ready"
    data = {"assay_id": assay_id, "itemcode": itemcode}

    # iOS with native token → send via APNs
    if device_token and device_type == "ios" and settings.APNS_KEY_ID:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [NOT-READY] Using APNs for device_token={device_token[:8]}..., assay_id={assay_id}")
        return send_apns_alert(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
        )

    # Android with native token → send via FCM V1 directly
    if device_token and device_type == "android" and settings.FCM_SERVICE_ACCOUNT_PATH:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [NOT-READY] Using FCM direct for device_token={device_token[:20]}..., assay_id={assay_id}")
        return send_fcm_direct(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
        )

    # Fallback → Expo Push API
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [NOT-READY] Using Expo fallback for assay_id={assay_id}")
    try:
        message = {
            "to": expo_push_token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data,
            "channelId": "default",
        }

        response = requests.post(
            "https://exp.host/--/api/v2/push/send",
            headers={
                "Accept": "application/json",
                "Accept-encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
            json=message,
        )

        return response.json()
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [NOT-READY] Error: {e}")
        return None


# ----------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------

@router.post("/push-token")
def register_push_token(
    token_data: PushTokenCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register or update a push notification token for the current user.
    """
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [TOKEN] Registering push token for user={current_user.id}, device_type={token_data.device_type}, device_token={'yes' if token_data.device_token else 'None'}")

    # Check if token already exists
    existing_token = db.query(models.PushToken).filter(
        models.PushToken.token == token_data.token
    ).first()

    if existing_token:
        # Update existing token
        existing_token.user_id = current_user.id
        existing_token.device_token = token_data.device_token
        existing_token.device_type = token_data.device_type
        existing_token.updated = datetime.now()
    else:
        # Create new token
        push_token = models.PushToken(
            user_id=current_user.id,
            token=token_data.token,
            device_token=token_data.device_token,
            device_type=token_data.device_type,
            created=datetime.now(),
            updated=datetime.now()
        )
        db.add(push_token)

    try:
        db.commit()
    except Exception:
        # Race condition: another request inserted the same token concurrently
        db.rollback()
        existing_token = db.query(models.PushToken).filter(
            models.PushToken.token == token_data.token
        ).first()
        if existing_token:
            existing_token.user_id = current_user.id
            existing_token.device_token = token_data.device_token
            existing_token.device_type = token_data.device_type
            existing_token.updated = datetime.now()
            db.commit()

    return {"message": "Push token registered successfully"}


@router.delete("/push-token/{token}")
def unregister_push_token(
    token: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unregister a push notification token.
    """
    push_token = db.query(models.PushToken).filter(
        and_(
            models.PushToken.token == token,
            models.PushToken.user_id == current_user.id
        )
    ).first()

    if push_token:
        db.delete(push_token)
        db.commit()

    return {"message": "Push token unregistered successfully"}


@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for the current user.
    """
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )

    if unread_only:
        query = query.filter(models.Notification.read == False)

    notifications = query.order_by(
        desc(models.Notification.created)
    ).limit(limit).offset(offset).all()

    # Enrich with assay details
    result = []
    for notif in notifications:
        assay = db.query(models.AssayResult).filter(
            models.AssayResult.id == notif.assay_id
        ).first()

        result.append(NotificationResponse(
            id=notif.id,
            title=notif.title,
            message=notif.message,
            read=notif.read,
            created=notif.created,
            assay_id=notif.assay_id,
            itemcode=assay.itemcode if assay else None,
            formcode=assay.formcode if assay else None
        ))

    return result


@router.get("/stats", response_model=NotificationStats)
def get_notification_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notification statistics for the current user.
    """
    total = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).count()

    unread = db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.read == False
        )
    ).count()

    return NotificationStats(total=total, unread=unread)


@router.put("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a notification as read.
    """
    notification = db.query(models.Notification).filter(
        and_(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id
        )
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.read = True
    db.commit()

    return {"message": "Notification marked as read"}


@router.put("/read-all")
def mark_all_notifications_as_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read for the current user.
    """
    db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.read == False
        )
    ).update({"read": True})

    db.commit()

    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a notification.
    """
    notification = db.query(models.Notification).filter(
        and_(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id
        )
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    db.delete(notification)
    db.commit()

    return {"message": "Notification deleted"}
