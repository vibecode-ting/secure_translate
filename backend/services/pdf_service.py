"""PDF service — text extraction, rendering, and in-place translation using PyMuPDF."""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text extraction
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
# In-place text replacement
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
                    # Text overflow — shrink font and retry
                    fontsize = round(fontsize * 0.85, 1)
                    logger.debug(
                        "Text overflow on page %d, shrinking font to %.1f",
                        page_num, fontsize,
                    )

        doc.save(output_path, garbage=4, deflate=True)
        logger.info("Saved translated PDF to %s", output_path)

    finally:
        doc.close()
