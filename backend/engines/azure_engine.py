import logging
import time

import requests

from .base import TranslationEngine

logger = logging.getLogger(__name__)

# Azure uses the same codes we use, so no mapping needed.
# But we keep this dict for documentation and future extension.
AZURE_LANGUAGE_MAP = {
    "en": "en",
    "my": "my",
    "zh-Hans": "zh-Hans",
    "zh-Hant": "zh-Hant",
    "vi": "vi",
    "km": "km",
    "id": "id",
}


class AzureEngine(TranslationEngine):
    """Translation engine using Azure Translator REST API."""

    def __init__(
        self,
        api_key: str,
        region: str,
        endpoint: str = "https://api.cognitive.microsofttranslator.com",
    ):
        self.api_key = api_key
        self.region = region
        self.endpoint = endpoint.rstrip("/")

    def get_name(self) -> str:
        return "azure-translator"

    def _resolve_language(self, code: str) -> str:
        """Map a language code to Azure's expected format."""
        if code in AZURE_LANGUAGE_MAP:
            return AZURE_LANGUAGE_MAP[code]
        return code

    def _headers(self) -> dict:
        return {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
        }

    def _call_with_retry(
        self, url: str, body: list[dict], retries: int = 3
    ) -> list[dict]:
        """Call Azure Translator with retry on rate limit / transient errors."""
        last_exception = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    url,
                    headers=self._headers(),
                    json=body,
                    timeout=30,
                )
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Azure rate limit (attempt %d/%d), retrying in %ds",
                        attempt + 1, retries, wait_time,
                    )
                    time.sleep(wait_time)
                    last_exception = RuntimeError(
                        f"Azure 429: {response.text}"
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error("Azure API request error: %s", e)
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        raise RuntimeError(
            f"Azure API failed after {retries} retries: {last_exception}"
        )

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate a single text via Azure Translator."""
        source = self._resolve_language(source_lang)
        target = self._resolve_language(target_lang)

        url = (
            f"{self.endpoint}/translate"
            f"?api-version=3.0&from={source}&to={target}"
        )
        body = [{"text": text}]

        logger.info(
            "Azure translating (%s -> %s): %.80s...",
            source_lang, target_lang, text,
        )
        result = self._call_with_retry(url, body)
        translated = result[0]["translations"][0]["text"]
        logger.info("Azure result: %.80s...", translated)
        return translated

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of texts in a single Azure request."""
        if not texts:
            return []

        source = self._resolve_language(source_lang)
        target = self._resolve_language(target_lang)

        url = (
            f"{self.endpoint}/translate"
            f"?api-version=3.0&from={source}&to={target}"
        )
        body = [{"text": t} for t in texts]

        logger.info(
            "Azure batch translating %d segments (%s -> %s)",
            len(texts), source_lang, target_lang,
        )
        result = self._call_with_retry(url, body)

        translations = []
        for i, item in enumerate(result):
            translated = item["translations"][0]["text"]
            translations.append(translated)

        logger.info("Azure batch returned %d translations", len(translations))
        return translations
