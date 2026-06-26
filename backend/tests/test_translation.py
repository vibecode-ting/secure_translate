"""Tests for translation engines."""

import pytest
from unittest.mock import patch, MagicMock
from backend.engines.base import TranslationEngine


class TestTranslationEngineInterface:
    """Test the abstract translation engine interface."""

    def test_cannot_instantiate_base(self):
        """Base TranslationEngine should not be instantiable."""
        with pytest.raises(TypeError):
            TranslationEngine()


class TestGeminiEngine:
    """Test Gemini translation engine."""

    def test_get_name(self):
        from backend.engines.gemini_engine import GeminiEngine
        engine = GeminiEngine(api_key="test-key")
        assert engine.get_name() == "gemini"

    def test_supported_languages(self):
        from backend.engines.gemini_engine import GeminiEngine
        engine = GeminiEngine(api_key="test-key")
        langs = engine.get_supported_languages()
        assert "en" in langs
        assert "my" in langs
        assert "zh-Hans" in langs
        assert "km" in langs


class TestAzureEngine:
    """Test Azure translation engine."""

    def test_get_name(self):
        from backend.engines.azure_engine import AzureEngine
        engine = AzureEngine(api_key="test-key", region="eastus")
        assert engine.get_name() == "azure"

    def test_supported_languages(self):
        from backend.engines.azure_engine import AzureEngine
        engine = AzureEngine(api_key="test-key", region="eastus")
        langs = engine.get_supported_languages()
        assert len(langs) == 7


class TestGoogleEngine:
    """Test Google Cloud Translation engine."""

    def test_get_name(self):
        from backend.engines.google_engine import GoogleEngine
        engine = GoogleEngine(api_key="test-key")
        assert engine.get_name() == "google"

    def test_supported_languages(self):
        from backend.engines.google_engine import GoogleEngine
        engine = GoogleEngine(api_key="test-key")
        langs = engine.get_supported_languages()
        assert len(langs) == 7
