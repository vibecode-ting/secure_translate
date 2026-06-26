"""Image service — paint over original text and render translations onto images."""

import logging
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font, falling back to the default bitmap font."""
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        logger.warning("Could not load font %s at size %d, using default", font_path, size)
        return ImageFont.load_default()


def _calculate_font_size(
    text: str,
    region: dict,
    font_path: str,
    max_font_size: Optional[float] = None,
) -> int:
    """Find the largest font size that fits ``text`` inside ``region``.

    Starts at region height * 0.7 and decreases until the text fits
    both width and height constraints.
    """
    region_w = region["width"]
    region_h = region["height"]

    # Start from region height * 0.7, capped at max_font_size if given
    start_size = int(region_h * 0.7)
    if max_font_size:
        start_size = min(start_size, int(max_font_size))
    start_size = max(start_size, 8)  # never go below 8px

    for size in range(start_size, 7, -1):
        font = _load_font(font_path, size)

        # Wrap text to fit region width
        wrapped = _wrap_text(text, font, region_w)
        bbox = font.getbbox(wrapped)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        if text_w <= region_w and text_h <= region_h:
            return size

    return 8  # absolute minimum


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Word-wrap ``text`` so each line fits within ``max_width`` pixels."""
    words = text.split()
    if not words:
        return text

    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def paint_over_region(
    image: Image.Image,
    region: dict,
    color: tuple = (255, 255, 255),
) -> Image.Image:
    """Fill a bounding box with a solid color.

    This is used to cover original text before rendering the translation.

    Args:
        image: Source PIL Image (will be copied).
        region: Dict with x, y, width, height keys.
        color: RGB fill color (default white).

    Returns:
        New Image with the region painted over.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    x = int(region["x"])
    y = int(region["y"])
    x2 = x + int(region["width"])
    y2 = y + int(region["height"])

    draw.rectangle([x, y, x2, y2], fill=color)
    return result


def render_text_on_image(
    image: Image.Image,
    text: str,
    region: dict,
    font_path: str,
    font_size: float = None,
    text_color: tuple = (0, 0, 0),
) -> Image.Image:
    """Render translated text into a region on the image.

    The original region area is painted white first, then the translated
    text is drawn with word-wrapping and vertical centering.

    Args:
        image: Source PIL Image (will be copied).
        text: Translated text to render.
        region: Dict with x, y, width, height keys.
        font_path: Path to a .ttf font file.
        font_size: Font size in pixels. Auto-calculated from region height if None.
        text_color: RGB text color (default black).

    Returns:
        New Image with the text rendered.
    """
    if not text.strip():
        return image.copy()

    result = image.copy()
    draw = ImageDraw.Draw(result)

    # Paint over original content
    x = int(region["x"])
    y = int(region["y"])
    region_w = int(region["width"])
    region_h = int(region["height"])
    x2 = x + region_w
    y2 = y + region_h

    draw.rectangle([x, y, x2, y2], fill=(255, 255, 255))

    # Determine font size
    if font_size and font_size > 0:
        size = int(font_size)
    else:
        size = _calculate_font_size(text, region, font_path)

    font = _load_font(font_path, size)

    # Wrap text to fit the region width
    wrapped = _wrap_text(text, font, region_w)

    # Calculate vertical offset to center text in the region
    bbox = font.getbbox(wrapped)
    text_h = bbox[3] - bbox[1]
    vertical_offset = max(0, (region_h - text_h) // 2)

    draw.text(
        (x, y + vertical_offset),
        wrapped,
        fill=text_color,
        font=font,
    )

    return result


def composite_page(
    original: Image.Image,
    regions: list[dict],
    translations: dict[str, str],
    font_path: str,
) -> Image.Image:
    """Full compositing pipeline for one page.

    For each text region that has a translation:
    1. Paint over the original text area (white fill).
    2. Render the translated text with auto-sized font and word-wrapping.

    Args:
        original: The original page image.
        regions: List of region dicts with x, y, width, height, text.
        translations: Mapping of original_text -> translated_text.
        font_path: Path to a .ttf font file.

    Returns:
        New Image with all translations composited.
    """
    result = original.copy()

    for region in regions:
        original_text = region.get("text", "").strip()
        translated = translations.get(original_text, "").strip()

        if not translated:
            continue

        try:
            result = render_text_on_image(
                image=result,
                text=translated,
                region=region,
                font_path=font_path,
            )
        except Exception:
            logger.exception(
                "Failed to render text for region at (%s, %s)",
                region.get("x"), region.get("y"),
            )

    return result
