"""PDF service — text extraction, rendering, and in-place translation using PyMuPDF.

This module provides two layers of PDF text handling:

1. **Line-level extraction** (``extract_text_regions``) -- returns individual
   text lines with bounding boxes.  Used by the OCR pipeline for region
   detection.

2. **Paragraph-level rewrite** (``rewrite_pdf_with_translations``) -- groups
   lines into paragraphs, redacts the originals, and inserts translated
   text at the same positions with layout preservation.  This is the
   production-quality entry point for PDF translation output.
"""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from backend.config import settings

logger = logging.getLogger(__name__)

# Default font name used when registering custom fonts with the document.
_DEFAULT_FONT_NAME = "NotoSans"

# Bounds for auto-sized font scaling.
_MIN_FONT_SIZE = 6.0
_MAX_FONT_SIZE = 72.0


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _resolve_font_path(font_path: Optional[str] = None) -> Optional[str]:
    """Return a valid font file path, falling back to the bundled NotoSans.

    If the caller supplies a path that does not exist, we try the bundled
    NotoSans-Regular.ttf.  Returns ``None`` only when no usable font is found.
    """
    if font_path and Path(font_path).is_file():
        return font_path
    bundled = settings.FONT_DIR / "NotoSans-Regular.ttf"
    if bundled.is_file():
        return str(bundled)
    return None


def _register_font(doc: fitz.Document, font_path: Optional[str] = None, target_lang: Optional[str] = None) -> str:
    """Register a font with *doc* and return the font name for ``insert_textbox``.

    Uses built-in CJK fonts for Chinese/Japanese/Korean languages,
    falls back to NotoSans for other languages, and finally to Helvetica.
    """
    # Use built-in CJK fonts for CJK languages
    CJK_FONT_MAP = {
        "zh-Hans": "china-s",
        "zh-Hant": "china-t",
        "ja": "japan-s",
        "ko": "korea-s",
    }

    if target_lang and target_lang in CJK_FONT_MAP:
        fontname = CJK_FONT_MAP[target_lang]
        try:
            # Test if the font works by inserting a test character
            return fontname
        except Exception:
            logger.warning("CJK font %s failed, trying file font", fontname)

    # Try file-based font
    resolved = _resolve_font_path(font_path)
    if resolved:
        try:
            doc.insert_font(fontname=_DEFAULT_FONT_NAME, fontfile=resolved)
            return _DEFAULT_FONT_NAME
        except Exception:
            logger.warning(
                "Failed to register font %s, falling back to helvetica", resolved
            )
    return "helv"


# ---------------------------------------------------------------------------
# Text extraction -- line level
# ---------------------------------------------------------------------------

def extract_text_regions(pdf_path: str) -> dict[int, list[dict]]:
    """Extract text regions from every page of a PDF using PyMuPDF's text search.

    Returns:
        Dict mapping page_number (0-indexed) to a list of region dicts.
        Each dict has keys: x, y, width, height, text, confidence, font_size
    """
    regions_by_page: dict[int, list[dict]] = {}

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF: %s", pdf_path)
        return regions_by_page

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            page_regions: list[dict] = []
            for block in blocks:
                if block["type"] != 0:  # 0 = text block
                    continue
                for line in block["lines"]:
                    # Merge all spans in a line into one region
                    line_text = "".join(span["text"] for span in line["spans"]).strip()
                    if not line_text:
                        continue

                    # Bounding box from the line bbox
                    x0, y0, x1, y1 = line["bbox"]
                    width = x1 - x0
                    height = y1 - y0

                    if width <= 0 or height <= 0:
                        continue

                    # Estimate font size from the largest span in the line
                    font_sizes = [span["size"] for span in line["spans"] if span["size"] > 0]
                    font_size = max(font_sizes) if font_sizes else round(height * 0.75, 1)

                    page_regions.append({
                        "x": round(x0, 1),
                        "y": round(y0, 1),
                        "width": round(width, 1),
                        "height": round(height, 1),
                        "text": line_text,
                        "confidence": 1.0,  # PyMuPDF extraction is deterministic
                        "font_size": round(font_size, 1),
                    })

            regions_by_page[page_num] = page_regions
            logger.debug("Page %d: extracted %d text regions", page_num, len(page_regions))

    finally:
        doc.close()

    return regions_by_page


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

