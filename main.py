from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine
from config import settings
from routers import users, auth, assayresult, analytics, pdf, notifications, sync

# Create tables
models.Base.metadata.create_all(bind=engine)

# Configure FastAPI based on environment
app = FastAPI(
    title="Assay Dashboard",
    version="1.0.0",
    description="Assay Dashboard API",
    # Disable docs in production for security (optional - remove if you want docs)
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS middleware - uses origins from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(assayresult.router, prefix="/assay-results", tags=["Assay Results"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(pdf.router, prefix="/pdf", tags=["PDF Generation"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(sync.router, prefix="/sync", tags=["Sync"])


@app.get("/")
async def root():
    return {
        "message": "Assay Dashboard",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if not settings.is_production else "disabled"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}