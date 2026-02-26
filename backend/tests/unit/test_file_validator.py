"""Unit tests for file validation utilities."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.file_validator import (
    validate_file_size,
    validate_file_type,
    detect_file_type_from_magic,
    detect_file_type_from_content,
    sanitize_filename,
    compute_file_hash,
    FileValidationError,
)
from app.schemas.bulk_import import FileType


class TestMagicByteDetection:
    """Tests for magic byte file type detection."""

    def test_detect_pdf_magic(self):
        """Detect PDF from magic bytes."""
        pdf_bytes = b"%PDF-1.4 some content"
        file_type = detect_file_type_from_magic(pdf_bytes)
        assert file_type == FileType.PDF

    def test_detect_png_magic(self):
        """Detect PNG from magic bytes."""
        png_bytes = b"\x89PNG\r\n\x1a\n fake png content"
        file_type = detect_file_type_from_magic(png_bytes)
        assert file_type == FileType.IMAGE

    def test_detect_jpeg_magic(self):
        """Detect JPEG from magic bytes."""
        jpeg_bytes = b"\xff\xd8\xff fake jpeg content"
        file_type = detect_file_type_from_magic(jpeg_bytes)
        assert file_type == FileType.IMAGE

    def test_detect_xlsx_magic(self):
        """Detect XLSX (ZIP-based) from magic bytes."""
        xlsx_bytes = b"PK\x03\x04 zip content"
        file_type = detect_file_type_from_magic(xlsx_bytes)
        assert file_type == FileType.EXCEL

    def test_detect_legacy_excel_magic(self):
        """Detect legacy Excel (OLE) from magic bytes."""
        xls_bytes = b"\xd0\xcf\x11\xe0 ole content"
        file_type = detect_file_type_from_magic(xls_bytes)
        assert file_type == FileType.EXCEL

    def test_unknown_magic_returns_none(self):
        """Return None for unknown magic bytes."""
        unknown_bytes = b"some random content"
        file_type = detect_file_type_from_magic(unknown_bytes)
        assert file_type is None

    def test_empty_file_returns_none(self):
        """Return None for empty file."""
        file_type = detect_file_type_from_magic(b"")
        assert file_type is None


class TestFileSizeValidation:
    """Tests for file size validation."""

    def test_valid_file_size_passes(self):
        """Valid file size passes validation."""
        with patch("app.services.file_validator.settings") as mock_settings:
            mock_settings.BULK_IMPORT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
            validate_file_size(1024)  # 1KB - should not raise

    def test_file_size_at_limit_passes(self):
        """File size at exactly the limit passes."""
        with patch("app.services.file_validator.settings") as mock_settings:
            mock_settings.BULK_IMPORT_MAX_FILE_SIZE = 1024
            validate_file_size(1024)  # Exactly at limit - should not raise

    def test_file_size_over_limit_raises(self):
        """File size over limit raises error."""
        with patch("app.services.file_validator.settings") as mock_settings:
            mock_settings.BULK_IMPORT_MAX_FILE_SIZE = 1024
            with pytest.raises(FileValidationError) as exc_info:
                validate_file_size(1025)

            assert exc_info.value.error_code == "FILE_TOO_LARGE"
            assert exc_info.value.details["max_size_bytes"] == 1024
            assert exc_info.value.details["received_size_bytes"] == 1025

    def test_zero_file_size_passes(self):
        """Zero file size passes validation (will fail elsewhere)."""
        with patch("app.services.file_validator.settings") as mock_settings:
            mock_settings.BULK_IMPORT_MAX_FILE_SIZE = 1024
            validate_file_size(0)  # Should not raise


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_normal_filename_unchanged(self):
        """Normal filename passes through unchanged."""
        filename = "document.pdf"
        result = sanitize_filename(filename)
        assert result == "document.pdf"

    def test_removes_path_traversal_dots(self):
        """Remove .. path traversal attempts."""
        filename = "../../../etc/passwd"
        result = sanitize_filename(filename)
        assert ".." not in result

    def test_removes_forward_slash(self):
        """Remove forward slashes."""
        filename = "path/to/file.pdf"
        result = sanitize_filename(filename)
        assert "/" not in result

    def test_removes_backslash(self):
        """Remove backslashes."""
        filename = "path\\to\\file.pdf"
        result = sanitize_filename(filename)
        assert "\\" not in result

    def test_removes_control_characters(self):
        """Remove control characters."""
        filename = "file\x00name\x1f.pdf"
        result = sanitize_filename(filename)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_preserves_extension(self):
        """Preserve file extension."""
        filename = "document.pdf"
        result = sanitize_filename(filename)
        assert result.endswith(".pdf")

    def test_truncates_long_filename(self):
        """Truncate filename exceeding 255 characters."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_handles_empty_filename(self):
        """Handle empty filename."""
        result = sanitize_filename("")
        assert result  # Should return something
        assert len(result) > 0

    def test_handles_dot_filename(self):
        """Handle filename starting with dot."""
        result = sanitize_filename(".hidden")
        assert not result.startswith(".") or result.startswith("unnamed")

    def test_extracts_filename_from_path(self):
        """Extract just filename from full path."""
        filename = "/home/user/documents/file.pdf"
        result = sanitize_filename(filename)
        assert "/" not in result
        # Should just be the filename part
        assert "file" in result

    def test_windows_path_extraction(self):
        """Extract filename from Windows path."""
        filename = "C:\\Users\\test\\file.docx"
        result = sanitize_filename(filename)
        assert "\\" not in result


