import logging
import time

import requests

from .base import TranslationEngine

logger = logging.getLogger(__name__)

# Google Cloud Translation v3 uses BCP-47 codes.
GOOGLE_LANGUAGE_MAP = {
    "en": "en",
    "my": "my",
    "zh-Hans": "zh-Hans",
    "zh-Hant": "zh-Hant",
    "vi": "vi",
    "km": "km",
    "id": "id",
}

V2_ENDPOINT = "https://www.googleapis.com/language/translate/v2"
V3_ENDPOINT_TEMPLATE = (
    "https://translation.googleapis.com/v3/projects/"
    "{project_id}/locations/global:translateText"
)


class GoogleEngine(TranslationEngine):
    """Translation engine using Google Cloud Translation API (v2 or v3)."""

    def __init__(self, api_key: str, project_id: str = None):
        self.api_key = api_key
        self.project_id = project_id
        # Use v3 when project_id is provided, otherwise fall back to v2 simple mode
        self.use_v3 = project_id is not None

    def get_name(self) -> str:
        return "google-translate-v3" if self.use_v3 else "google-translate-v2"

    def _resolve_language(self, code: str) -> str:
        """Map a language code to Google's expected format."""
        if code in GOOGLE_LANGUAGE_MAP:
            return GOOGLE_LANGUAGE_MAP[code]
        return code

    def _call_with_retry(
        self, method: str, url: str, **kwargs
    ) -> dict:
        """Call Google API with exponential backoff on rate limit errors."""
        retries = 3
        last_exception = None
        for attempt in range(retries):
            try:
                response = requests.request(method, url, timeout=30, **kwargs)
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Google rate limit (attempt %d/%d), retrying in %ds",
                        attempt + 1, retries, wait_time,
                    )
                    time.sleep(wait_time)
                    last_exception = RuntimeError(
                        f"Google 429: {response.text}"
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error("Google API request error: %s", e)
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        raise RuntimeError(
            f"Google API failed after {retries} retries: {last_exception}"
        )

    # ------------------------------------------------------------------
    # v2 simple API key mode
    # ------------------------------------------------------------------

    def _translate_v2(self, text: str, source: str, target: str) -> str:
        params = {
            "key": self.api_key,
            "q": text,
            "source": source,
            "target": target,
        }
        result = self._call_with_retry("POST", V2_ENDPOINT, data=params)
        return result["data"]["translations"][0]["translatedText"]

    def _translate_batch_v2(
        self, texts: list[str], source: str, target: str
    ) -> list[str]:
        params = {
            "key": self.api_key,
            "q": texts,
            "source": source,
            "target": target,
        }
        result = self._call_with_retry("POST", V2_ENDPOINT, data=params)
        return [t["translatedText"] for t in result["data"]["translations"]]

    # ------------------------------------------------------------------
    # v3 project-based API
    # ------------------------------------------------------------------

    def _translate_v3(self, text: str, source: str, target: str) -> str:
        url = V3_ENDPOINT_TEMPLATE.format(project_id=self.project_id)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-goog-user-project": self.project_id,
        }
        body = {
            "contents": [text],
            "targetLanguageCode": target,
            "sourceLanguageCode": source,
            "mimeType": "text/plain",
        }
        result = self._call_with_retry("POST", url, headers=headers, json=body)
        return result["translations"][0]["translatedText"]

    def _translate_batch_v3(
        self, texts: list[str], source: str, target: str
    ) -> list[str]:
        url = V3_ENDPOINT_TEMPLATE.format(project_id=self.project_id)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-goog-user-project": self.project_id,
        }
        body = {
            "contents": texts,
            "targetLanguageCode": target,
            "sourceLanguageCode": source,
            "mimeType": "text/plain",
        }
        result = self._call_with_retry("POST", url, headers=headers, json=body)
        return [t["translatedText"] for t in result["translations"]]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text via Google Cloud Translation."""
        source = self._resolve_language(source_lang)
        target = self._resolve_language(target_lang)

        logger.info(
            "Google translating (%s -> %s, v%s): %.80s...",
            source_lang, target_lang, "3" if self.use_v3 else "2", text,
        )

        if self.use_v3:
            result = self._translate_v3(text, source, target)
        else:
            result = self._translate_v2(text, source, target)

        logger.info("Google result: %.80s...", result)
        return result

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of texts in a single Google request."""
        if not texts:
            return []

        source = self._resolve_language(source_lang)
        target = self._resolve_language(target_lang)

        logger.info(
            "Google batch translating %d segments (%s -> %s, v%s)",
            len(texts), source_lang, target_lang,
            "3" if self.use_v3 else "2",
        )

        if self.use_v3:
            translations = self._translate_batch_v3(texts, source, target)
        else:
            translations = self._translate_batch_v2(texts, source, target)

        logger.info("Google batch returned %d translations", len(translations))
        return translations
