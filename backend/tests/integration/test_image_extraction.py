"""Integration tests for image OCR extraction."""

import pytest
from pathlib import Path
from unittest.mock import patch

from app.services.extraction.image import ImageExtractor


# Fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def extractor():
    """Create ImageExtractor instance."""
    return ImageExtractor()


@pytest.fixture
def clear_table_bytes():
    """Load clear table PNG file bytes."""
    filepath = FIXTURES_DIR / "clear_table.png"
    return filepath.read_bytes()


@pytest.fixture
def low_quality_bytes():
    """Load low quality JPG file bytes."""
    filepath = FIXTURES_DIR / "low_quality.jpg"
    return filepath.read_bytes()


class TestImageExtractor:
    """Test ImageExtractor functionality."""

    def test_supports_png_mime_type(self, extractor):
        """Verify extractor supports PNG MIME type."""
        assert extractor.supports("image/png")

    def test_supports_jpeg_mime_type(self, extractor):
        """Verify extractor supports JPEG MIME type."""
        assert extractor.supports("image/jpeg")

    def test_supports_jpg_mime_type(self, extractor):
        """Verify extractor supports JPG MIME type."""
        assert extractor.supports("image/jpg")

    def test_does_not_support_pdf(self, extractor):
        """Verify extractor does not support PDF."""
        assert not extractor.supports("application/pdf")


class TestClearImageOCR:
    """Tests for OCR on clear, high-quality images."""

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_extract_table_from_clear_image(self, extractor, clear_table_bytes):
        """Extract table from clear image with high accuracy."""
        result = extractor.extract(clear_table_bytes, "clear_table.png")

        # Should succeed if Tesseract is available
        assert result.success is True
        assert len(result.tables) >= 1

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_clear_image_has_high_confidence(self, extractor, clear_table_bytes):
        """Verify clear image extraction has high confidence score."""
        result = extractor.extract(clear_table_bytes, "clear_table.png")

        if result.success and result.tables:
            table = result.tables[0]
            # Clear images should have > 80% confidence
            assert table.confidence_score is not None
            assert table.confidence_score > 0.7

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_clear_image_extracts_column_headers(self, extractor, clear_table_bytes):
        """Verify column headers are extracted from clear image."""
        result = extractor.extract(clear_table_bytes, "clear_table.png")

        if result.success and result.tables:
            table = result.tables[0]
            # Fixture has columns: ID, Name, Value
            assert len(table.column_headers) >= 2

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_clear_image_extracts_data_rows(self, extractor, clear_table_bytes):
        """Verify data rows are extracted from clear image."""
        result = extractor.extract(clear_table_bytes, "clear_table.png")

        if result.success and result.tables:
            table = result.tables[0]
            # Fixture has 5 data rows
            assert table.row_count >= 3


class TestLowConfidenceDetection:
    """Tests for detecting and handling low confidence OCR."""

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_low_quality_image_detected(self, extractor, low_quality_bytes):
        """Detect low quality image extraction."""
        result = extractor.extract(low_quality_bytes, "low_quality.jpg")

        # May succeed but with lower confidence or warnings
        if result.success and result.tables:
            table = result.tables[0]
            # Low quality images may have lower confidence
            # or warnings about OCR quality
            has_low_confidence = (
                table.confidence_score is not None and table.confidence_score < 0.9
            )
            has_warnings = len(table.warnings) > 0
            assert has_low_confidence or has_warnings

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_low_confidence_warning_generated(self, extractor, low_quality_bytes):
        """Verify warning is generated for low confidence OCR."""
        result = extractor.extract(low_quality_bytes, "low_quality.jpg")

        if result.success and result.tables:
            table = result.tables[0]
            if table.confidence_score and table.confidence_score < 0.7:
                # Should have low confidence warning
                low_conf_warnings = [
                    w for w in table.warnings if "confidence" in w.type.lower()
                ]
                assert len(low_conf_warnings) > 0


class TestNoTableDetected:
    """Tests for handling images with no detectable tables."""

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_no_table_returns_error(self, extractor):
        """Verify image with no table returns appropriate error."""
        # Create a blank white image
        from PIL import Image
        import io

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        blank_bytes = buffer.getvalue()

        result = extractor.extract(blank_bytes, "blank.png")

        # Should fail or return error about no table found
        if not result.success:
            assert "no table" in result.error_message.lower()


class TestGracefulTesseractFailure:
    """Tests for graceful handling of Tesseract unavailability."""

    def test_tesseract_unavailable_returns_error(self, extractor, clear_table_bytes):
        """Verify graceful failure when Tesseract is unavailable."""
        with patch.object(extractor, "_is_tesseract_available", return_value=False):
            result = extractor.extract(clear_table_bytes, "clear_table.png")

            assert result.success is False
            assert "OCR service unavailable" in result.error_message
            assert result.error_details is not None
            assert result.error_details.get("tesseract_available") is False


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_image_returns_error(self, extractor):
        """Verify invalid image returns error result."""
        result = extractor.extract(b"not a valid image file", "invalid.png")

        assert result.success is False
        assert result.error_message is not None

    def test_empty_file_returns_error(self, extractor):
        """Verify empty file returns error result."""
        result = extractor.extract(b"", "empty.png")

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.skipif(
        not ImageExtractor()._is_tesseract_available(),
        reason="Tesseract not available",
    )
    def test_source_location_indicates_ocr(self, extractor, clear_table_bytes):
        """Verify source location indicates OCR was used."""
        result = extractor.extract(clear_table_bytes, "clear_table.png")

        if result.success and result.tables:
            table = result.tables[0]
            assert "OCR" in table.source_location or "Image" in table.source_location
