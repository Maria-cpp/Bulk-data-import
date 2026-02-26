"""CSV file extractor using standard library csv module."""

import csv
import io
from typing import Any

from app.services.extraction.base import (
    BaseExtractor,
    ExtractionResult,
    ExtractedTableData,
    ExtractionWarning,
)


class CSVExtractor(BaseExtractor):
    """Extract tables from CSV files."""

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "text/csv",
            "text/plain",
            "application/csv",
        ]

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract data from CSV file."""
        try:
            # Detect encoding
            content = self._decode_content(file_bytes)

            # Detect delimiter
            dialect = self._detect_dialect(content)

            # Parse CSV
            reader = csv.reader(io.StringIO(content), dialect=dialect)
            rows = list(reader)

            if not rows:
                return self._create_error_result(
                    message="CSV file is empty",
                )

            # First row is headers
            headers = rows[0]

            # Clean headers - remove empty and ensure uniqueness
            headers = self._clean_headers(headers)

            # Parse data rows
            row_data: list[dict[str, Any]] = []
            warnings: list[ExtractionWarning] = []

            for row_index, row in enumerate(rows[1:], start=2):
                # Handle rows with different column counts
                if len(row) != len(headers):
                    if len(row) < len(headers):
                        # Pad with None
                        row = row + [None] * (len(headers) - len(row))
                        warnings.append(
                            ExtractionWarning(
                                type="COLUMN_MISMATCH",
                                location=f"Row {row_index}",
                                message=f"Row has fewer columns than headers ({len(row)} vs {len(headers)})",
                            )
                        )
                    else:
                        # Truncate
                        row = row[: len(headers)]
                        warnings.append(
                            ExtractionWarning(
                                type="COLUMN_MISMATCH",
                                location=f"Row {row_index}",
                                message=f"Row has more columns than headers, extra columns ignored",
                            )
                        )

                row_dict: dict[str, Any] = {}
                for header, value in zip(headers, row):
                    row_dict[header] = self._convert_value(value)

                row_data.append(row_dict)

            if not row_data:
                return self._create_error_result(
                    message="CSV file contains only headers, no data rows",
                )

            table = ExtractedTableData(
                table_index=0,
                source_location=filename,
                column_headers=headers,
                row_data=row_data,
                row_count=len(row_data),
                column_count=len(headers),
                warnings=warnings,
            )

            return self._create_success_result([table])

        except csv.Error as e:
            return self._create_error_result(
                message=f"CSV parsing error: {str(e)}",
            )
        except Exception as e:
            return self._create_error_result(
                message=f"Failed to extract data from CSV: {str(e)}",
                details={"error_type": type(e).__name__},
            )

    def _decode_content(self, file_bytes: bytes) -> str:
        """Decode file bytes to string, detecting encoding."""
        # Try common encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        # Fallback with errors ignored
        return file_bytes.decode("utf-8", errors="replace")

    def _detect_dialect(self, content: str) -> csv.Dialect:
        """Detect CSV dialect (delimiter, quoting, etc.)."""
        try:
            # Use csv.Sniffer to detect dialect
            sniffer = csv.Sniffer()
            sample = content[:8192]  # Sample first 8KB
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            return dialect
        except csv.Error:
            # Default to excel dialect (comma-separated)
            return csv.excel

    def _clean_headers(self, headers: list[str]) -> list[str]:
        """Clean and deduplicate headers."""
        clean_headers: list[str] = []
        seen: set[str] = set()

        for i, header in enumerate(headers):
            # Clean whitespace
            header = header.strip() if header else ""

            # Generate name for empty headers
            if not header:
                header = f"Column_{i + 1}"

            # Handle duplicates
            original = header
            counter = 1
            while header.lower() in seen:
                header = f"{original}_{counter}"
                counter += 1

            seen.add(header.lower())
            clean_headers.append(header)

        return clean_headers

    def _convert_value(self, value: str | None) -> Any:
        """Convert string value to appropriate Python type."""
        if value is None or value == "":
            return None

        value = value.strip()

        # Try to parse as number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Try to parse as boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Return as string
        return value