class TestFileTypeValidation:
    """Tests for file type validation."""

    def test_pdf_file_validated(self):
        """Validate PDF file type."""
        pdf_bytes = b"%PDF-1.4 some content"
        file_type = validate_file_type(pdf_bytes, "test.pdf")
        assert file_type == FileType.PDF

    def test_csv_file_validated(self):
        """Validate CSV file type (no magic bytes)."""
        csv_bytes = b"col1,col2,col3\n1,2,3"
        file_type = validate_file_type(csv_bytes, "test.csv")
        assert file_type == FileType.CSV

    def test_xlsx_file_validated(self):
        """Validate XLSX file type."""
        xlsx_bytes = b"PK\x03\x04 zip content"
        file_type = validate_file_type(xlsx_bytes, "test.xlsx")
        assert file_type == FileType.EXCEL

    def test_docx_file_validated(self):
        """Validate DOCX file type (also ZIP-based)."""
        docx_bytes = b"PK\x03\x04 zip content"
        file_type = validate_file_type(docx_bytes, "test.docx")
        assert file_type == FileType.WORD

    def test_png_file_validated(self):
        """Validate PNG file type."""
        png_bytes = b"\x89PNG\r\n\x1a\n content"
        file_type = validate_file_type(png_bytes, "test.png")
        assert file_type == FileType.IMAGE

    def test_jpeg_file_validated(self):
        """Validate JPEG file type."""
        jpeg_bytes = b"\xff\xd8\xff content"
        file_type = validate_file_type(jpeg_bytes, "test.jpg")
        assert file_type == FileType.IMAGE

    def test_unsupported_type_raises(self):
        """Unsupported file type raises error."""
        unknown_bytes = b"unknown content"
        with pytest.raises(FileValidationError) as exc_info:
            validate_file_type(unknown_bytes, "test.xyz")

        assert exc_info.value.error_code == "INVALID_FILE_TYPE"

    def test_mime_type_mismatch_raises(self):
        """Mismatched MIME type raises error."""
        pdf_bytes = b"%PDF-1.4 content"
        with pytest.raises(FileValidationError) as exc_info:
            validate_file_type(pdf_bytes, "test.pdf", "image/png")

        assert exc_info.value.error_code == "FILE_TYPE_MISMATCH"

    def test_text_plain_csv_allowed(self):
        """Allow text/plain MIME type for CSV files."""
        csv_bytes = b"a,b,c\n1,2,3"
        file_type = validate_file_type(csv_bytes, "test.csv", "text/plain")
        assert file_type == FileType.CSV


class TestFileHash:
    """Tests for file hash computation."""

    def test_hash_returns_string(self):
        """Hash returns string."""
        content = b"test content"
        hash_result = compute_file_hash(content)
        assert isinstance(hash_result, str)

    def test_hash_is_sha256(self):
        """Hash is 64 character SHA-256."""
        content = b"test content"
        hash_result = compute_file_hash(content)
        assert len(hash_result) == 64

    def test_same_content_same_hash(self):
        """Same content produces same hash."""
        content = b"identical content"
        hash1 = compute_file_hash(content)
        hash2 = compute_file_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        hash1 = compute_file_hash(b"content 1")
        hash2 = compute_file_hash(b"content 2")
        assert hash1 != hash2

    def test_empty_file_hash(self):
        """Empty file produces valid hash."""
        hash_result = compute_file_hash(b"")
        assert len(hash_result) == 64
        # SHA256 of empty string is known
        assert hash_result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestFileValidationError:
    """Tests for FileValidationError exception."""

    def test_error_has_code(self):
        """Error has error code."""
        error = FileValidationError("TEST_ERROR", "Test message")
        assert error.error_code == "TEST_ERROR"

    def test_error_has_message(self):
        """Error has message."""
        error = FileValidationError("TEST_ERROR", "Test message")
        assert error.message == "Test message"
        assert str(error) == "Test message"

    def test_error_has_details(self):
        """Error has details dict."""
        details = {"key": "value"}
        error = FileValidationError("TEST_ERROR", "Test message", details)
        assert error.details == {"key": "value"}

    def test_error_details_default_empty(self):
        """Error details default to empty dict."""
        error = FileValidationError("TEST_ERROR", "Test message")
        assert error.details == {}
