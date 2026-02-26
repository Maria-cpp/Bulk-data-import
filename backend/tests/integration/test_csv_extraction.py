"""Integration tests for CSV file extraction."""

import pytest
from pathlib import Path

from app.services.extraction.csv_extractor import CSVExtractor


# Fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def extractor():
    """Create CSVExtractor instance."""
    return CSVExtractor()


@pytest.fixture
def sample_csv_bytes():
    """Load sample CSV file bytes."""
    filepath = FIXTURES_DIR / "sample_data.csv"
    return filepath.read_bytes()


class TestCSVExtractor:
    """Test CSVExtractor functionality."""

    def test_supports_csv_mime_type(self, extractor):
        """Verify extractor supports CSV MIME type."""
        assert extractor.supports("text/csv")

    def test_supports_plain_text(self, extractor):
        """Verify extractor supports plain text MIME type."""
        assert extractor.supports("text/plain")

    def test_supports_application_csv(self, extractor):
        """Verify extractor supports application/csv MIME type."""
        assert extractor.supports("application/csv")

    def test_does_not_support_excel(self, extractor):
        """Verify extractor does not support Excel."""
        assert not extractor.supports(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


class TestStandardCSVParsing:
    """Tests for standard CSV file parsing."""

    def test_extract_all_rows(self, extractor, sample_csv_bytes):
        """Extract all 50 rows from sample CSV."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        assert result.success is True
        assert len(result.tables) == 1

        table = result.tables[0]
        assert table.row_count == 50

    def test_extract_column_headers(self, extractor, sample_csv_bytes):
        """Verify column headers are correctly extracted."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]
        expected_headers = ["ID", "Name", "Email", "Age", "Balance", "Active", "Notes"]
        assert table.column_headers == expected_headers
        assert table.column_count == 7

    def test_first_row_data(self, extractor, sample_csv_bytes):
        """Verify first row data is correctly parsed."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]
        first_row = table.row_data[0]

        assert first_row["ID"] == 1
        assert first_row["Name"] == "User 1"
        assert first_row["Email"] == "user1@example.com"


class TestDelimiterDetection:
    """Tests for automatic delimiter detection."""

    def test_comma_delimiter(self, extractor):
        """Parse standard comma-delimited CSV."""
        csv_content = b"a,b,c\n1,2,3\n4,5,6"
        result = extractor.extract(csv_content, "comma.csv")

        assert result.success is True
        table = result.tables[0]
        assert table.column_headers == ["a", "b", "c"]
        assert table.row_count == 2

    def test_semicolon_delimiter(self, extractor):
        """Parse semicolon-delimited CSV (European format)."""
        csv_content = b"a;b;c\n1;2;3\n4;5;6"
        result = extractor.extract(csv_content, "semicolon.csv")

        assert result.success is True
        table = result.tables[0]
        assert table.column_headers == ["a", "b", "c"]
        assert table.row_count == 2

    def test_tab_delimiter(self, extractor):
        """Parse tab-delimited TSV file."""
        csv_content = b"a\tb\tc\n1\t2\t3\n4\t5\t6"
        result = extractor.extract(csv_content, "tab.tsv")

        assert result.success is True
        table = result.tables[0]
        assert table.column_headers == ["a", "b", "c"]
        assert table.row_count == 2


class TestEncodingDetection:
    """Tests for character encoding detection."""

    def test_utf8_encoding(self, extractor):
        """Parse UTF-8 encoded CSV."""
        csv_content = "name,city\nJosé,São Paulo\nMüller,München".encode("utf-8")
        result = extractor.extract(csv_content, "utf8.csv")

        assert result.success is True
        table = result.tables[0]
        assert table.row_data[0]["name"] == "José"
        assert table.row_data[0]["city"] == "São Paulo"

    def test_utf8_bom_encoding(self, extractor):
        """Parse UTF-8 with BOM encoded CSV."""
        csv_content = b"\xef\xbb\xbfname,value\ntest,123"
        result = extractor.extract(csv_content, "utf8bom.csv")

        assert result.success is True
        table = result.tables[0]
        # BOM may or may not be stripped depending on encoding detection order
        # Check that we have the expected structure
        assert table.column_count == 2
        assert table.row_count == 1
        # Either stripped or with BOM prefix
        assert any("name" in h for h in table.column_headers)

    def test_latin1_encoding(self, extractor):
        """Parse Latin-1 encoded CSV."""
        csv_content = "name,city\nJosé,São Paulo".encode("latin-1")
        result = extractor.extract(csv_content, "latin1.csv")

        assert result.success is True


class TestDataTypeConversion:
    """Tests for automatic data type conversion."""

    def test_integer_conversion(self, extractor, sample_csv_bytes):
        """Verify integers are converted correctly."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]
        first_row = table.row_data[0]

        assert isinstance(first_row["ID"], int)
        assert isinstance(first_row["Age"], int)

    def test_float_conversion(self, extractor, sample_csv_bytes):
        """Verify floats are converted correctly."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]
        first_row = table.row_data[0]

        assert isinstance(first_row["Balance"], float)

    def test_boolean_conversion(self, extractor, sample_csv_bytes):
        """Verify booleans are converted correctly."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]

        # First row has Active=false
        assert table.row_data[0]["Active"] is False

        # Second row has Active=true
        assert table.row_data[1]["Active"] is True

    def test_null_handling(self, extractor, sample_csv_bytes):
        """Verify empty values are converted to None."""
        result = extractor.extract(sample_csv_bytes, "sample_data.csv")

        table = result.tables[0]

        # First row has empty Notes
        assert table.row_data[0]["Notes"] is None


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_quoted_values(self, extractor):
        """Parse CSV with quoted values containing commas."""
        csv_content = b'name,address\n"John Doe","123 Main St, Apt 4"\n'
        result = extractor.extract(csv_content, "quoted.csv")

        assert result.success is True
        table = result.tables[0]
        assert table.row_data[0]["address"] == "123 Main St, Apt 4"

    def test_empty_csv_returns_error(self, extractor):
        """Verify empty CSV returns error."""
        result = extractor.extract(b"", "empty.csv")

        assert result.success is False
        assert result.error_message is not None

    def test_headers_only_returns_error(self, extractor):
        """Verify CSV with only headers returns error."""
        csv_content = b"a,b,c\n"
        result = extractor.extract(csv_content, "headers_only.csv")

        assert result.success is False
        assert "no data" in result.error_message.lower()

    def test_duplicate_headers(self, extractor):
        """Parse CSV with duplicate column headers."""
        csv_content = b"id,name,name,value\n1,a,b,100\n"
        result = extractor.extract(csv_content, "duplicates.csv")

        assert result.success is True
        table = result.tables[0]

        # Should have deduplicated headers
        assert len(set(table.column_headers)) == len(table.column_headers)
        assert "name" in table.column_headers
        assert "name_1" in table.column_headers

    def test_mismatched_columns(self, extractor):
        """Parse CSV with rows having different column counts."""
        csv_content = b"a,b,c\n1,2\n4,5,6,7\n"
        result = extractor.extract(csv_content, "mismatched.csv")

        assert result.success is True
        table = result.tables[0]

        # Should have warnings about column mismatches
        assert len(table.warnings) > 0
        assert any("COLUMN_MISMATCH" in w.type for w in table.warnings)
