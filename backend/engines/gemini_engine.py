import logging
import time

import google.generativeai as genai

from .base import TranslationEngine

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "en": "English",
    "my": "Burmese",
    "zh-Hans": "Simplified Chinese",
    "zh-Hant": "Traditional Chinese",
    "vi": "Vietnamese",
    "km": "Khmer",
    "id": "Indonesian",
}

SEGMENT_MARKER = "---SEGMENT---"


class GeminiEngine(TranslationEngine):
    """Translation engine using Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config={"temperature": 0.1},
        )

    def get_name(self) -> str:
        return f"gemini-{self.model_name}"

    def _resolve_language(self, code: str) -> str:
        """Map a language code to its human-readable name."""
        if code in LANGUAGE_MAP:
            return LANGUAGE_MAP[code]
        return code

    def _call_with_backoff(self, prompt: str, retries: int = 3) -> str:
        """Call Gemini API with exponential backoff on rate limit errors."""
        last_exception = None
        for attempt in range(retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                if "429" in error_str or "rate" in error_str or "quota" in error_str:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Gemini rate limit hit (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1, retries, wait_time, e,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("Gemini API error: %s", e)
                    raise
        raise RuntimeError(
            f"Gemini API failed after {retries} retries: {last_exception}"
        )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text segment using Gemini."""
        source_name = self._resolve_language(source_lang)
        target_name = self._resolve_language(target_lang)

        prompt = (
            f"Translate the following text from {source_name} to {target_name}. "
            f"Output ONLY the translated text, no explanations or notes:\n\n{text}"
        )

        logger.info(
            "Gemini translating (%s -> %s): %.80s...",
            source_lang, target_lang, text,
        )
        result = self._call_with_backoff(prompt)
        logger.info("Gemini result: %.80s...", result)
        return result

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of texts in a single Gemini request."""
        if not texts:
            return []

        source_name = self._resolve_language(source_lang)
        target_name = self._resolve_language(target_lang)

        joined = f"\n{SEGMENT_MARKER}\n".join(texts)
        prompt = (
            f"Translate each of the following text segments from {source_name} to {target_name}. "
            f"The segments are separated by '{SEGMENT_MARKER}' markers. "
            f"Output ONLY the translated segments, separated by '{SEGMENT_MARKER}' markers, "
            f"in the same order. No explanations or notes:\n\n{joined}"
        )

        logger.info(
            "Gemini batch translating %d segments (%s -> %s)",
            len(texts), source_lang, target_lang,
        )
        response_text = self._call_with_backoff(prompt)

        # Split the response back into segments
        segments = [s.strip() for s in response_text.split(SEGMENT_MARKER)]
        segments = [s for s in segments if s]  # remove empties

        if len(segments) != len(texts):
            logger.warning(
                "Gemini batch returned %d segments but expected %d",
                len(segments), len(texts),
            )
            # Pad with empty strings if Gemini returned fewer segments
            while len(segments) < len(texts):
                segments.append("")

        return segments[:len(texts)]
