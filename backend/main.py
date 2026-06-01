import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.routes.analysis_routes import router as analysis_router
from api.routes.resume_routes import router as resume_router


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# FastAPI Application
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Career Intelligence Platform",
    description="AI-Powered Student Career Intelligence Platform",
    version="1.0.0",
)


# -----------------------------------------------------------------------------
# CORS Configuration
# Development: Allow all origins
# Production: Replace "*" with specific frontend domains
# Example:
# allow_origins=["https://yourdomain.com"]
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Request Logging Middleware
# -----------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        f"Incoming Request: {request.method} {request.url.path}"
    )

    response = await call_next(request)

    logger.info(
        f"Response Status: {response.status_code} "
        f"for {request.method} {request.url.path}"
    )

    return response


# -----------------------------------------------------------------------------
# Startup Event
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("Career Intelligence Platform API started successfully.")


# -----------------------------------------------------------------------------
# Shutdown Event
# -----------------------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Career Intelligence Platform API shutting down.")


# -----------------------------------------------------------------------------
# Global Exception Handler
# -----------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        f"Unhandled exception on {request.url.path}: {exc}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error"
        },
    )


# -----------------------------------------------------------------------------
# Health & Root Endpoints
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Career Intelligence Platform API",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }


# -----------------------------------------------------------------------------
# Register Routers
# -----------------------------------------------------------------------------
app.include_router(analysis_router)
app.include_router(resume_router)