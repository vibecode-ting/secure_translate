"""Services package."""

from backend.services.ocr_service import detect_text_regions, detect_text_regions_from_pil
from backend.services.pdf_service import (
    extract_text_regions,
    render_page_to_image,
    render_all_pages,
    replace_text_in_pdf,
    get_page_count,
)
from backend.services.image_service import (
    paint_over_region,
    render_text_on_image,
    composite_page,
)
from backend.services.security_service import (
    filter_regions_for_translation,
    crop_image_excluding_regions,
    validate_no_exclusion_leak,
    regions_overlap,
)
from backend.services.translation_service import TranslationPipeline

__all__ = [
    # OCR
    "detect_text_regions",
    "detect_text_regions_from_pil",
    # PDF
    "extract_text_regions",
    "render_page_to_image",
    "render_all_pages",
    "replace_text_in_pdf",
    "get_page_count",
    # Image
    "paint_over_region",
    "render_text_on_image",
    "composite_page",
    # Security
    "filter_regions_for_translation",
    "crop_image_excluding_regions",
    "validate_no_exclusion_leak",
    "regions_overlap",
    # Translation
    "TranslationPipeline",
]
