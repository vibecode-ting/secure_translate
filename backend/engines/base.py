from abc import ABC, abstractmethod


class TranslationEngine(ABC):
    """Base class for all translation engines."""

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language."""
        pass

    @abstractmethod
    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a batch of text segments."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return engine name."""
        pass

    def get_supported_languages(self) -> list[str]:
        """Return list of supported language codes."""
        return ["en", "my", "zh-Hans", "zh-Hant", "vi", "km", "id"]
