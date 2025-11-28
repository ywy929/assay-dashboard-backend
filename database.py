from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

DATABASE_URL = settings.DATABASE_URL
engine = create_engine(
    DATABASE_URL, pool_size=12, max_overflow=20, pool_timeout=30, pool_recycle=1000
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
