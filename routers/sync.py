"""
Sync Router - Endpoints for local-cloud database synchronization
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from database import get_db
from config import settings
import models

router = APIRouter(tags=["sync"])

# Allowed IPs for sync endpoint (your local server's public IP)
ALLOWED_SYNC_IPS = [
    "127.0.0.1",        # localhost for testing
    "139.59.250.254",   # DigitalOcean VPS
]


# ----------------------------------------------------------------------
# SCHEMAS
# ----------------------------------------------------------------------

class UserSync(BaseModel):
    id: int
    pwhash: Optional[bytes] = None
    salt: Optional[bytes] = None
    role: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    phonetwo: Optional[str] = None
    email: Optional[str] = None
    companyemail: Optional[str] = None
    fax: Optional[str] = None
    addressone: Optional[str] = None
    addresstwo: Optional[str] = None
    area: Optional[str] = None
    mailpw: Optional[str] = None
    orientation: Optional[str] = None
    billing: Optional[bool] = None
    coupon: Optional[bool] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssayResultSync(BaseModel):
    id: int
    customer: Optional[int] = None
    itemcode: Optional[str] = None
    formcode: Optional[int] = None
    collector: Optional[str] = None
    incharge: Optional[str] = None
    color: Optional[int] = None
    sampleweight: Optional[float] = None
    samplereturn: Optional[float] = None
    fwa: Optional[int] = None
    fwb: Optional[int] = None
    lwa: Optional[int] = None
    lwb: Optional[int] = None
    silverpct: Optional[int] = None
    resulta: Optional[float] = None
    resultb: Optional[float] = None
    preresult: Optional[float] = None
    loss: Optional[float] = None
    finalresult: Optional[float] = None
    ready: Optional[bool] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    returndate: Optional[datetime] = None

    class Config:
        from_attributes = True


class SpoilRecordSync(BaseModel):
    id: int
    customer: Optional[int] = None
    itemcode: Optional[str] = None
    formcode: Optional[int] = None
    collector: Optional[str] = None
    incharge: Optional[str] = None
    color: Optional[int] = None
    sampleweight: Optional[float] = None
    samplereturn: Optional[float] = None
    fwa: Optional[int] = None
    fwb: Optional[int] = None
    lwa: Optional[int] = None
    lwb: Optional[int] = None
    silverpct: Optional[int] = None
    resulta: Optional[float] = None
    resultb: Optional[float] = None
    preresult: Optional[float] = None
    loss: Optional[float] = None
    finalresult: Optional[float] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    returndate: Optional[datetime] = None

    class Config:
        from_attributes = True


class LossSync(BaseModel):
    id: int
    low: Optional[float] = None
    high: Optional[float] = None
    pct: Optional[float] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    class Config:
        from_attributes = True


class SyncChangesResponse(BaseModel):
    users: List[UserSync]
    assay_results: List[AssayResultSync]
    spoil_records: List[SpoilRecordSync]
    losses: List[LossSync]
    server_time: datetime


class PushDataRequest(BaseModel):
    users: List[dict] = []
    assay_results: List[dict] = []
    spoil_records: List[dict] = []
    losses: List[dict] = []


class PushDataResponse(BaseModel):
    success: bool
    users_synced: int
    assay_results_synced: int
    spoil_records_synced: int
    losses_synced: int
    notifications_created: int
    errors: List[str] = []


# ----------------------------------------------------------------------
# AUTHENTICATION
# ----------------------------------------------------------------------

def verify_sync_key(x_sync_key: str = Header(...)):
    """Verify the sync API key"""
    if x_sync_key != settings.SYNC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sync API key"
        )
    return True


def verify_sync_ip(request: Request):
    """Verify the request comes from an allowed IP"""
    client_ip = request.client.host
    # Also check X-Forwarded-For header in case behind reverse proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    if client_ip not in ALLOWED_SYNC_IPS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"IP {client_ip} not allowed for sync operations"
        )
    return True


# ----------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------

@router.get("/changes", response_model=SyncChangesResponse)
def get_changes(
    request: Request,
    since: datetime,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_sync_key),
    __: bool = Depends(verify_sync_ip)
):
    """
    Get all records modified since the given timestamp.
    Used by local service to pull changes from cloud.
    """
    users = db.query(models.User).filter(models.User.modified > since).all()
    assay_results = db.query(models.AssayResult).filter(models.AssayResult.modified > since).all()
    spoil_records = db.query(models.SpoilRecord).filter(models.SpoilRecord.modified > since).all()
    losses = db.query(models.Loss).filter(models.Loss.modified > since).all()

    return SyncChangesResponse(
        users=[UserSync.model_validate(u) for u in users],
        assay_results=[AssayResultSync.model_validate(a) for a in assay_results],
        spoil_records=[SpoilRecordSync.model_validate(s) for s in spoil_records],
        losses=[LossSync.model_validate(l) for l in losses],
        server_time=datetime.now()
    )


@router.post("/push", response_model=PushDataResponse)
def push_data(
    request: Request,
    data: PushDataRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_sync_key),
    __: bool = Depends(verify_sync_ip)
):
    """
    Receive data from local and upsert to cloud database.
    Creates notifications when assay.ready changes to true.
    """
    errors = []
    users_synced = 0
    assay_results_synced = 0
    spoil_records_synced = 0
    losses_synced = 0
    notifications_created = 0

    # Sync users
    for user_data in data.users:
        try:
            user_id = user_data.get('id')
            existing = db.query(models.User).filter(models.User.id == user_id).first()

            local_modified = user_data.get('modified')
            if isinstance(local_modified, str):
                local_modified = datetime.fromisoformat(local_modified.replace('Z', '+00:00'))

            if existing:
                # Only update if local is newer
                if local_modified and (existing.modified is None or local_modified > existing.modified):
                    for key, value in user_data.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
                    users_synced += 1
            else:
                # Insert new
                new_user = models.User(**user_data)
                db.add(new_user)
                users_synced += 1
        except Exception as e:
            errors.append(f"User {user_data.get('id')}: {str(e)}")

    # Sync assay results
    for assay_data in data.assay_results:
        try:
            assay_id = assay_data.get('id')
            existing = db.query(models.AssayResult).filter(models.AssayResult.id == assay_id).first()

            local_modified = assay_data.get('modified')
            if isinstance(local_modified, str):
                local_modified = datetime.fromisoformat(local_modified.replace('Z', '+00:00'))

            local_ready = assay_data.get('ready', False)

            if existing:
                # Check if ready status is changing to true
                was_ready = existing.ready

                # Only update if local is newer
                if local_modified and (existing.modified is None or local_modified > existing.modified):
                    for key, value in assay_data.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
                    assay_results_synced += 1

                    # Create notification if ready changed from false to true
                    if local_ready and not was_ready:
                        notification = models.Notification(
                            user_id=existing.customer,
                            assay_id=existing.id,
                            title="Assay Ready",
                            message=f"Your assay {existing.itemcode} is ready for pickup",
                            read=False,
                            created=datetime.now()
                        )
                        db.add(notification)
                        notifications_created += 1

                        # Send push notification
                        _send_push_for_assay(db, existing)
            else:
                # Insert new
                new_assay = models.AssayResult(**assay_data)
                db.add(new_assay)
                assay_results_synced += 1

                # Create notification if new and ready
                if local_ready:
                    db.flush()  # Get the ID
                    notification = models.Notification(
                        user_id=new_assay.customer,
                        assay_id=new_assay.id,
                        title="Assay Ready",
                        message=f"Your assay {new_assay.itemcode} is ready for pickup",
                        read=False,
                        created=datetime.now()
                    )
                    db.add(notification)
                    notifications_created += 1
                    _send_push_for_assay(db, new_assay)

        except Exception as e:
            errors.append(f"AssayResult {assay_data.get('id')}: {str(e)}")

    # Sync spoil records
    for spoil_data in data.spoil_records:
        try:
            spoil_id = spoil_data.get('id')
            existing = db.query(models.SpoilRecord).filter(models.SpoilRecord.id == spoil_id).first()

            local_modified = spoil_data.get('modified')
            if isinstance(local_modified, str):
                local_modified = datetime.fromisoformat(local_modified.replace('Z', '+00:00'))

            if existing:
                if local_modified and (existing.modified is None or local_modified > existing.modified):
                    for key, value in spoil_data.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
                    spoil_records_synced += 1
            else:
                new_spoil = models.SpoilRecord(**spoil_data)
                db.add(new_spoil)
                spoil_records_synced += 1
        except Exception as e:
            errors.append(f"SpoilRecord {spoil_data.get('id')}: {str(e)}")

    # Sync losses
    for loss_data in data.losses:
        try:
            loss_id = loss_data.get('id')
            existing = db.query(models.Loss).filter(models.Loss.id == loss_id).first()

            local_modified = loss_data.get('modified')
            if isinstance(local_modified, str):
                local_modified = datetime.fromisoformat(local_modified.replace('Z', '+00:00'))

            if existing:
                if local_modified and (existing.modified is None or local_modified > existing.modified):
                    for key, value in loss_data.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
                    losses_synced += 1
            else:
                new_loss = models.Loss(**loss_data)
                db.add(new_loss)
                losses_synced += 1
        except Exception as e:
            errors.append(f"Loss {loss_data.get('id')}: {str(e)}")

    db.commit()

    return PushDataResponse(
        success=len(errors) == 0,
        users_synced=users_synced,
        assay_results_synced=assay_results_synced,
        spoil_records_synced=spoil_records_synced,
        losses_synced=losses_synced,
        notifications_created=notifications_created,
        errors=errors
    )


def _send_push_for_assay(db: Session, assay: models.AssayResult):
    """Send push notification for an assay"""
    from routers.notifications import send_push_notification

    push_tokens = db.query(models.PushToken).filter(
        models.PushToken.user_id == assay.customer
    ).all()

    for push_token in push_tokens:
        try:
            send_push_notification(
                expo_push_token=push_token.token,
                title="Assay Ready",
                body=f"Your assay {assay.itemcode} is ready for pickup",
                data={"assay_id": assay.id, "itemcode": assay.itemcode}
            )
        except Exception:
            pass  # Don't fail sync if push fails
