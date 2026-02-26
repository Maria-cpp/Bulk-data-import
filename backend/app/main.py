"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.logging import configure_logging, get_logger

# Configure structured logging
configure_logging()
logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title="Bulk Data Import API",
    description="Extract tabular data from documents (PDF, Excel, Word, Image, CSV)",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next):
    """Reject requests exceeding file size limit early."""
    content_length = request.headers.get("content-length")
    if content_length:
        content_length = int(content_length)
        if content_length > settings.BULK_IMPORT_MAX_FILE_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "FILE_TOO_LARGE",
                    "message": "File size exceeds limit",
                    "max_size_bytes": settings.BULK_IMPORT_MAX_FILE_SIZE,
                    "received_size_bytes": content_length,
                },
            )
    return await call_next(request)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and register routers
from app.api.routes import bulk_import
app.include_router(bulk_import.router, prefix="/api/v1/bulk-imports", tags=["bulk-imports"])


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("bulk_import_api_starting", version="0.1.0")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("bulk_import_api_shutting_down")
