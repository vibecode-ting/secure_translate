"""OCR service — text detection and recognition using RapidOCR."""

import logging
from typing import Optional

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from backend.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — RapidOCR loads ONNX models once and reuses them.
_ocr_engine: Optional[RapidOCR] = None


def _get_ocr() -> RapidOCR:
    """Lazy-initialize the RapidOCR engine."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR(
            lang=settings.OCR_LANGUAGES,
            use_cuda=settings.OCR_USE_GPU,
        )
        logger.info("RapidOCR engine initialized (lang=%s)", settings.OCR_LANGUAGES)
    return _ocr_engine


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_raw_results(raw_results: list) -> list[dict]:
    """Convert RapidOCR raw output into a list of region dicts.

    RapidOCR returns a list of tuples: (bbox, text, confidence)
    where bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].

    Each returned dict has keys:
        x, y, width, height, text, confidence, font_size
    """
    if not raw_results:
        return []

    regions: list[dict] = []
    for bbox, text, confidence in raw_results:
        if confidence < 0.5:
            continue

        # Bounding box from RapidOCR: 4 corner points
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        width = x_max - x_min
        height = y_max - y_min

        if width <= 0 or height <= 0:
            continue

        # Estimate font size from bbox height (rough heuristic)
        font_size = round(height * 0.75, 1)

        regions.append({
            "x": round(x_min, 1),
            "y": round(y_min, 1),
            "width": round(width, 1),
            "height": round(height, 1),
            "text": text.strip(),
            "confidence": round(confidence, 4),
            "font_size": font_size,
        })

    return regions


def _group_into_paragraphs(regions: list[dict], line_gap_ratio: float = 0.6) -> list[dict]:
    """Group nearby text lines into paragraph blocks.

    Two consecutive lines are merged if the vertical gap between them
    is smaller than ``line_gap_ratio`` times the average line height.

    Merged regions get their text joined with newlines and their bounding
    box expanded to cover all constituent lines.
    """
    if not regions:
        return []

    # Sort top-to-bottom, then left-to-right
    sorted_regions = sorted(regions, key=lambda r: (r["y"], r["x"]))

    paragraphs: list[dict] = [dict(sorted_regions[0])]

    for region in sorted_regions[1:]:
        prev = paragraphs[-1]

        prev_bottom = prev["y"] + prev["height"]
        gap = region["y"] - prev_bottom
        avg_height = (prev["height"] + region["height"]) / 2.0

        # Check horizontal proximity: regions should overlap horizontally
        # or at least be close to the same x-range to be considered the
        # same paragraph.
        prev_cx = prev["x"] + prev["width"] / 2
        curr_cx = region["x"] + region["width"] / 2
        horizontal_close = abs(prev_cx - curr_cx) < max(prev["width"], region["width"]) * 1.5

        if gap <= avg_height * line_gap_ratio and horizontal_close:
            # Merge into the current paragraph
            new_x = min(prev["x"], region["x"])
            new_y = min(prev["y"], region["y"])
            new_right = max(prev["x"] + prev["width"], region["x"] + region["width"])
            new_bottom = max(prev_bottom, region["y"] + region["height"])

            prev["x"] = round(new_x, 1)
            prev["y"] = round(new_y, 1)
            prev["width"] = round(new_right - new_x, 1)
            prev["height"] = round(new_bottom - new_y, 1)
            prev["text"] = prev["text"] + "\n" + region["text"]
            prev["confidence"] = round(
                min(prev["confidence"], region["confidence"]), 4
            )
            # Re-estimate font size from the merged height
            prev["font_size"] = round(prev["height"] * 0.75 / max(prev["text"].count("\n"), 1), 1)
        else:
            paragraphs.append(dict(region))

    return paragraphs


def _run_ocr(image: Image.Image) -> list[dict]:
    """Run OCR on a PIL Image and return grouped paragraph regions."""
    ocr = _get_ocr()

    # RapidOCR expects a numpy array (H, W, C) in BGR or RGB
    img_array = np.array(image.convert("RGB"))

    result, _ = ocr(img_array)
    regions = _parse_raw_results(result)
    paragraphs = _group_into_paragraphs(regions)

    logger.debug("OCR detected %d raw lines -> %d paragraph blocks", len(regions), len(paragraphs))
    return paragraphs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_text_regions(image_path: str) -> list[dict]:
    """Detect text regions in an image file.

    Args:
        image_path: Path to the image file on disk.

    Returns:
        List of region dicts with keys:
            x, y, width, height, text, confidence, font_size
    """
    try:
        image = Image.open(image_path)
        return _run_ocr(image)
    except Exception:
        logger.exception("OCR failed for image: %s", image_path)
        return []


def detect_text_regions_from_pil(image: Image.Image) -> list[dict]:
    """Detect text regions from an in-memory PIL Image.

    Args:
        image: A PIL Image object.

    Returns:
        List of region dicts with keys:
            x, y, width, height, text, confidence, font_size
    """
    try:
        return _run_ocr(image)
    except Exception:
        logger.exception("OCR failed for PIL image")
        return []
