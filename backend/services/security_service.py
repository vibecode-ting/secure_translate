"""Security service — ensures excluded regions are NEVER sent to external APIs.

This is the critical trust boundary.  Every function in this module is
designed to fail closed: if anything goes wrong, regions are excluded
rather than leaked.
"""

import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bounding-box geometry
# ---------------------------------------------------------------------------

def _bbox_overlap_area(r1: dict, r2: dict) -> float:
    """Calculate the overlap area between two bounding boxes.

    Each box is a dict with keys: x, y, width, height.
    Returns 0 if there is no overlap.
    """
    x_overlap_start = max(r1["x"], r2["x"])
    y_overlap_start = max(r1["y"], r2["y"])
    x_overlap_end = min(r1["x"] + r1["width"], r2["x"] + r2["width"])
    y_overlap_end = min(r1["y"] + r1["height"], r2["y"] + r2["height"])

    if x_overlap_end <= x_overlap_start or y_overlap_end <= y_overlap_start:
        return 0.0

    return (x_overlap_end - x_overlap_start) * (y_overlap_end - y_overlap_start)


def _bbox_area(box: dict) -> float:
    """Area of a bounding box."""
    return box["width"] * box["height"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def regions_overlap(r1: dict, r2: dict, threshold: float = 0.3) -> bool:
    """Check whether two bounding boxes overlap by more than ``threshold``.

    The threshold is relative to the *smaller* region's area, so a tiny
    exclusion zone can still block a large text region if they intersect
    significantly.

    Args:
        r1: First region dict with x, y, width, height.
        r2: Second region dict with x, y, width, height.
        threshold: Fraction of the smaller region that must overlap (default 0.3 = 30%).

    Returns:
        True if the overlap exceeds the threshold.
    """
    overlap = _bbox_overlap_area(r1, r2)
    if overlap <= 0:
        return False

    smaller_area = min(_bbox_area(r1), _bbox_area(r2))
    if smaller_area <= 0:
        return False

    return (overlap / smaller_area) > threshold


def filter_regions_for_translation(
    regions: list[dict],
    exclusion_zones: list[dict],
) -> list[dict]:
    """Remove any text region that overlaps with an exclusion zone.

    This is the primary gate that prevents sensitive content from being
    sent to external translation APIs.

    Args:
        regions: Text regions detected by OCR.
        exclusion_zones: User-marked exclusion zones (never translated).

    Returns:
        Filtered list containing only safe-to-translate regions.
    """
    if not exclusion_zones:
        return list(regions)

    safe_regions: list[dict] = []
    excluded_count = 0

    for region in regions:
        is_excluded = False
        for zone in exclusion_zones:
            if regions_overlap(region, zone):
                is_excluded = True
                excluded_count += 1
                logger.debug(
                    "Excluded region '%s' (overlaps with zone '%s')",
                    region.get("text", "")[:50],
                    zone.get("label", "unlabeled"),
                )
                break

        if not is_excluded:
            safe_regions.append(region)

    if excluded_count > 0:
        logger.info(
            "Security filter: excluded %d / %d regions (exclusion zones active)",
            excluded_count,
            len(regions),
        )

    return safe_regions


def crop_image_excluding_regions(
    image: Image.Image,
    regions: list[dict],
    exclusion_zones: list[dict],
) -> list[dict]:
    """Crop individual text region images, excluding any that overlap zones.

    For image-based documents where OCR is needed, this crops each allowed
    text region from the source image so only the text pixels are sent for
    translation — never pixels from exclusion zones.

    Args:
        image: The full page image.
        regions: Text region dicts with x, y, width, height.
        exclusion_zones: Exclusion zone dicts.

    Returns:
        List of dicts, each with the original region keys plus a
        ``crop`` key containing the cropped PIL Image.  Regions that
        overlap exclusion zones are omitted.
    """
    safe_regions = filter_regions_for_translation(regions, exclusion_zones)
    img_w, img_h = image.size

    cropped: list[dict] = []
    for region in safe_regions:
        # Clamp coordinates to image bounds
        x = max(0, int(region["x"]))
        y = max(0, int(region["y"]))
        x2 = min(img_w, int(region["x"] + region["width"]))
        y2 = min(img_h, int(region["y"] + region["height"]))

        if x2 <= x or y2 <= y:
            logger.warning("Skipping degenerate region at (%s, %s)", region["x"], region["y"])
            continue

        crop = image.crop((x, y, x2, y2))
        entry = dict(region)
        entry["crop"] = crop
        cropped.append(entry)

    logger.debug("Cropped %d / %d regions (exclusions removed)", len(cropped), len(regions))
    return cropped


def validate_no_exclusion_leak(
    regions: list[dict],
    exclusion_zones: list[dict],
) -> bool:
    """Verify that NO region overlaps with any exclusion zone.

    Call this as a safety check before sending regions to an external API.
    Returns True if it is safe to proceed, False if there is any overlap.

    Args:
        regions: Regions about to be sent for translation.
        exclusion_zones: All exclusion zones for the document.

    Returns:
        True if safe (no overlap), False if any overlap detected.
    """
    if not exclusion_zones:
        return True

    for region in regions:
        for zone in exclusion_zones:
            if regions_overlap(region, zone):
                logger.error(
                    "SECURITY VIOLATION: region '%s' overlaps exclusion zone '%s' — "
                    "blocking translation",
                    region.get("text", "")[:80],
                    zone.get("label", "unlabeled"),
                )
                return False

    return True