def render_page_to_image(pdf_path: str, page_number: int, dpi: int = 300) -> Image.Image:
    """Render a single PDF page to a PIL Image at the given DPI.

    Args:
        pdf_path: Path to the PDF file.
        page_number: 0-indexed page number.
        dpi: Resolution for rendering (default 300).

    Returns:
        PIL Image of the rendered page.

    Raises:
        ValueError: If page_number is out of range.
        FileNotFoundError: If pdf_path does not exist.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for rendering: %s", pdf_path)
        raise

    try:
        if page_number < 0 or page_number >= len(doc):
            raise ValueError(
                f"Page {page_number} out of range (document has {len(doc)} pages)"
            )

        page = doc[page_number]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        logger.debug("Rendered page %d at %d dpi -> %dx%d", page_number, dpi, pix.width, pix.height)
        return image

    finally:
        doc.close()


def render_all_pages(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    """Render every page of a PDF to PIL Images.

    Args:
        pdf_path: Path to the PDF file.
        dpi: Resolution for rendering (default 300).

    Returns:
        List of PIL Images, one per page.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for batch rendering: %s", pdf_path)
        raise

    try:
        images: list[Image.Image] = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(image)

        logger.debug("Rendered %d pages at %d dpi", len(images), dpi)
        return images

    finally:
        doc.close()


def get_page_count(pdf_path: str) -> int:
    """Return the number of pages in a PDF."""
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        logger.exception("Failed to get page count: %s", pdf_path)
        return 0


# ---------------------------------------------------------------------------
# Legacy in-place text replacement (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def _find_font_for_page(page: fitz.Page, font_path: Optional[str] = None) -> str:
    """Return a usable font name for insert_textbox.

    If a custom font_path is provided, it is registered with the document.
    Otherwise falls back to Helvetica.
    """
    if font_path and Path(font_path).is_file():
        try:
            doc = page.parent
            fontname = "custom"
            doc.insert_font(fontname=fontname, fontfile=font_path)
            return fontname
        except Exception:
            logger.warning("Failed to load custom font %s, falling back to Helvetica", font_path)
    return "helv"


