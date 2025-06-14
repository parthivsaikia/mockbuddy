# app/main.py
import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

from app.config import settings
from app.db.database import create_db_tables

from app.routes import (
    auth_user_routes,
    auth_interviewer_routes,
    user_profile_routes,
    Interview_profile_routes,
    scheduling_routes,
    dsa_routes
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for MockBuddy interview preparation platform.",
    version="1.0.0",
    openapi_url="/openapi.json",     # <-- Changed to root
    docs_url="/docs",                # <-- Swagger UI at /docs
    redoc_url="/redoc"               # <-- ReDoc UI at /redoc
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip() for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(f"CORS middleware enabled for origins: {settings.BACKEND_CORS_ORIGINS}")

# --- Include Routers ---
from fastapi import APIRouter as FastAPIAPIRouter
api_v1_router = FastAPIAPIRouter()

api_v1_router.include_router(auth_user_routes.router, prefix="/auth/users", tags=["User Authentication"])
api_v1_router.include_router(auth_interviewer_routes.router, prefix="/auth/interviewers", tags=["Interviewer Authentication"])
api_v1_router.include_router(user_profile_routes.router, prefix="/users", tags=["User Profile & History"])
api_v1_router.include_router(Interview_profile_routes.router, prefix="/interviewers", tags=["Interviewer Profiles & Public Listing"])
api_v1_router.include_router(scheduling_routes.router, prefix="/schedule", tags=["Interview Scheduling & Management"])
api_v1_router.include_router(dsa_routes.router, prefix="/dsa", tags=["DSA Evaluation & Questions"])

app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": f"{settings.PROJECT_NAME} API is running!",
        "status": "healthy",
        "docs_url": app.docs_url,
        "redoc_url": app.redoc_url,
        "version": app.version
    }

@app.get("/health", tags=["Health Check"])
async def health_check_detailed():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.exception_handler(HTTPException)
async def http_exception_handler_custom(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler_custom(request, exc: Exception):
    logger.error(f"Unhandled Internal Server Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected internal server error occurred."}
    )

@app.on_event("startup")
async def startup_event():
    logger.info(f"Application startup: {settings.PROJECT_NAME} v{app.version if hasattr(app, 'version') else 'N/A'}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Application shutdown: {settings.PROJECT_NAME}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server directly for development...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
