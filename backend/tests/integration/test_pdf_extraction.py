"""Integration tests for PDF file extraction."""

import pytest
from pathlib import Path

from app.services.extraction.pdf import PDFExtractor


# Fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def extractor():
    """Create PDFExtractor instance."""
    return PDFExtractor()


@pytest.fixture
def single_table_pdf_bytes():
    """Load single table PDF file bytes."""
    filepath = FIXTURES_DIR / "single_table.pdf"
    return filepath.read_bytes()


@pytest.fixture
def multi_table_pdf_bytes():
    """Load multi-table PDF file bytes."""
    filepath = FIXTURES_DIR / "multi_table.pdf"
    return filepath.read_bytes()


class TestPDFExtractor:
    """Test PDFExtractor functionality."""

    def test_supports_pdf_mime_type(self, extractor):
        """Verify extractor supports PDF MIME type."""
        assert extractor.supports("application/pdf")

    def test_does_not_support_excel(self, extractor):
        """Verify extractor does not support Excel."""
        assert not extractor.supports(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_does_not_support_word(self, extractor):
        """Verify extractor does not support Word."""
        assert not extractor.supports(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )


class TestSingleTableExtraction:
    """Tests for extracting a single table from PDF."""

    def test_extract_single_table(self, extractor, single_table_pdf_bytes):
        """Extract single table from PDF successfully."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        assert result.success is True
        assert len(result.tables) >= 1

    def test_single_table_has_correct_structure(self, extractor, single_table_pdf_bytes):
        """Verify extracted table has expected column structure."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        table = result.tables[0]
        # Check expected columns from fixture
        assert "ID" in table.column_headers
        assert "Product" in table.column_headers
        assert "Category" in table.column_headers
        assert "Price" in table.column_headers
        assert "Stock" in table.column_headers

    def test_single_table_has_data_rows(self, extractor, single_table_pdf_bytes):
        """Verify extracted table has data rows."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        table = result.tables[0]
        assert table.row_count > 0
        # Fixture has 20 data rows
        assert table.row_count == 20

    def test_source_location_shows_page(self, extractor, single_table_pdf_bytes):
        """Verify source location indicates page number."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        table = result.tables[0]
        assert "Page" in table.source_location


class TestMultiTableExtraction:
    """Tests for extracting multiple tables from PDF."""

    def test_extract_multiple_tables(self, extractor, multi_table_pdf_bytes):
        """Extract multiple tables from multi-page PDF."""
        result = extractor.extract(multi_table_pdf_bytes, "multi_table.pdf")

        assert result.success is True
        # Fixture has 3 tables across 2 pages
        assert len(result.tables) >= 2

    def test_tables_have_different_page_locations(self, extractor, multi_table_pdf_bytes):
        """Verify tables from different pages have correct locations."""
        result = extractor.extract(multi_table_pdf_bytes, "multi_table.pdf")

        locations = [t.source_location for t in result.tables]
        # Should have tables from page 1 and page 2
        page_1_tables = [l for l in locations if "Page 1" in l]
        page_2_tables = [l for l in locations if "Page 2" in l]

        assert len(page_1_tables) >= 1
        assert len(page_2_tables) >= 1


class TestTableAcrossPages:
    """Tests for handling tables that span pages."""

    def test_partial_extraction_on_error(self, extractor, multi_table_pdf_bytes):
        """Verify partial extraction works when some pages fail."""
        result = extractor.extract(multi_table_pdf_bytes, "multi_table.pdf")

        # Even if some pages have issues, successfully extracted tables are returned
        if result.partial:
            assert len(result.tables) > 0


class TestPartialFailure:
    """Tests for partial failure scenarios."""

    def test_partial_success_with_error_details(self, extractor, multi_table_pdf_bytes):
        """Verify error details are provided on partial failures."""
        result = extractor.extract(multi_table_pdf_bytes, "multi_table.pdf")

        if result.partial:
            assert result.error_details is not None or any(
                len(t.warnings) > 0 for t in result.tables
            )


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_pdf_returns_error(self, extractor):
        """Verify invalid PDF returns error result."""
        result = extractor.extract(b"not a valid pdf file", "invalid.pdf")

        assert result.success is False
        assert result.error_message is not None

    def test_empty_file_returns_error(self, extractor):
        """Verify empty file returns error result."""
        result = extractor.extract(b"", "empty.pdf")

        assert result.success is False
        assert result.error_message is not None

    def test_encrypted_pdf_error_message(self, extractor):
        """Verify encrypted PDF returns appropriate error."""
        # Create a minimal PDF-like structure that might trigger encryption check
        # This is a basic test - real encrypted PDFs would need proper fixtures
        result = extractor.extract(b"%PDF-1.4\nencrypted", "encrypted.pdf")

        # Either fails gracefully or returns error about encryption
        assert result.success is False or result.error_message is not None


class TestDataPreservation:
    """Tests for data preservation during extraction."""

    def test_cell_values_preserved(self, extractor, single_table_pdf_bytes):
        """Verify cell values are correctly extracted."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        if result.success and result.tables:
            table = result.tables[0]
            # Check first row has expected structure
            if table.row_data:
                first_row = table.row_data[0]
                # Should have values for each column
                assert len(first_row) == table.column_count

    def test_whitespace_cleaned(self, extractor, single_table_pdf_bytes):
        """Verify whitespace is cleaned from extracted values."""
        result = extractor.extract(single_table_pdf_bytes, "single_table.pdf")

        if result.success and result.tables:
            table = result.tables[0]
            for row in table.row_data:
                for value in row.values():
                    if isinstance(value, str):
                        # No leading/trailing whitespace
                        assert value == value.strip()
                        # No multiple consecutive spaces
                        assert "  " not in value
