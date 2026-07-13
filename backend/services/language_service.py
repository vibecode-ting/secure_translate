"""Language detection service — character-range heuristics for supported languages."""

import logging
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# Supported languages with their codes and display names.
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "auto", "name": "Auto-detect"},
    {"code": "en", "name": "English"},
    {"code": "my", "name": "Burmese"},
    {"code": "zh-Hans", "name": "Simplified Chinese"},
    {"code": "zh-Hant", "name": "Traditional Chinese"},
    {"code": "vi", "name": "Vietnamese"},
    {"code": "km", "name": "Khmer"},
    {"code": "id", "name": "Indonesian"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "th", "name": "Thai"},
]

# Unicode ranges for CJK unification — used to distinguish Chinese variants.
_CJK_UNIFIED_START = 0x4E00
_CJK_UNIFIED_END = 0x9FFF
_CJK_EXTENSION_A_START = 0x3400
_CJK_EXTENSION_A_END = 0x4DBF
_CJK_EXTENSION_B_START = 0x20000
_CJK_EXTENSION_B_END = 0x2A6DF

# Hiragana + Katakana ranges for Japanese detection
_HIRAGANA_START = 0x3040
_HIRAGANA_END = 0x309F
_KATAKANA_START = 0x30A0
_KATAKANA_END = 0x30FF
_KATAKANA_EXT_START = 0x31F0
_KATAKANA_EXT_END = 0x31FF

# Hangul ranges for Korean detection
_HANGUL_START = 0xAC00
_HANGUL_END = 0xD7AF
_HANGUL_JAMO_START = 0x1100
_HANGUL_JAMO_END = 0x11FF

# Vietnamese uses Latin script with heavy diacritics — detect via common
# Vietnamese diacritical combinations
_VIETNAMESE_MARKS = set("ăâđêôơưĂÂĐÊÔƠƯ")

# Burmese/Myanmar script range
_MYANMAR_START = 0x1000
_MYANMAR_END = 0x109F

# Thai script range
_THAI_START = 0x0E00
_THAI_END = 0x0E7F

# Khmer script range
_KHMER_START = 0x1780
_KHMER_END = 0x17FF

# Latin script range (for English/Indonesian)
_LATIN_START = 0x0041
_LATIN_END = 0x024F