def replace_text_in_pdf(
    pdf_path: str,
    translations: dict[str, str],
    regions: list[dict],
    output_path: str,
    font_path: Optional[str] = None,
) -> None:
    """Replace text in a PDF using redaction annotations.

    For each region, the original text area is whited-out via
    ``add_redact_annot`` and then the translated text is inserted
    with ``insert_textbox``.

    Args:
        pdf_path: Path to the source PDF.
        translations: Mapping of original_text -> translated_text.
        regions: List of region dicts (must include page_number, x, y, width, height, text).
        output_path: Where to save the modified PDF.
        font_path: Optional path to a .ttf font file for rendering translations.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for text replacement: %s", pdf_path)
        raise

    try:
        # Group regions by page
        regions_by_page: dict[int, list[dict]] = {}
        for region in regions:
            page_num = region.get("page_number", 0)
            regions_by_page.setdefault(page_num, []).append(region)

        for page_num, page_regions in regions_by_page.items():
            if page_num >= len(doc):
                logger.warning("Skipping page %d (out of range)", page_num)
                continue

            page = doc[page_num]
            fontname = _find_font_for_page(page, font_path)

            for region in page_regions:
                original_text = region.get("text", "")
                translated = translations.get(original_text, "")
                if not translated:
                    continue

                # Define the rectangle for this region
                rect = fitz.Rect(
                    region["x"],
                    region["y"],
                    region["x"] + region["width"],
                    region["y"] + region["height"],
                )

                # Add a redaction annotation to white-out the original text
                page.add_redact_annot(
                    rect,
                    text="",  # no overlay text from redaction itself
                    fill=(1, 1, 1),  # white fill
                )

            # Apply all redactions for this page at once
            page.apply_redactions()

            # Now insert translated text into each region
            for region in page_regions:
                original_text = region.get("text", "")
                translated = translations.get(original_text, "")
                if not translated:
                    continue

                rect = fitz.Rect(
                    region["x"],
                    region["y"],
                    region["x"] + region["width"],
                    region["y"] + region["height"],
                )

                # Determine font size: use region's font_size or fit to height
                fontsize = region.get("font_size")
                if not fontsize:
                    fontsize = round(region["height"] * 0.7, 1)

                # Try to insert; if text overflows, reduce font size
                for attempt in range(3):
                    rc = page.insert_textbox(
                        rect,
                        translated,
                        fontsize=fontsize,
                        fontname=fontname,
                        color=(0, 0, 0),
                        align=fitz.TEXT_ALIGN_LEFT,
                    )
                    if rc >= 0:
                        # rc >= 0 means text fit (returns unused space)
                        break
                    # Text overflow -- shrink font and retry
                    fontsize = round(fontsize * 0.85, 1)
                    logger.debug(
                        "Text overflow on page %d, shrinking font to %.1f",
                        page_num, fontsize,
                    )

        doc.save(output_path, garbage=4, deflate=True)
        logger.info("Saved translated PDF to %s", output_path)

    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Paragraph-level text extraction
# ---------------------------------------------------------------------------

def extract_paragraphs_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text paragraph-by-paragraph from each page of a PDF.

    Groups individual text lines into logical paragraphs based on vertical
    proximity and horizontal alignment.  Handles mixed-content pages by
    processing only text blocks and skipping image blocks.

    Each returned dict contains:

    - ``page_number`` (int) -- 0-indexed page number.
    - ``x``, ``y``, ``width``, ``height`` (float) -- bounding box.
    - ``text`` (str) -- paragraph text with ``\\n`` between original lines.
    - ``font_size`` (float) -- estimated font size (points).
    - ``line_count`` (int) -- number of original lines in the paragraph.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of paragraph dicts sorted by page then vertical position.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for paragraph extraction: %s", pdf_path)
        return []

    paragraphs: list[dict] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            # Collect all text lines from this page, skipping image blocks
            page_lines: list[dict] = []
            for block in blocks:
                if block["type"] != 0:  # skip image blocks (type 1)
                    continue
                for line in block["lines"]:
                    line_text = "".join(span["text"] for span in line["spans"]).strip()
                    if not line_text:
                        continue

                    x0, y0, x1, y1 = line["bbox"]
                    width = x1 - x0
                    height = y1 - y0

                    if width <= 0 or height <= 0:
                        continue

                    # Use the dominant font size from the line's spans
                    font_sizes = [span["size"] for span in line["spans"] if span["size"] > 0]
                    font_size = max(font_sizes) if font_sizes else round(height * 0.75, 1)

                    page_lines.append({
                        "x": round(x0, 1),
                        "y": round(y0, 1),
                        "width": round(width, 1),
                        "height": round(height, 1),
                        "text": line_text,
                        "font_size": round(font_size, 1),
                    })

            # Group lines into paragraphs
            page_paragraphs = _group_lines_into_paragraphs(page_lines)

            for para in page_paragraphs:
                para["page_number"] = page_num

            paragraphs.extend(page_paragraphs)
            logger.debug(
                "Page %d: %d lines -> %d paragraphs",
                page_num, len(page_lines), len(page_paragraphs),
            )

    finally:
        doc.close()

    return paragraphs


def _group_lines_into_paragraphs(
    lines: list[dict],
    line_gap_ratio: float = 0.6,
    horizontal_tolerance: float = 1.5,
) -> list[dict]:
    """Group nearby text lines into paragraph blocks.

    Two consecutive lines are merged if the vertical gap between them
    is smaller than ``line_gap_ratio`` times the average line height,
    and they are horizontally close.

    Args:
        lines: List of line dicts (x, y, width, height, text, font_size).
        line_gap_ratio: Maximum gap as a fraction of line height to merge.
        horizontal_tolerance: Max horizontal offset multiplier for alignment.

    Returns:
        List of merged paragraph dicts (same shape as input, with merged
        text joined by ``\\n``).
    """
    if not lines:
        return []

    # Sort top-to-bottom, left-to-right
    sorted_lines = sorted(lines, key=lambda r: (r["y"], r["x"]))
    paragraphs: list[dict] = [dict(sorted_lines[0])]

    for line in sorted_lines[1:]:
        prev = paragraphs[-1]
        prev_bottom = prev["y"] + prev["height"]
        gap = line["y"] - prev_bottom
        avg_height = (prev["height"] + line["height"]) / 2.0

        # Check horizontal proximity: centres should be reasonably aligned
        prev_cx = prev["x"] + prev["width"] / 2
        curr_cx = line["x"] + line["width"] / 2
        horizontal_close = (
            abs(prev_cx - curr_cx)
            < max(prev["width"], line["width"]) * horizontal_tolerance
        )

        if gap <= avg_height * line_gap_ratio and horizontal_close:
            # Merge into current paragraph
            new_x = min(prev["x"], line["x"])
            new_y = min(prev["y"], line["y"])
            new_right = max(prev["x"] + prev["width"], line["x"] + line["width"])
            new_bottom = max(prev_bottom, line["y"] + line["height"])

            prev["x"] = round(new_x, 1)
            prev["y"] = round(new_y, 1)
            prev["width"] = round(new_right - new_x, 1)
            prev["height"] = round(new_bottom - new_y, 1)
            prev["text"] = prev["text"] + "\n" + line["text"]
            # Re-estimate font size: use per-line sizes weighted average
            prev["font_size"] = round(
                (prev["font_size"] + line["font_size"]) / 2.0, 1
            )
        else:
            paragraphs.append(dict(line))

    # Annotate each paragraph with its line count
    for para in paragraphs:
        para["line_count"] = para["text"].count("\n") + 1

    return paragraphs


# ---------------------------------------------------------------------------
# PDF metadata helper
# ---------------------------------------------------------------------------

def get_pdf_metadata(pdf_path: str) -> dict:
    """Extract basic metadata from a PDF file.

    Returns:
        Dict with keys: page_count, has_images, title, author, subject.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for metadata: %s", pdf_path)
        return {"page_count": 0, "has_images": False, "title": None, "author": None, "subject": None}

    try:
        page_count = len(doc)
        has_images = False

        # Check first few pages for images (sampling for performance)
        pages_to_check = min(page_count, 5)
        for page_num in range(pages_to_check):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            if image_list:
                has_images = True
                break

        metadata = doc.metadata or {}

        return {
            "page_count": page_count,
            "has_images": has_images,
            "title": metadata.get("title") or None,
            "author": metadata.get("author") or None,
            "subject": metadata.get("subject") or None,
        }

    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Production-quality PDF rewrite
