from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Numeric, LargeBinary, Boolean, ForeignKey, SmallInteger, Text
from sqlalchemy.orm import relationship, Mapped
from database import Base
# Base is the essential class for declarative model definition.

# ----------------------------------------------------------------------
# USER MODEL (customer information)
# ----------------------------------------------------------------------

class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pwhash: Mapped[bytes] = Column(LargeBinary(32))
    salt: Mapped[bytes] = Column(LargeBinary(32))
    role: Mapped[str] = Column(String(45))
    name: Mapped[str] = Column(String(45))
    phone: Mapped[str] = Column(String(45))
    phonetwo: Mapped[str] = Column(String(45))
    email: Mapped[str] = Column(String(45))
    companyemail: Mapped[str] = Column(String(45))
    fax: Mapped[str] = Column(String(45))
    addressone: Mapped[str] = Column(String(55))
    addresstwo: Mapped[str] = Column(String(55))
    area: Mapped[str] = Column(String(45))
    mailpw: Mapped[str] = Column(String(45))
    orientation: Mapped[str] = Column(String(45))
    billing: Mapped[bool] = Column(Boolean)
    coupon: Mapped[bool] = Column(Boolean)
    created: Mapped[DateTime] = Column(DateTime)
    modified: Mapped[DateTime] = Column(DateTime)

    assay_results = relationship("AssayResult", back_populates="customer_user")
    spoil_records = relationship("SpoilRecord", back_populates="customer_user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    push_tokens = relationship("PushToken", back_populates="user")


# ----------------------------------------------------------------------
# ASSAY RESULT MODEL
# ----------------------------------------------------------------------

class AssayResult(Base):
    __tablename__ = "assayresult"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key to User
    customer: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    
    itemcode: Mapped[str] = Column(String(45))
    formcode: Mapped[int] = Column(Integer)
    collector: Mapped[str] = Column(String(45))
    incharge: Mapped[str] = Column(String(45))
    color: Mapped[int] = Column(SmallInteger)
    sampleweight: Mapped[float] = Column(Numeric(6, 2))
    samplereturn: Mapped[float] = Column(Numeric(6, 2))
    fwa: Mapped[int] = Column(Integer)
    fwb: Mapped[int] = Column(Integer)
    lwa: Mapped[int] = Column(Integer)
    lwb: Mapped[int] = Column(Integer)
    silverpct: Mapped[int] = Column(Integer)
    resulta: Mapped[float] = Column(Numeric(5, 1))
    resultb: Mapped[float] = Column(Numeric(5, 1))
    preresult: Mapped[float] = Column(Numeric(5, 1))
    loss: Mapped[float] = Column(Numeric(3, 2))
    finalresult: Mapped[float] = Column(Numeric(5, 1))
    ready: Mapped[bool] = Column(Boolean, default=False)
    deleted: Mapped[bool] = Column(Boolean, default=False)
    created: Mapped[DateTime] = Column(DateTime)
    modified: Mapped[DateTime] = Column(DateTime)
    returndate: Mapped[DateTime] = Column(DateTime)

    customer_user = relationship("User", back_populates="assay_results")
    notifications = relationship("Notification", back_populates="assay")


# ----------------------------------------------------------------------
# SPOIL RECORD MODEL
# ----------------------------------------------------------------------

class SpoilRecord(Base):
    __tablename__ = "spoilrecord"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    
    # Identical fields to AssayResult
    itemcode: Mapped[str] = Column(String(45))
    formcode: Mapped[int] = Column(Integer)
    collector: Mapped[str] = Column(String(45))
    incharge: Mapped[str] = Column(String(45))
    color: Mapped[int] = Column(SmallInteger)
    sampleweight: Mapped[float] = Column(Numeric(6, 2))
    samplereturn: Mapped[float] = Column(Numeric(6, 2))
    fwa: Mapped[int] = Column(Integer)
    fwb: Mapped[int] = Column(Integer)
    lwa: Mapped[int] = Column(Integer)
    lwb: Mapped[int] = Column(Integer)
    silverpct: Mapped[int] = Column(Integer)
    resulta: Mapped[float] = Column(Numeric(5, 1))
    resultb: Mapped[float] = Column(Numeric(5, 1))
    preresult: Mapped[float] = Column(Numeric(5, 1))
    loss: Mapped[float] = Column(Numeric(3, 2))
    finalresult: Mapped[float] = Column(Numeric(5, 1))
    created: Mapped[DateTime] = Column(DateTime)
    modified: Mapped[DateTime] = Column(DateTime)
    returndate: Mapped[DateTime] = Column(DateTime)

    customer_user = relationship("User", back_populates="spoil_records")


# ----------------------------------------------------------------------
# LOSS MODEL
# ----------------------------------------------------------------------

class Loss(Base):
    __tablename__ = "loss"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    low: Mapped[float] = Column(Numeric(6, 2))
    high: Mapped[float] = Column(Numeric(6, 2))
    pct: Mapped[float] = Column(Numeric(3, 2))
    
    created: Mapped[DateTime] = Column(DateTime)
    modified: Mapped[DateTime] = Column(DateTime)


class RefreshToken(Base):
    __tablename__ = "refreshtoken"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    token: Mapped[str] = Column(String(500), unique=True, index=True)
    expires_at: Mapped[DateTime] = Column(DateTime, index=True)
    created: Mapped[DateTime] = Column(DateTime)
    revoked: Mapped[bool] = Column(Boolean, default=False)

    user = relationship("User", back_populates="refresh_tokens")


# ----------------------------------------------------------------------
# NOTIFICATION MODEL
# ----------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    assay_id: Mapped[int] = Column(Integer, ForeignKey("assayresult.id"), index=True)
    title: Mapped[str] = Column(String(100))
    message: Mapped[str] = Column(Text)
    read: Mapped[bool] = Column(Boolean, default=False)
    created: Mapped[DateTime] = Column(DateTime)

    user = relationship("User", back_populates="notifications")
    assay = relationship("AssayResult", back_populates="notifications")


# ----------------------------------------------------------------------
# PUSH TOKEN MODEL
# ----------------------------------------------------------------------

class PushToken(Base):
    __tablename__ = "pushtoken"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("user.id"), index=True)
    token: Mapped[str] = Column(String(500), unique=True, index=True)
    device_token: Mapped[Optional[str]] = Column(String(500), nullable=True)
    device_type: Mapped[str] = Column(String(20))  # ios, android, web
    created: Mapped[DateTime] = Column(DateTime)
    updated: Mapped[DateTime] = Column(DateTime)

    user = relationship("User", back_populates="push_tokens")