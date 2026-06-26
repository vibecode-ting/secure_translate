"""Tests for image processing service."""

import pytest
from PIL import Image
from backend.services.image_service import paint_over_region, render_text_on_image


class TestPaintOverRegion:
    """Test painting over text regions."""

    def test_paint_fills_region(self):
        img = Image.new("RGB", (200, 200), color=(0, 0, 0))
        region = {"x": 10, "y": 10, "width": 50, "height": 30}
        result = paint_over_region(img, region, color=(255, 255, 255))

        # Check that the painted area is white
        pixel = result.getpixel((20, 20))
        assert pixel == (255, 255, 255)

    def test_paint_preserves_outside(self):
        img = Image.new("RGB", (200, 200), color=(0, 0, 0))
        region = {"x": 10, "y": 10, "width": 50, "height": 30}
        result = paint_over_region(img, region, color=(255, 255, 255))

        # Check that area outside is still black
        pixel = result.getpixel((100, 100))
        assert pixel == (0, 0, 0)


class TestRenderTextOnImage:
    """Test rendering translated text onto images."""

    def test_renders_text_in_region(self):
        img = Image.new("RGB", (400, 200), color=(255, 255, 255))
        region = {"x": 10, "y": 10, "width": 180, "height": 50}
        result = render_text_on_image(img, "Hello World", region)

        # Result should be a PIL Image of same size
        assert result.size == (400, 200)

    def test_handles_empty_text(self):
        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        region = {"x": 10, "y": 10, "width": 50, "height": 30}
        result = render_text_on_image(img, "", region)
        assert result.size == (200, 200)