def detect_language(text: str) -> dict:
    """Detect the language of text using character-range heuristics.

    Examines the Unicode code points of non-whitespace characters and
    determines which script family dominates. Returns a language code
    and confidence score.

    Args:
        text: The text to analyze.

    Returns:
        Dict with keys:
            language_code (str): Detected language code (e.g., 'en', 'ja', 'zh-Hans').
            confidence (float): Confidence score between 0.0 and 1.0.
    """
    if not text or not text.strip():
        return {"language_code": "en", "confidence": 0.0}

    # Normalize text
    text = text.strip()
    total_chars = 0
    script_counts: dict[str, int] = {}

    for char in text:
        if char.isspace() or char in ".,;:!?-—()[]{}\"'0123456789/\\|@#$%^&*+=<>{}~`":
            continue

        total_chars += 1
        cp = ord(char)

        if _MYANMAR_START <= cp <= _MYANMAR_END:
            script_counts["my"] = script_counts.get("my", 0) + 1
        elif _THAI_START <= cp <= _THAI_END:
            script_counts["th"] = script_counts.get("th", 0) + 1
        elif _KHMER_START <= cp <= _KHMER_END:
            script_counts["km"] = script_counts.get("km", 0) + 1
        elif _HANGUL_START <= cp <= _HANGUL_END or _HANGUL_JAMO_START <= cp <= _HANGUL_JAMO_END:
            script_counts["ko"] = script_counts.get("ko", 0) + 1
        elif (_HIRAGANA_START <= cp <= _HIRAGANA_END or
              _KATAKANA_START <= cp <= _KATAKANA_END or
              _KATAKANA_EXT_START <= cp <= _KATAKANA_EXT_END):
            script_counts["ja"] = script_counts.get("ja", 0) + 1
        elif (_CJK_UNIFIED_START <= cp <= _CJK_UNIFIED_END or
              _CJK_EXTENSION_A_START <= cp <= _CJK_EXTENSION_A_END or
              _CJK_EXTENSION_B_START <= cp <= _CJK_EXTENSION_B_END):
            # CJK unified — could be Chinese, Japanese, or Korean
            # We'll refine after the initial pass
            script_counts["cjk"] = script_counts.get("cjk", 0) + 1
        elif _LATIN_START <= cp <= _LATIN_END:
            script_counts["latin"] = script_counts.get("latin", 0) + 1
        elif char in _VIETNAMESE_MARKS:
            script_counts["vi"] = script_counts.get("vi", 0) + 1

    if total_chars == 0:
        return {"language_code": "en", "confidence": 0.0}

    # Determine dominant script
    if not script_counts:
        return {"language_code": "en", "confidence": 0.3}

    dominant_script = max(script_counts, key=script_counts.get)
    dominant_count = script_counts[dominant_script]
    confidence = round(dominant_count / total_chars, 4)

    # Refine CJK detection
    if dominant_script == "cjk":
        # If there are also hiragana/katakana characters, it's likely Japanese
        if script_counts.get("ja", 0) > 0:
            # Mixed CJK + kana = Japanese
            total_ja = script_counts.get("cjk", 0) + script_counts.get("ja", 0)
            confidence = round(total_ja / total_chars, 4)
            return {"language_code": "ja", "confidence": min(confidence, 0.95)}

        # If there are also hangul characters, it's likely Korean
        if script_counts.get("ko", 0) > 0:
            total_ko = script_counts.get("cjk", 0) + script_counts.get("ko", 0)
            confidence = round(total_ko / total_chars, 4)
            return {"language_code": "ko", "confidence": min(confidence, 0.95)}

        # Pure CJK without kana/hangul — default to Simplified Chinese
        # (Traditional Chinese uses same range; a more sophisticated detector
        # would look at specific character variants, but this is a heuristic)
        return {"language_code": "zh-Hans", "confidence": min(confidence, 0.9)}

    # Vietnamese: Latin script with Vietnamese marks
    if dominant_script == "latin" and script_counts.get("vi", 0) > 0:
        vi_chars = script_counts.get("vi", 0)
        # If significant Vietnamese marks present, it's Vietnamese
        if vi_chars / total_chars > 0.02:
            return {"language_code": "vi", "confidence": min(confidence + 0.2, 0.95)}

    # Vietnamese: dominant script is vi marks themselves
    if dominant_script == "vi":
        return {"language_code": "vi", "confidence": min(confidence, 0.95)}

    # Pure Latin script — could be English or Indonesian
    # For now, default to English (Indonesian would need word-frequency analysis)
    if dominant_script == "latin":
        return {"language_code": "en", "confidence": min(confidence, 0.9)}

    # Direct script matches
    script_to_lang = {
        "my": "my",
        "th": "th",
        "km": "km",
        "ko": "ko",
        "ja": "ja",
    }
    if dominant_script in script_to_lang:
        return {"language_code": script_to_lang[dominant_script], "confidence": min(confidence, 0.95)}

    return {"language_code": "en", "confidence": 0.3}


def get_supported_languages() -> list[dict[str, str]]:
    """Return the list of supported languages with codes and names.

    Returns:
        List of dicts with 'code' and 'name' keys.
    """
    return SUPPORTED_LANGUAGES


def get_language_name(code: str) -> Optional[str]:
    """Look up a language name by its code.

    Args:
        code: Language code (e.g., 'en', 'zh-Hans').

    Returns:
        Language name or None if not found.
    """
    for lang in SUPPORTED_LANGUAGES:
        if lang["code"] == code:
            return lang["name"]
    return None


def detect_language_from_document_text(text_regions: list[dict]) -> dict:
    """Detect language from a collection of text regions (e.g., from OCR results).

    Concatenates all region texts and runs detection on the combined text.

    Args:
        text_regions: List of region dicts with 'text' keys.

    Returns:
        Dict with keys: language_code, confidence.
    """
    combined_text = " ".join(
        region.get("text", "") for region in text_regions if region.get("text")
    )
    return detect_language(combined_text)
