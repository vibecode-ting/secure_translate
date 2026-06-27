"""Document API routes — upload, list, view, delete, detect, download."""

import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import settings
from backend.models.document import Document, DocumentStatus, DocumentType
from backend.models.region import Region, RegionType
from backend.models.job import TranslationJob

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document (image or PDF). Validates file type, saves to disk, creates DB record."""
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: jpg, png, pdf",
        )

    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check file size by reading content
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Max: {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Determine document type
    doc_type = DocumentType.PDF if ext == ".pdf" else DocumentType.IMAGE

    # Generate unique filename and save
    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = settings.UPLOAD_DIR / unique_name
    save_path.write_bytes(content)

    # Extract page count for PDFs
    page_count = 1
    if doc_type == DocumentType.PDF:
        try:
            import pymupdf

            pdf_doc = pymupdf.open(str(save_path))
            page_count = pdf_doc.page_count
            pdf_doc.close()
        except Exception as e:
            # Clean up file on error
            save_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Failed to read PDF: {e}")

    # Create DB record
    document = Document(
        filename=unique_name,
        original_filename=file.filename,
        doc_type=doc_type,
        status=DocumentStatus.UPLOADED,
        page_count=page_count,
        file_size_bytes=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "document_id": document.id,
        "filename": document.original_filename,
        "page_count": document.page_count,
        "doc_type": document.doc_type.value,
        "status": document.status.value,
    }


@router.get("/")
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List all documents, paginated, sorted by created_at descending."""
    total = db.query(Document).count()
    documents = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "doc_type": d.doc_type.value,
                "status": d.status.value,
                "page_count": d.page_count,
                "file_size_bytes": d.file_size_bytes,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in documents
        ],
    }


