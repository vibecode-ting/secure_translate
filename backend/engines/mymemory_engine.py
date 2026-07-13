"""Free translation engine using MyMemory API (no API key required)."""

import logging
import time
import requests

from .base import TranslationEngine

logger = logging.getLogger(__name__)

# Map our language codes to MyMemory codes
LANG_MAP = {
    "en": "en",
    "my": "my",
    "zh-Hans": "zh-CN",
    "zh-Hant": "zh-TW",
    "vi": "vi",
    "km": "km",
    "id": "id",
    "ja": "ja",
    "ko": "ko",
    "th": "th",
}


class MyMemoryEngine(TranslationEngine):
    """Free translation engine using MyMemory API.

    No API key required. Limited to ~5000 chars/day for anonymous use.
    Good for testing and small documents.
    """

    def __init__(self):
        self.endpoint = "https://api.mymemory.translated.net/get"

    def get_name(self) -> str:
        return "mymemory"

    def _resolve_language(self, code: str) -> str:
        return LANG_MAP.get(code, code)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return ""

        source = self._resolve_language(source_lang)
        target = self._resolve_language(target_lang)

        try:
            response = requests.get(
                self.endpoint,
                params={
                    "q": text,
                    "langpair": f"{source}|{target}",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("responseStatus") == 200:
                translated = data["responseData"]["translatedText"]
                logger.info("MyMemory: '%s' -> '%s'", text[:40], translated[:40])
                return translated
            else:
                logger.warning("MyMemory error: %s", data.get("responseDetails"))
                return text

        except Exception as e:
            logger.error("MyMemory API error: %s", e)
            return text

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        # MyMemory doesn't support batch, translate one by one
        results = []
        for text in texts:
            translated = self.translate(text, source_lang, target_lang)
            results.append(translated)
            time.sleep(0.5)  # Rate limiting
        return results