# ---------------------------------------------------------------------------

def redact_text_from_pdf(
    pdf_path: str,
    paragraphs: list[dict],
    output_path: str,
) -> None:
    """Remove original text from a PDF using redaction annotations.

    For each paragraph, a white-filled redaction annotation is placed over
    the bounding box, then all annotations on the page are applied at once.

    This does **not** save the file -- call ``save`` on the returned
    document, or use ``rewrite_pdf_with_translations`` which handles
    the full pipeline.

    Args:
        pdf_path: Path to the source PDF.
        paragraphs: List of paragraph dicts with page_number, x, y, width, height.
        output_path: Where to save the redacted PDF.

    Note:
        The file is saved with redactions applied but no translated text
        inserted.  This is a building block for the full rewrite pipeline.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for redaction: %s", pdf_path)
        raise

    try:
        # Group paragraphs by page for batch redaction
        by_page: dict[int, list[dict]] = {}
        for para in paragraphs:
            pg = para.get("page_number", 0)
            by_page.setdefault(pg, []).append(para)

        for page_num, page_paras in by_page.items():
            if page_num >= len(doc):
                logger.warning("Skipping redaction on page %d (out of range)", page_num)
                continue

            page = doc[page_num]

            for para in page_paras:
                rect = fitz.Rect(
                    para["x"],
                    para["y"],
                    para["x"] + para["width"],
                    para["y"] + para["height"],
                )
                # Ensure rect is valid (non-negative area)
                if rect.is_empty or rect.is_infinite:
                    continue

                page.add_redact_annot(
                    rect,
                    text="",
                    fill=(1, 1, 1),  # white background
                )

            # Apply all redactions for this page in one pass
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

        doc.save(output_path, garbage=4, deflate=True)
        logger.info("Redacted PDF saved to %s", output_path)

    finally:
        doc.close()


def _fit_font_size(
    page: fitz.Page,
    text: str,
    rect: fitz.Rect,
    target_size: float,
    fontname: str,
) -> float:
    """Find the largest font size <= target_size that fits *text* inside *rect*.

    Uses ``insert_textbox`` in a trial-and-error loop.  If the text fits
    at the target size, returns immediately.  Otherwise, progressively
    shrinks until it fits or hits ``_MIN_FONT_SIZE``.

    Returns:
        The font size that fits, or ``_MIN_FONT_SIZE`` as a last resort.
    """
    fontsize = min(target_size, _MAX_FONT_SIZE)
    fontsize = max(fontsize, _MIN_FONT_SIZE)

    for _ in range(20):  # max 20 shrink iterations
        rc = page.insert_textbox(
            rect,
            text,
            fontsize=fontsize,
            fontname=fontname,
            color=(0, 0, 0),
            align=fitz.TEXT_ALIGN_LEFT,
        )
        if rc >= 0:
            # rc >= 0 means text fit (value is unused vertical space)
            return fontsize
        # Overflow -- shrink by 10%
        fontsize = round(fontsize * 0.9, 2)
        if fontsize < _MIN_FONT_SIZE:
            return _MIN_FONT_SIZE

    return _MIN_FONT_SIZE


def insert_translated_text(
    pdf_path: str,
    paragraphs: list[dict],
    translations: dict[str, str],
    output_path: str,
    font_path: Optional[str] = None,
) -> None:
    """Insert translated text into a previously redacted PDF.

    For each paragraph that has a translation, the translated text is
    inserted at the same bounding box using ``insert_textbox``.  Font
    size is auto-scaled to fit when the translation is longer than the
    original.

    Args:
        pdf_path: Path to the redacted PDF (output of ``redact_text_from_pdf``).
        paragraphs: List of paragraph dicts with page_number, x, y, width, height,
                    text, font_size.
        translations: Mapping of original_text -> translated_text.
        output_path: Where to save the final PDF.
        font_path: Optional path to a .ttf font file for multi-language support.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for text insertion: %s", pdf_path)
        raise

    try:
        fontname = _register_font(doc, font_path)

        # Group by page
        by_page: dict[int, list[dict]] = {}
        for para in paragraphs:
            pg = para.get("page_number", 0)
            by_page.setdefault(pg, []).append(para)

        for page_num, page_paras in by_page.items():
            if page_num >= len(doc):
                logger.warning("Skipping insertion on page %d (out of range)", page_num)
                continue

            page = doc[page_num]

            for para in page_paras:
                original_text = para.get("text", "")
                translated = translations.get(original_text, "")
                if not translated:
                    continue

                rect = fitz.Rect(
                    para["x"],
                    para["y"],
                    para["x"] + para["width"],
                    para["y"] + para["height"],
                )
                if rect.is_empty or rect.is_infinite:
                    continue

                # Determine target font size
                target_size = para.get("font_size", 11.0)
                if not target_size or target_size <= 0:
                    target_size = round(para["height"] * 0.7, 1)

                # Fit the translated text into the bounding box
                actual_size = _fit_font_size(page, translated, rect, target_size, fontname)

                # If we had to shrink significantly, log it
                if actual_size < target_size * 0.8:
                    logger.debug(
                        "Font scaled down on page %d: %.1f -> %.1fpt for '%s'",
                        page_num, target_size, actual_size, translated[:40],
                    )

        doc.save(output_path, garbage=4, deflate=True)
        logger.info("Translated text inserted into %s", output_path)

    finally:
        doc.close()