@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get document details including its regions."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    regions = (
        db.query(Region)
        .filter(Region.document_id == document_id)
        .order_by(Region.page_number, Region.y, Region.x)
        .all()
    )

    return {
        "id": document.id,
        "filename": document.original_filename,
        "doc_type": document.doc_type.value,
        "status": document.status.value,
        "page_count": document.page_count,
        "file_size_bytes": document.file_size_bytes,
        "source_language": document.source_language,
        "target_language": document.target_language,
        "progress": document.progress,
        "error_message": document.error_message,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "regions": [
            {
                "id": r.id,
                "page_number": r.page_number,
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "region_type": r.region_type.value,
                "original_text": r.original_text,
                "translated_text": r.translated_text,
                "font_size": r.font_size,
                "font_family": r.font_family,
                "label": r.label,
                "is_auto_detected": r.is_auto_detected,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in regions
        ],
    }


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document and all its associated files."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete uploaded file
    upload_path = settings.UPLOAD_DIR / document.filename
    upload_path.unlink(missing_ok=True)

    # Delete any output files for this document's jobs
    jobs = db.query(TranslationJob).filter(TranslationJob.document_id == document_id).all()
    for job in jobs:
        if job.output_filename:
            output_path = settings.OUTPUT_DIR / job.output_filename
            output_path.unlink(missing_ok=True)

    # Cascading deletes handle regions and jobs via SQLAlchemy relationships
    db.delete(document)
    db.commit()

    return {"detail": "Document deleted", "document_id": document_id}


@router.get("/{document_id}/pages/{page_number}/image")
def get_page_image(
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
):
    """Serve a rendered page image. For PDFs, render the specific page. For images, return original."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if page_number < 0 or page_number >= document.page_count:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page_number} out of range (0-{document.page_count - 1})",
        )

    file_path = settings.UPLOAD_DIR / document.filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    if document.doc_type == DocumentType.PDF:
        # Render PDF page to image using pymupdf
        try:
            import pymupdf

            pdf_doc = pymupdf.open(str(file_path))
            page = pdf_doc[page_number]
            # Render at configured DPI
            zoom = settings.OCR_DPI / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Save rendered page as temporary PNG
            page_image_name = f"{document_id}_page_{page_number}.png"
            page_image_path = settings.UPLOAD_DIR / page_image_name
            pix.save(str(page_image_path))

            pdf_doc.close()

            return FileResponse(
                path=str(page_image_path),
                media_type="image/png",
                filename=page_image_name,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to render PDF page: {e}")
    else:
        # For images, return the original file (page_number should be 0)
        media_type = "image/png" if document.filename.endswith(".png") else "image/jpeg"
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=document.original_filename,
        )


@router.get("/{document_id}/pages/{page_number}/translated")
def get_translated_page_image(
    document_id: str,
    page_number: int,
    job_id: str = Query(..., description="Translation job ID"),
    db: Session = Depends(get_db),
):
    """Serve a rendered translated page image. For PDFs, render from the translated output."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if page_number < 0 or page_number >= document.page_count:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page_number} out of range (0-{document.page_count - 1})",
        )

    # Get the translation job
    job = (
        db.query(TranslationJob)
        .filter(TranslationJob.id == job_id, TranslationJob.document_id == document_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translation job not found")

    if not job.output_filename:
        raise HTTPException(status_code=404, detail="No translated output available")

    output_path = settings.OUTPUT_DIR / job.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Translated file not found on disk")

    if document.doc_type == DocumentType.PDF:
        # Render translated PDF page to image
        try:
            import pymupdf

            pdf_doc = pymupdf.open(str(output_path))
            page = pdf_doc[page_number]
            # Render at configured DPI
            zoom = settings.OCR_DPI / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Save rendered page as temporary PNG
            page_image_name = f"{document_id}_translated_page_{page_number}.png"
            page_image_path = settings.OUTPUT_DIR / page_image_name
            pix.save(str(page_image_path))

            pdf_doc.close()

            return FileResponse(
                path=str(page_image_path),
                media_type="image/png",
                filename=page_image_name,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to render translated PDF page: {e}")
    else:
        # For images, return the translated output directly
        ext = output_path.suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"
        return FileResponse(
            path=str(output_path),
            media_type=media_type,
            filename=f"translated_{document.original_filename}",
        )


@router.post("/{document_id}/detect")
def detect_regions(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Trigger OCR text detection on all pages. Creates Region records with region_type=TEXT."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status not in (DocumentStatus.UPLOADED, DocumentStatus.READY, DocumentStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Document is in '{document.status.value}' state. Must be uploaded/ready/failed to run detection.",
        )

    # Mark as processing
    document.status = DocumentStatus.PROCESSING
    db.commit()

    try:
        from backend.services.ocr_service import detect_text_regions

        file_path = settings.UPLOAD_DIR / document.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Document file not found on disk")

        # Run OCR detection across all pages
        detected_regions = []
        if document.doc_type == DocumentType.PDF:
            import pymupdf
            pdf_doc = pymupdf.open(str(file_path))
            for page_num in range(document.page_count):
                page = pdf_doc[page_num]
                zoom = settings.OCR_DPI / 72.0
                mat = pymupdf.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                page_img_path = settings.UPLOAD_DIR / f"{document_id}_page_{page_num}.png"
                pix.save(str(page_img_path))
                page_regions = detect_text_regions(str(page_img_path))
                for r in page_regions:
                    r["page_number"] = page_num
                detected_regions.extend(page_regions)
                page_img_path.unlink(missing_ok=True)
            pdf_doc.close()
        else:
            page_regions = detect_text_regions(str(file_path))
            for r in page_regions:
                r["page_number"] = 0
            detected_regions = page_regions

        # Clear any existing auto-detected regions for this document
        db.query(Region).filter(
            Region.document_id == document_id,
            Region.is_auto_detected == True,
        ).delete()

        # Create new Region records
        created_regions = []
        for region_data in detected_regions:
            region = Region(
                document_id=document_id,
                page_number=region_data["page_number"],
                x=region_data["x"],
                y=region_data["y"],
                width=region_data["width"],
                height=region_data["height"],
                region_type=RegionType.TEXT,
                original_text=region_data.get("text"),
                font_size=region_data.get("font_size"),
                font_family=region_data.get("font_family"),
                is_auto_detected=True,
            )
            db.add(region)
            created_regions.append(region)

        document.status = DocumentStatus.READY
        document.progress = 1.0
        db.commit()

        return {
            "document_id": document_id,
            "status": document.status.value,
            "regions_detected": len(created_regions),
        }

    except ImportError:
        document.status = DocumentStatus.FAILED
        document.error_message = "OCR service not available"
        db.commit()
        raise HTTPException(status_code=500, detail="OCR service not implemented yet")
    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")


@router.get("/{document_id}/download/{job_id}")
def download_translated(
    document_id: str,
    job_id: str,
    db: Session = Depends(get_db),
):
    """Download the translated output file for a completed job."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    job = (
        db.query(TranslationJob)
        .filter(TranslationJob.id == job_id, TranslationJob.document_id == document_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translation job not found")

    if job.status.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job.status.value})",
        )

    if not job.output_filename:
        raise HTTPException(status_code=404, detail="No output file available")

    output_path = settings.OUTPUT_DIR / job.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    # Determine media type from extension
    ext = output_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=f"translated_{document.original_filename}",
    )
