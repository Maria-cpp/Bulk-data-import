"""Integration tests for Excel file extraction."""

import pytest
from pathlib import Path

from app.services.extraction.excel import ExcelExtractor


# Fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def extractor():
    """Create ExcelExtractor instance."""
    return ExcelExtractor()


@pytest.fixture
def sample_xlsx_bytes():
    """Load sample Excel file bytes."""
    filepath = FIXTURES_DIR / "sample_data.xlsx"
    return filepath.read_bytes()


class TestExcelExtractor:
    """Test ExcelExtractor functionality."""

    def test_supports_xlsx_mime_type(self, extractor):
        """Verify extractor supports XLSX MIME type."""
        assert extractor.supports(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_supports_xls_mime_type(self, extractor):
        """Verify extractor supports legacy XLS MIME type."""
        assert extractor.supports("application/vnd.ms-excel")

    def test_does_not_support_csv(self, extractor):
        """Verify extractor does not support CSV."""
        assert not extractor.supports("text/csv")


class TestSingleSheetExtraction:
    """Tests for extracting data from single sheets."""

    def test_extract_employees_sheet(self, extractor, sample_xlsx_bytes):
        """Extract first sheet (Employees) with 50 rows."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        assert result.success is True
        assert len(result.tables) >= 1

        # Check first table (Employees)
        employees_table = result.tables[0]
        assert employees_table.source_location == "Sheet: Employees"
        assert employees_table.row_count == 50
        assert employees_table.column_count == 5
        assert "ID" in employees_table.column_headers
        assert "Name" in employees_table.column_headers
        assert "Department" in employees_table.column_headers
        assert "Salary" in employees_table.column_headers
        assert "Hire Date" in employees_table.column_headers


class TestMultiSheetExtraction:
    """Tests for extracting data from multiple sheets."""

    def test_extract_all_sheets(self, extractor, sample_xlsx_bytes):
        """Extract all 3 sheets from sample workbook."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        assert result.success is True
        assert len(result.tables) == 3

        # Verify sheet names
        sheet_locations = [t.source_location for t in result.tables]
        assert "Sheet: Employees" in sheet_locations
        assert "Sheet: Products" in sheet_locations
        assert "Sheet: Orders" in sheet_locations

    def test_total_row_count_across_sheets(self, extractor, sample_xlsx_bytes):
        """Verify total row count across all sheets is 100."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        total_rows = sum(t.row_count for t in result.tables)
        assert total_rows == 100  # 50 + 30 + 20

    def test_products_sheet_structure(self, extractor, sample_xlsx_bytes):
        """Verify Products sheet has correct structure."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        products_table = next(
            t for t in result.tables if "Products" in t.source_location
        )
        assert products_table.row_count == 30
        assert "SKU" in products_table.column_headers
        assert "Product Name" in products_table.column_headers
        assert "Category" in products_table.column_headers
        assert "Price" in products_table.column_headers
        assert "Stock" in products_table.column_headers

    def test_orders_sheet_structure(self, extractor, sample_xlsx_bytes):
        """Verify Orders sheet has correct structure."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        orders_table = next(
            t for t in result.tables if "Orders" in t.source_location
        )
        assert orders_table.row_count == 20
        assert "Order ID" in orders_table.column_headers
        assert "Customer" in orders_table.column_headers
        assert "Status" in orders_table.column_headers


class TestDataTypePreservation:
    """Tests for data type preservation during extraction."""

    def test_numeric_values_preserved(self, extractor, sample_xlsx_bytes):
        """Verify numeric values are preserved correctly."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        employees_table = result.tables[0]
        first_row = employees_table.row_data[0]

        # ID should be integer
        assert first_row["ID"] == 1
        assert isinstance(first_row["ID"], int)

        # Salary should be numeric
        assert isinstance(first_row["Salary"], (int, float))

    def test_string_values_preserved(self, extractor, sample_xlsx_bytes):
        """Verify string values are preserved correctly."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        employees_table = result.tables[0]
        first_row = employees_table.row_data[0]

        # Name should be string
        assert isinstance(first_row["Name"], str)
        assert "Employee" in first_row["Name"]


class TestFormulaHandling:
    """Tests for formula value extraction."""

    def test_computed_values_extracted(self, extractor, sample_xlsx_bytes):
        """Verify formulas return computed values, not formula text."""
        result = extractor.extract(sample_xlsx_bytes, "sample_data.xlsx")

        # All values should be resolved, not contain formula syntax
        for table in result.tables:
            for row in table.row_data:
                for value in row.values():
                    if isinstance(value, str):
                        assert not value.startswith("="), "Formula not computed"


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_file_returns_error(self, extractor):
        """Verify invalid file returns error result."""
        result = extractor.extract(b"not a valid excel file", "invalid.xlsx")

        assert result.success is False
        assert result.error_message is not None

    def test_empty_file_returns_error(self, extractor):
        """Verify empty file returns error result."""
        result = extractor.extract(b"", "empty.xlsx")

        assert result.success is False
        assert result.error_message is not None
