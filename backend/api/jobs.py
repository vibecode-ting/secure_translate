"""Translation job API routes — create, list, status, cancel."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.document import Document, DocumentStatus
from backend.models.job import TranslationJob, JobStatus

router = APIRouter()


# --- Request schemas ---


class JobCreate(BaseModel):
    document_id: str
    source_language: str = Field(min_length=2, max_length=10)
    target_language: str = Field(min_length=2, max_length=10)
    engine: str = Field(default="gemini", max_length=50)


# --- Helpers ---


def _serialize_job(job: TranslationJob) -> dict:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "celery_task_id": job.celery_task_id,
        "source_language": job.source_language,
        "target_language": job.target_language,
        "engine": job.engine,
        "status": job.status.value,
        "progress": job.progress,
        "pages_completed": job.pages_completed,
        "total_pages": job.total_pages,
        "error_message": job.error_message,
        "output_filename": job.output_filename,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# --- Endpoints ---


@router.post("/")
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    """Create a translation job. Validates document exists and is READY. Dispatches Celery task."""
    document = db.query(Document).filter(Document.id == body.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=400,
            detail=f"Document is in '{document.status.value}' state. Must be 'ready' to start translation.",
        )

    # Validate languages are different
    if body.source_language == body.target_language:
        raise HTTPException(
            status_code=400,
            detail="Source and target languages must be different",
        )

    # Create job record
    job = TranslationJob(
        document_id=body.document_id,
        source_language=body.source_language,
        target_language=body.target_language,
        engine=body.engine,
        status=JobStatus.PENDING,
        total_pages=document.page_count,
    )
    db.add(job)

    # Update document status
    document.status = DocumentStatus.TRANSLATING
    document.source_language = body.source_language
    document.target_language = body.target_language

    db.commit()
    db.refresh(job)

    # Dispatch translation — try Celery first, fall back to background thread
    try:
        from backend.tasks.translate_task import translate_document

        task = translate_document.delay(job.id)
        job.celery_task_id = task.id
        db.commit()
    except Exception:
        # Celery/Redis not available — run in background thread
        import threading
        from backend.tasks.translate_task import run_translation_sync

        def _run_sync(job_id: str):
            """Run translation synchronously (no Celery)."""
            try:
                run_translation_sync(job_id)
            except Exception:
                pass  # Error is stored in DB by the task

        thread = threading.Thread(target=_run_sync, args=(job.id,), daemon=True)
        thread.start()
        db.commit()

    return _serialize_job(job)


@router.get("/")
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List all translation jobs, paginated."""
    total = db.query(TranslationJob).count()
    jobs = (
        db.query(TranslationJob)
        .order_by(TranslationJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize_job(j) for j in jobs],
    }


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job status with progress, pages_completed, total_pages, error_message."""
    job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Translation job not found")

    return _serialize_job(job)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running translation job by revoking the Celery task."""
    job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Translation job not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in '{job.status.value}' state. Must be pending or running.",
        )

    # Revoke Celery task if it has a task ID
    if job.celery_task_id:
        try:
            from backend.tasks.celery_app import celery_app

            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass  # Best effort — task may already be done

    # Update job status
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = "Cancelled by user"

    # Reset document status back to READY
    document = db.query(Document).filter(Document.id == job.document_id).first()
    if document and document.status == DocumentStatus.TRANSLATING:
        document.status = DocumentStatus.READY

    db.commit()
    db.refresh(job)

    return _serialize_job(job)


@router.get("/document/{document_id}")
def list_jobs_for_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get all translation jobs for a specific document."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = (
        db.query(TranslationJob)
        .filter(TranslationJob.document_id == document_id)
        .order_by(TranslationJob.created_at.desc())
        .all()
    )

    return {
        "document_id": document_id,
        "total": len(jobs),
        "items": [_serialize_job(j) for j in jobs],
    }
