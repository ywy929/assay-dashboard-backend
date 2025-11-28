from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine
from routers import users, auth, assayresult, analytics, pdf, notifications

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Assay Dashboard",
    version="1.0.0",
    description="Assay Dashboard"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"], # React Native default port
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

@app.get("/")
async def root():
    return {
        "message": "Assay Dashboard",
        "version": "1.0.0",
        "docs": "/docs"
    }