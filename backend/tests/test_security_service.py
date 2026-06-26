"""Tests for the security service — the critical exclusion zone enforcement."""

import pytest
from backend.services.security_service import (
    regions_overlap,
    filter_regions_for_translation,
    validate_no_exclusion_leak,
)


class TestRegionsOverlap:
    """Test bounding box overlap detection."""

    def test_no_overlap(self):
        r1 = {"x": 0, "y": 0, "width": 100, "height": 100}
        r2 = {"x": 200, "y": 200, "width": 100, "height": 100}
        assert regions_overlap(r1, r2) is False

    def test_full_overlap(self):
        r1 = {"x": 0, "y": 0, "width": 100, "height": 100}
        r2 = {"x": 0, "y": 0, "width": 100, "height": 100}
        assert regions_overlap(r1, r2) is True

    def test_partial_overlap_below_threshold(self):
        """Small overlap (5%) should not count as overlap with default 30% threshold."""
        r1 = {"x": 0, "y": 0, "width": 100, "height": 100}  # area = 10000
        r2 = {"x": 95, "y": 95, "width": 100, "height": 100}  # overlap = 5x5 = 25
        assert regions_overlap(r1, r2, threshold=0.3) is False

    def test_partial_overlap_above_threshold(self):
        """Significant overlap should be detected."""
        r1 = {"x": 0, "y": 0, "width": 100, "height": 100}  # area = 10000
        r2 = {"x": 50, "y": 50, "width": 100, "height": 100}  # overlap = 50x50 = 2500
        assert regions_overlap(r1, r2, threshold=0.3) is True

    def test_contained_region(self):
        """One region entirely inside another."""
        r1 = {"x": 0, "y": 0, "width": 200, "height": 200}
        r2 = {"x": 50, "y": 50, "width": 50, "height": 50}
        assert regions_overlap(r1, r2) is True


class TestFilterRegionsForTranslation:
    """Test that exclusion zones properly filter out overlapping text regions."""

    def test_no_exclusions(self):
        regions = [
            {"id": "1", "x": 0, "y": 0, "width": 100, "height": 50, "text": "Hello"},
            {"id": "2", "x": 0, "y": 100, "width": 100, "height": 50, "text": "World"},
        ]
        result = filter_regions_for_translation(regions, [])
        assert len(result) == 2

    def test_exclusion_removes_overlapping(self):
        regions = [
            {"id": "1", "x": 0, "y": 0, "width": 100, "height": 50, "text": "Title"},
            {"id": "2", "x": 0, "y": 200, "width": 100, "height": 50, "text": "Body"},
        ]
        exclusions = [
            {"x": 0, "y": 0, "width": 120, "height": 60},  # Covers "Title"
        ]
        result = filter_regions_for_translation(regions, exclusions)
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_exclusion_removes_multiple(self):
        regions = [
            {"id": "1", "x": 0, "y": 0, "width": 100, "height": 50, "text": "Header"},
            {"id": "2", "x": 0, "y": 100, "width": 100, "height": 50, "text": "Secret"},
            {"id": "3", "x": 0, "y": 200, "width": 100, "height": 50, "text": "Body"},
        ]
        exclusions = [
            {"x": 0, "y": 0, "width": 100, "height": 60},    # Covers "Header"
            {"x": 0, "y": 100, "width": 100, "height": 60},  # Covers "Secret"
        ]
        result = filter_regions_for_translation(regions, exclusions)
        assert len(result) == 1
        assert result[0]["id"] == "3"


class TestValidateNoExclusionLeak:
    """Test the final safety gate."""

    def test_safe_when_no_overlap(self):
        regions = [{"id": "1", "x": 0, "y": 200, "width": 100, "height": 50}]
        exclusions = [{"x": 0, "y": 0, "width": 100, "height": 100}]
        assert validate_no_exclusion_leak(regions, exclusions) is True

    def test_unsafe_when_overlap(self):
        regions = [{"id": "1", "x": 0, "y": 0, "width": 100, "height": 50}]
        exclusions = [{"x": 0, "y": 0, "width": 120, "height": 60}]
        assert validate_no_exclusion_leak(regions, exclusions) is False

    def test_safe_with_empty_exclusions(self):
        regions = [{"id": "1", "x": 0, "y": 0, "width": 100, "height": 50}]
        assert validate_no_exclusion_leak(regions, []) is True

    def test_safe_with_empty_regions(self):
        exclusions = [{"x": 0, "y": 0, "width": 100, "height": 100}]
        assert validate_no_exclusion_leak([], exclusions) is True
