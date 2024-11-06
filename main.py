import sys
from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from loguru import logger

# Import settings first as it sets up crucial configurations
from app.core.config import get_settings
settings = get_settings()

# Configure paths for Tesseract and Poppler
os.environ["TESSERACT_CMD"] = settings.TESSERACT_PATH
os.environ["POPPLER_PATH"] = settings.POPPLER_PATH

# Initialize FastAPI with settings
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes after settings are configured
from app.api.routes import resume_router

# Include routers
app.include_router(resume_router, prefix=settings.API_V1_STR)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception handler caught: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    )

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    # Validate critical settings and paths
    try:
        if not os.path.exists(settings.TESSERACT_PATH):
            raise Exception(f"Tesseract not found at {settings.TESSERACT_PATH}")
        if not os.path.exists(settings.POPPLER_PATH):
            raise Exception(f"Poppler not found at {settings.POPPLER_PATH}")
        logger.info("All required external tools validated successfully")
    except Exception as e:
        logger.error(f"Startup validation failed: {str(e)}")
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.PROJECT_NAME}")
    # Add any cleanup code here

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": "development" if settings.DEBUG else "production"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.DEBUG,
        workers=settings.WORKERS_COUNT if not settings.DEBUG else 1
    )