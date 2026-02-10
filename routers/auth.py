from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
import models, schemas
from jose import JWTError, jwt
from config import settings
from utils import create_hash_with_new_salt, verify_password

router = APIRouter()
security = HTTPBearer()

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


@router.post("/register", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if phone number already exists
    existing_user = (
        db.query(models.User).filter(models.User.phone == user.phone).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    # Generate salt and hash password using PBKDF2-HMAC-SHA256
    salt, pwhash = create_hash_with_new_salt(user.password)

    # Create new user
    db_user = models.User(
        email=user.email,
        pwhash=pwhash,
        salt=salt,
        name=user.name,
        phone=user.phone,
        phonetwo=user.phonetwo,
        companyemail=user.companyemail,
        fax=user.fax,
        addressone=user.addressone,
        addresstwo=user.addresstwo,
        area=user.area,
        mailpw=user.mailpw,
        orientation=user.orientation,
        billing=user.billing,
        coupon=user.coupon,
        role=user.role,
        created=datetime.now(),
        modified=datetime.now(),
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Return user without sensitive information
        return db_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the user",
        )


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(payload: schemas.ChangePassword, db: Session = Depends(get_db)):
    """
    Change user's password by name
    Requires:
      - name
      - new_password

    Notes:
      - If multiple users match the same name, an error is returned to avoid unintended changes.
    """
    users = db.query(models.User).filter(models.User.name == payload.name).all()

    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple users found with that name; please use a unique identifier",
        )

    user = users[0]

    # Set new password using PBKDF2-HMAC-SHA256
    new_salt, new_hash = create_hash_with_new_salt(payload.new_password)
    user.salt = new_salt
    user.pwhash = new_hash
    user.modified = datetime.now()

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"detail": "Password updated"}
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update password",
        )


def create_tokens(user: models.User, db: Session):
    # Access token payload
    access_token_data = {"sub": user.phone, "role": user.role, "type": "access"}

    # Refresh token payload
    refresh_token_data = {"sub": user.phone, "type": "refresh"}

    access_token = create_token(
        access_token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_token(
        refresh_token_data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    # Save refresh token to database
    refresh_token_expires = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = models.RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=refresh_token_expires,
        created=datetime.now(),
        revoked=False
    )
    
    try:
        db.add(db_refresh_token)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving refresh token"
        )

    return access_token, refresh_token


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.phone == user_credentials.phone)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password using PBKDF2-HMAC-SHA256
    if not verify_password(user_credentials.password, user.salt, user.pwhash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Enforce per-user device limit for customers
    # Staff roles (worker, admin, boss) have unlimited devices
    staff_roles = {"worker", "testworker", "admin", "boss"}
    if user.role not in staff_roles:
        max_devices = user.max_devices or 1
        active_tokens = db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked == False,
            models.RefreshToken.expires_at > datetime.now()
        ).order_by(models.RefreshToken.created.asc()).all()
        # Revoke oldest tokens to make room for the new login
        if len(active_tokens) >= max_devices:
            excess = len(active_tokens) - max_devices + 1
            for token in active_tokens[:excess]:
                token.revoked = True
            db.commit()

    access_token, refresh_token = create_tokens(user, db)

    # Return tokens along with user data
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "role": user.role,
            "name": user.name,
            "phone": user.phone,
            "phonetwo": user.phonetwo,
            "area": user.area,
            "billing": user.billing,
            "coupon": user.coupon,
            "created": user.created,
        },
    }


@router.post("/logout")
def logout(current_token: str, db: Session = Depends(get_db)):
    try:
        # First verify the token signature and type
        payload = jwt.decode(current_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Not a refresh token"
            )

        # Find and revoke the refresh token
        db_token = db.query(models.RefreshToken).filter(
            models.RefreshToken.token == current_token,
            models.RefreshToken.revoked == False
        ).first()

        if not db_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or already revoked token"
            )

        # Revoke the token
        db_token.revoked = True
        db.add(db_token)
        db.commit()

        return {"detail": "Successfully logged out"}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(current_token: str, db: Session = Depends(get_db)):
    try:
        # First verify the token signature and type
        payload = jwt.decode(current_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Not a refresh token"
            )

        # Find and validate the refresh token in database
        db_token = db.query(models.RefreshToken).filter(
            models.RefreshToken.token == current_token,
            models.RefreshToken.revoked == False,
            models.RefreshToken.expires_at > datetime.now()
        ).first()

        if not db_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        # Get the user
        phone = payload.get("sub")
        user = db.query(models.User).filter(models.User.phone == phone).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Revoke the used refresh token
        db_token.revoked = True
        db.add(db_token)
        db.commit()

        # Create new tokens
        access_token, refresh_token = create_tokens(user, db)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "role": user.role,
                "name": user.name,
                "phone": user.phone,
                "phonetwo": user.phonetwo,
                "area": user.area,
                "billing": user.billing,
                "coupon": user.coupon,
                "created": user.created,
            },
        }

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
