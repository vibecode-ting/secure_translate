"""Celery task for document translation — the main processing pipeline."""

import logging
import traceback
from datetime import datetime, timezone

from backend.tasks.celery_app import celery_app
from backend.config import settings
from backend.database import SessionLocal
from backend.models.document import Document, DocumentStatus, DocumentType
from backend.models.region import Region, RegionType
from backend.models.job import TranslationJob, JobStatus

logger = logging.getLogger(__name__)


def _get_engine(engine_name: str):
    """Instantiate the requested translation engine with API keys from config."""
    if engine_name == "gemini":
        from backend.engines.gemini_engine import GeminiEngine
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured in .env")
        return GeminiEngine(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    elif engine_name == "azure":
        from backend.engines.azure_engine import AzureEngine
        if not settings.AZURE_TRANSLATOR_KEY:
            raise ValueError("AZURE_TRANSLATOR_KEY not configured in .env")
        return AzureEngine(api_key=settings.AZURE_TRANSLATOR_KEY, region=settings.AZURE_TRANSLATOR_REGION or "")
    elif engine_name == "google":
        from backend.engines.google_engine import GoogleEngine
        if not settings.GOOGLE_TRANSLATE_API_KEY:
            raise ValueError("GOOGLE_TRANSLATE_API_KEY not configured in .env")
        return GoogleEngine(api_key=settings.GOOGLE_TRANSLATE_API_KEY, project_id=settings.GOOGLE_PROJECT_ID)
    elif engine_name == "mymemory":
        from backend.engines.mymemory_engine import MyMemoryEngine
        return MyMemoryEngine()
    else:
        raise ValueError(f"Unknown translation engine: {engine_name}")


def _get_exclusion_filter():
    """Get the security service for filtering exclusion zones."""
    try:
        from backend.services.security_service import SecurityService
        return SecurityService()
    except ImportError:
        # Fallback: no security service, exclusion filtering done inline
        return None


def _filter_exclusion_zones(regions: list[Region], security_service) -> list[Region]:
    """Remove exclusion zones and overlapping regions from the list."""
    exclusion_zones = [r for r in regions if r.region_type == RegionType.EXCLUSION]
    text_regions = [r for r in regions if r.region_type == RegionType.TEXT]

    if not exclusion_zones:
        return text_regions

    if security_service is not None:
        return security_service.filter_excluded_regions(text_regions, exclusion_zones)

    # Inline fallback: remove text regions that overlap with any exclusion zone
    filtered = []
    for text_r in text_regions:
        excluded = False
        for excl in exclusion_zones:
            if _regions_overlap(text_r, excl):
                excluded = True
                break
        if not excluded:
            filtered.append(text_r)
    return filtered


def _regions_overlap(r1, r2) -> bool:
    """Check if two regions overlap (both on same page)."""
    if r1.page_number != r2.page_number:
        return False
    return not (
        r1.x + r1.width < r2.x
        or r2.x + r2.width < r1.x
        or r1.y + r1.height < r2.y
        or r2.y + r2.height < r1.y
    )


def _process_pdf_page(
    page_number: int,
    file_path: str,
    regions: list[Region],
    engine,
    source_lang: str,
    target_lang: str,
) -> list[dict]:
    """Process a single PDF page: translate text from regions."""
    results = []

    for region in regions:
        # Use the original_text from OCR detection
        text = region.original_text or ""
        if not text.strip():
            continue

        # Translate the text
        try:
            translated = engine.translate(text, source_lang, target_lang)
        except Exception as e:
            logger.warning("Translation failed for region %s: %s", region.id, e)
            translated = text  # Fallback to original

        # Save translation to the region
        region.translated_text = translated

        results.append({
            "region_id": region.id,
            "original_text": text,
            "translated_text": translated,
            "page_number": page_number,
        })

    return results


def _process_image_page(
    page_number: int,
    file_path: str,
    regions: list[Region],
    engine,
    source_lang: str,
    target_lang: str,
) -> list[dict]:
    """Process a single image page: paint-over original text, render translated text."""
    try:
        from backend.services.image_service import ImageService
        image_service = ImageService()
        return image_service.process_page(
            file_path=file_path,
            page_number=page_number,
            regions=regions,
            engine=engine,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except ImportError:
        # Fallback: use Pillow for paint-over + text rendering
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(file_path)
        draw = ImageDraw.Draw(img)
        results = []

        for region in regions:
            if region.original_text:
                # Translate existing text
                translated = engine.translate(region.original_text, source_lang, target_lang)
            else:
                # Extract text from region area using OCR if available
                try:
                    from backend.services.ocr_service import extract_text_from_region
                    text = extract_text_from_region(file_path, region)
                    translated = engine.translate(text, source_lang, target_lang) if text else ""
                    region.original_text = text
                except ImportError:
                    continue

            if region.translated_text or translated:
                actual_translated = translated or region.translated_text
                region.translated_text = actual_translated

                # Paint over original area with white
                draw.rectangle(
                    [region.x, region.y, region.x + region.width, region.y + region.height],
                    fill="white",
                )

                # Render translated text
                font_size = int(region.font_size) if region.font_size else 16
                try:
                    font = ImageFont.truetype(str(settings.FONT_DIR / "default.ttf"), font_size)
                except (OSError, IOError):
                    font = ImageFont.load_default()

                draw.text(
                    (region.x, region.y),
                    actual_translated,
                    fill="black",
                    font=font,
                )

                results.append({
                    "region_id": region.id,
                    "original_text": region.original_text,
                    "translated_text": actual_translated,
                    "page_number": page_number,
                })

        return results


def run_translation_sync(job_id: str):
    """Run the translation pipeline synchronously (without Celery)."""
    return _execute_translation(job_id)


@celery_app.task(bind=True, name="translate_document")
def translate_document(self, job_id: str):
    """Celery wrapper for the translation pipeline."""
    return _execute_translation(job_id)


def _execute_translation(job_id: str):
    """
    Main translation pipeline.

    1. Load document and regions from DB
    2. Filter out exclusion zones
    3. For each page, extract/translate text based on document type
    4. Update job progress after each page
    5. Save output file
    6. Update job status to COMPLETED
    """
    db = SessionLocal()

    try:
        # Load job and document
        job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
        if not job:
            return {"error": f"Job {job_id} not found"}

        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.status = JobStatus.FAILED
            job.error_message = "Document not found"
            db.commit()
            return {"error": "Document not found"}

        # Mark job as running
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.TRANSLATING
        db.commit()

        # Load all regions for this document
        all_regions = (
            db.query(Region)
            .filter(Region.document_id == document.id)
            .all()
        )

        # Filter out exclusion zones
        security_service = _get_exclusion_filter()
        text_regions = _filter_exclusion_zones(all_regions, security_service)

        # Initialize translation engine
        engine = _get_engine(job.engine)

        file_path = str(settings.UPLOAD_DIR / document.filename)
        total_pages = document.page_count
        all_results = []

        # Process each page
        for page_num in range(total_pages):
            # Check if job was cancelled
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                return {"status": "cancelled", "pages_completed": job.pages_completed}

            # Get regions for this page
            page_regions = [r for r in text_regions if r.page_number == page_num]

            if not page_regions:
                # No text regions on this page, just count it as done
                job.pages_completed = page_num + 1
                job.progress = (page_num + 1) / total_pages
                db.commit()
                continue

            # Process based on document type
            if document.doc_type == DocumentType.PDF:
                page_results = _process_pdf_page(
                    page_number=page_num,
                    file_path=file_path,
                    regions=page_regions,
                    engine=engine,
                    source_lang=job.source_language,
                    target_lang=job.target_language,
                )
            else:
                page_results = _process_image_page(
                    page_number=page_num,
                    file_path=file_path,
                    regions=page_regions,
                    engine=engine,
                    source_lang=job.source_language,
                    target_lang=job.target_language,
                )

            all_results.extend(page_results)

            # Flush region translations to DB (so _save_pdf_output can use them)
            db.flush()

            # Update progress
            job.pages_completed = page_num + 1
            job.progress = (page_num + 1) / total_pages
            document.progress = job.progress
            db.commit()

        # Save output file
        if document.doc_type == DocumentType.PDF:
            output_filename = _save_pdf_output(document, all_regions, job)
        else:
            output_filename = _save_image_output(document, all_regions, job)

        # Mark completed
        job.status = JobStatus.COMPLETED
        job.progress = 1.0
        job.output_filename = output_filename
        job.completed_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.COMPLETED
        document.progress = 1.0
        db.commit()

        return {
            "status": "completed",
            "job_id": job_id,
            "output_filename": output_filename,
            "pages_processed": total_pages,
            "regions_translated": len(all_results),
        }

    except Exception as e:
        # Mark job as failed
        try:
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"{str(e)}\n{traceback.format_exc()}"
                job.completed_at = datetime.now(timezone.utc)
                if document:
                    document.status = DocumentStatus.FAILED
                    document.error_message = str(e)
                db.commit()
        except Exception:
            pass  # Don't mask the original error

        raise

    finally:
        db.close()


def _save_pdf_output(document: Document, regions: list[Region], job: TranslationJob) -> str:
    """Save translated PDF using the production rewrite pipeline."""
    from backend.services.pdf_service import (
        extract_paragraphs_from_pdf,
        rewrite_pdf_with_translations,
    )

    file_path = str(settings.UPLOAD_DIR / document.filename)
    output_filename = f"translated_{job.id}_{document.original_filename}"
    output_path = str(settings.OUTPUT_DIR / output_filename)

    # Extract paragraphs from the original PDF
    paragraphs = extract_paragraphs_from_pdf(file_path)

    # Build translations dict from regions (region.original_text -> region.translated_text)
    translations = {}
    for region in regions:
        if region.original_text and region.translated_text:
            translations[region.original_text] = region.translated_text

    # Use the production rewrite pipeline
    font_path = str(settings.FONT_DIR / "NotoSans-Regular.ttf")
    rewrite_pdf_with_translations(
        pdf_path=file_path,
        paragraphs=paragraphs,
        translations=translations,
        output_path=output_path,
        font_path=font_path,
        target_lang=job.target_language,
    )

    return output_filename


def _save_image_output(document: Document, regions: list[Region], job: TranslationJob) -> str:
    """Save translated image with text replacements."""
    from PIL import Image, ImageDraw, ImageFont

    file_path = str(settings.UPLOAD_DIR / document.filename)
    output_filename = f"translated_{job.id}_{document.original_filename}"
    output_path = str(settings.OUTPUT_DIR / output_filename)

    try:
        from backend.services.image_service import ImageService
        image_service = ImageService()
        image_service.save_translated(
            file_path=file_path,
            regions=regions,
            output_path=output_path,
        )
    except ImportError:
        # Fallback: Pillow-based rendering
        img = Image.open(file_path)
        draw = ImageDraw.Draw(img)

        translated_regions = [r for r in regions if r.translated_text and r.page_number == 0]

        for region in translated_regions:
            # Paint over original
            draw.rectangle(
                [region.x, region.y, region.x + region.width, region.y + region.height],
                fill="white",
            )
            # Draw translated text
            font_size = int(region.font_size) if region.font_size else 16
            try:
                font = ImageFont.truetype(str(settings.FONT_DIR / "default.ttf"), font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

            draw.text(
                (region.x, region.y),
                region.translated_text,
                fill="black",
                font=font,
            )

        img.save(output_path)

    return output_filename
