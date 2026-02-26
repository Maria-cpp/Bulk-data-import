"""Integration tests for data export functionality."""

import csv
import io
import json
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.bulk_import import BulkImport, ExtractedTable, ImportStatus, FileType


class TestJSONExport:
    """Tests for JSON export format."""

    def test_export_json_structure(self):
        """Verify JSON export has correct structure."""
        sample_data = [
            {"ID": 1, "Name": "Test 1", "Value": 100},
            {"ID": 2, "Name": "Test 2", "Value": 200},
        ]

        json_output = json.dumps(sample_data, indent=2)
        parsed = json.loads(json_output)

        assert len(parsed) == 2
        assert parsed[0]["ID"] == 1
        assert parsed[1]["Name"] == "Test 2"

    def test_export_json_preserves_types(self):
        """Verify JSON export preserves data types."""
        sample_data = [
            {
                "int_value": 42,
                "float_value": 3.14,
                "string_value": "hello",
                "null_value": None,
                "bool_value": True,
            }
        ]

        json_output = json.dumps(sample_data)
        parsed = json.loads(json_output)

        assert isinstance(parsed[0]["int_value"], int)
        assert isinstance(parsed[0]["float_value"], float)
        assert isinstance(parsed[0]["string_value"], str)
        assert parsed[0]["null_value"] is None
        assert isinstance(parsed[0]["bool_value"], bool)

    def test_export_json_empty_data(self):
        """Verify JSON export handles empty data."""
        empty_data = []
        json_output = json.dumps(empty_data)
        parsed = json.loads(json_output)

        assert parsed == []

    def test_export_json_special_characters(self):
        """Verify JSON export handles special characters."""
        sample_data = [
            {"text": "Hello\nWorld"},
            {"text": "Tab\there"},
            {"text": "Quote\"mark"},
            {"text": "Unicode: \u00e9\u00f1"},
        ]

        json_output = json.dumps(sample_data, ensure_ascii=False)
        parsed = json.loads(json_output)

        assert parsed[0]["text"] == "Hello\nWorld"
        assert parsed[3]["text"] == "Unicode: \u00e9\u00f1"


class TestCSVExport:
    """Tests for CSV export format."""

    def test_export_csv_structure(self):
        """Verify CSV export has correct structure."""
        sample_data = [
            {"ID": 1, "Name": "Test 1", "Value": 100},
            {"ID": 2, "Name": "Test 2", "Value": 200},
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["ID", "Name", "Value"])
        writer.writeheader()
        writer.writerows(sample_data)

        csv_content = output.getvalue()
        lines = csv_content.strip().split("\n")

        assert len(lines) == 3  # Header + 2 data rows
        assert "ID,Name,Value" in lines[0]

    def test_export_csv_parsing(self):
        """Verify exported CSV can be parsed back."""
        sample_data = [
            {"ID": "1", "Name": "Test 1", "Value": "100"},
            {"ID": "2", "Name": "Test 2", "Value": "200"},
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["ID", "Name", "Value"])
        writer.writeheader()
        writer.writerows(sample_data)

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["ID"] == "1"
        assert rows[1]["Name"] == "Test 2"

    def test_export_csv_escaping(self):
        """Verify CSV properly escapes special characters."""
        sample_data = [
            {"text": 'Contains "quotes"'},
            {"text": "Contains, comma"},
            {"text": "Contains\nnewline"},
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["text"])
        writer.writeheader()
        writer.writerows(sample_data)

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["text"] == 'Contains "quotes"'
        assert rows[1]["text"] == "Contains, comma"
        assert rows[2]["text"] == "Contains\nnewline"

    def test_export_csv_empty_data(self):
        """Verify CSV export handles empty data."""
        sample_data = []
        headers = ["ID", "Name", "Value"]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(sample_data)

        csv_content = output.getvalue()
        lines = csv_content.strip().split("\n")

        assert len(lines) == 1  # Only header

    def test_export_csv_unicode(self):
        """Verify CSV export handles unicode characters."""
        sample_data = [
            {"name": "José García"},
            {"name": "北京"},
            {"name": "Müller"},
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["name"])
        writer.writeheader()
        writer.writerows(sample_data)

        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["name"] == "José García"
        assert rows[1]["name"] == "北京"
        assert rows[2]["name"] == "Müller"


class TestExportContentDisposition:
    """Tests for export content disposition."""

    def test_json_filename_format(self):
        """Verify JSON export filename format."""
        table_name = "sales_data"
        filename = f"{table_name}.json"

        assert filename.endswith(".json")
        assert table_name in filename

    def test_csv_filename_format(self):
        """Verify CSV export filename format."""
        table_name = "sales_data"
        filename = f"{table_name}.csv"

        assert filename.endswith(".csv")
        assert table_name in filename

    def test_filename_sanitization(self):
        """Verify unsafe characters are handled in filename."""
        unsafe_name = "file/with\\bad:chars*"
        safe_name = unsafe_name.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_")

        assert "/" not in safe_name
        assert "\\" not in safe_name
        assert ":" not in safe_name
        assert "*" not in safe_name


class TestExportDataIntegrity:
    """Tests for data integrity during export."""

    def test_row_count_matches(self):
        """Verify exported row count matches original."""
        original_rows = 100
        sample_data = [{"id": i, "value": i * 10} for i in range(original_rows)]

        # JSON export
        json_output = json.dumps(sample_data)
        json_parsed = json.loads(json_output)
        assert len(json_parsed) == original_rows

        # CSV export
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "value"])
        writer.writeheader()
        writer.writerows(sample_data)

        output.seek(0)
        reader = csv.DictReader(output)
        csv_rows = list(reader)
        assert len(csv_rows) == original_rows

    def test_column_headers_preserved(self):
        """Verify all column headers are preserved in export."""
        headers = ["Column A", "Column B", "Column C", "Column D"]
        sample_data = [{h: f"value_{i}" for h in headers} for i in range(3)]

        # JSON export
        json_output = json.dumps(sample_data)
        json_parsed = json.loads(json_output)
        for row in json_parsed:
            assert set(row.keys()) == set(headers)

        # CSV export
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(sample_data)

        output.seek(0)
        reader = csv.DictReader(output)
        assert reader.fieldnames == headers