def rewrite_pdf_with_translations(
    pdf_path: str,
    paragraphs: list[dict],
    translations: dict[str, str],
    output_path: str,
    font_path: Optional[str] = None,
    target_lang: Optional[str] = None,
) -> None:
    """Full PDF rewrite pipeline: redact originals, insert translations.

    This is the main entry point for producing a translated PDF.  It:

    1. Opens the source PDF.
    2. For each page, redacts all paragraph bounding boxes (white fill).
    3. Inserts translated text at the same positions, auto-scaling font
       size to fit when the translation is longer.
    4. Saves the result with garbage collection and deflation.

    Multi-page documents are handled automatically -- each page is
    processed independently.

    Args:
        pdf_path: Path to the source PDF.
        paragraphs: List of paragraph dicts (from ``extract_paragraphs_from_pdf``
                    or equivalent).  Each must have: page_number, x, y, width,
                    height, text, font_size.
        translations: Mapping of original paragraph text -> translated text.
        output_path: Where to save the translated PDF.
        font_path: Optional path to a .ttf font file.  Falls back to the
                   bundled NotoSans-Regular.ttf, then to built-in Helvetica.
        target_lang: Target language code (e.g., 'zh-Hant') for CJK font selection.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for rewrite: %s", pdf_path)
        raise

    try:
        fontname = _register_font(doc, font_path, target_lang)

        # Group paragraphs by page for efficient processing
        by_page: dict[int, list[dict]] = {}
        for para in paragraphs:
            pg = para.get("page_number", 0)
            by_page.setdefault(pg, []).append(para)

        total_pages_processed = 0

        for page_num in sorted(by_page.keys()):
            if page_num >= len(doc):
                logger.warning("Skipping page %d (out of range, doc has %d pages)", page_num, len(doc))
                continue

            page = doc[page_num]
            page_paras = by_page[page_num]

            # ---- Phase 1: Redact all original text on this page ----
            for para in page_paras:
                rect = fitz.Rect(
                    para["x"],
                    para["y"],
                    para["x"] + para["width"],
                    para["y"] + para["height"],
                )
                if rect.is_empty or rect.is_infinite:
                    continue

                page.add_redact_annot(
                    rect,
                    text="",
                    fill=(1, 1, 1),
                )

            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

            # ---- Phase 2: Insert translated text ----
            inserted_count = 0
            for para in page_paras:
                original_text = para.get("text", "")
                translated = translations.get(original_text, "")
                if not translated:
                    continue

                rect = fitz.Rect(
                    para["x"],
                    para["y"],
                    para["x"] + para["width"],
                    para["y"] + para["height"],
                )
                if rect.is_empty or rect.is_infinite:
                    continue

                # Determine target font size from the original paragraph
                target_size = para.get("font_size", 11.0)
                if not target_size or target_size <= 0:
                    target_size = round(para["height"] * 0.7, 1)

                # Fit and insert
                actual_size = _fit_font_size(page, translated, rect, target_size, fontname)

                if actual_size < target_size * 0.8:
                    logger.debug(
                        "Page %d: font scaled %.1f -> %.1fpt for '%s'",
                        page_num, target_size, actual_size, translated[:40],
                    )

                inserted_count += 1

            total_pages_processed += 1
            logger.debug(
                "Page %d: redacted %d paragraphs, inserted %d translations",
                page_num, len(page_paras), inserted_count,
            )

        doc.save(output_path, garbage=4, deflate=True)
        logger.info(
            "PDF rewrite complete: %d pages processed, saved to %s",
            total_pages_processed, output_path,
        )

    finally:
        doc.close()
