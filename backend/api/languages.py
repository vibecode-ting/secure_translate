"""Language API routes — list supported languages, detect document language."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import settings
from backend.models.document import Document, DocumentType
from backend.services import language_service

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request schemas ---


class DetectRequest(BaseModel):
    document_id: str


# --- Endpoints ---


@router.get("/")
def list_languages():
    """Return all supported languages with codes and names.

    Includes an 'auto' option for automatic language detection.
    """
    return {
        "languages": language_service.get_supported_languages(),
        "auto_detect": True,
    }


@router.post("/detect")
def detect_language(body: DetectRequest, db: Session = Depends(get_db)):
    """Detect the language of a document based on its text content.

    First checks existing OCR regions for text, then falls back to
    extracting text directly from the file. Uses character-range
    heuristics for detection.

    Returns:
        Dict with detected_language, confidence, language_name, and source.
    """
    document = db.query(Document).filter(Document.id == body.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Try to detect from existing regions first
    from backend.models.region import Region, RegionType

    regions = (
        db.query(Region)
        .filter(
            Region.document_id == body.document_id,
            Region.region_type == RegionType.TEXT,
            Region.original_text.isnot(None),
            Region.original_text != "",
        )
        .all()
    )

    if regions:
        text_regions = [{"text": r.original_text} for r in regions]
        result = language_service.detect_language_from_document_text(text_regions)
        lang_name = language_service.get_language_name(result["language_code"]) or result["language_code"]
        return {
            "detected_language": result["language_code"],
            "confidence": round(result["confidence"], 2),
            "language_name": lang_name,
            "source": "regions",
        }

    # No regions with text — extract text from the file directly
    file_path = settings.UPLOAD_DIR / document.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    extracted_text = ""

    if document.doc_type == DocumentType.PDF:
        try:
            import fitz

            doc = fitz.open(str(file_path))
            # Sample first few pages for detection (performance)
            pages_to_sample = min(len(doc), 3)
            for page_num in range(pages_to_sample):
                page = doc[page_num]
                extracted_text += page.get_text()
            doc.close()
        except Exception:
            logger.exception("Failed to extract text from PDF for language detection")
    else:
        # For images, try OCR text extraction
        try:
            from backend.services.ocr_service import detect_text_regions

            ocr_regions = detect_text_regions(str(file_path))
            extracted_text = " ".join(r.get("text", "") for r in ocr_regions)
        except Exception:
            logger.exception("Failed to extract text from image for language detection")

    if not extracted_text.strip():
        return {
            "detected_language": "en",
            "confidence": 0.0,
            "language_name": "English",
            "source": "none",
        }

    result = language_service.detect_language(extracted_text)
    lang_name = language_service.get_language_name(result["language_code"]) or result["language_code"]
    return {
        "detected_language": result["language_code"],
        "confidence": round(result["confidence"], 2),
        "language_name": lang_name,
        "source": "file",
    }
