"""Secure Translate — FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
import traceback
import logging

from backend.config import settings
from backend.database import init_db
from backend.api.documents import router as documents_router
from backend.api.regions import router as regions_router
from backend.api.jobs import router as jobs_router
from backend.api.languages import router as languages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade document translation with layout preservation and region-based security.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return JSON, not HTML."""
    logging.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "type": type(exc).__name__,
            "path": str(request.url),
        },
    )

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://translate.pouchen.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(regions_router, prefix="/api/regions", tags=["regions"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
app.include_router(languages_router, prefix="/api/languages", tags=["languages"])

# Serve uploaded/output files (dev only)
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/api/config")
def get_config():
    """Return non-secret configuration for the frontend."""
    return {
        "defaultEngine": settings.DEFAULT_TRANSLATION_ENGINE,
        "maxFileSizeMb": settings.MAX_FILE_SIZE_MB,
        "maxPages": settings.MAX_PAGES,
        "supportedLanguages": [
            {"code": "auto", "name": "Auto-detect"},
            {"code": "en", "name": "English"},
            {"code": "my", "name": "Burmese"},
            {"code": "zh-Hans", "name": "Simplified Chinese"},
            {"code": "zh-Hant", "name": "Traditional Chinese"},
            {"code": "vi", "name": "Vietnamese"},
            {"code": "km", "name": "Khmer"},
            {"code": "id", "name": "Indonesian"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "th", "name": "Thai"},
        ],
        "availableEngines": ["gemini", "azure", "google", "mymemory"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
