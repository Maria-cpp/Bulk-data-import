"""PDF table extraction using pdfplumber."""

import io
from typing import Any

import pdfplumber

from app.services.extraction.base import (
    BaseExtractor,
    ExtractionResult,
    ExtractedTableData,
    ExtractionWarning,
)


class PDFExtractor(BaseExtractor):
    """Extract tables from PDF documents using pdfplumber."""

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/pdf"]

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract tables from PDF file."""
        tables: list[ExtractedTableData] = []
        warnings: list[ExtractionWarning] = []
        table_index = 0

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    return self._create_error_result(
                        "PDF file has no pages",
                        {"filename": filename},
                    )

                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        page_tables = page.extract_tables()

                        if not page_tables:
                            continue

                        for raw_table in page_tables:
                            if not raw_table or len(raw_table) < 1:
                                continue

                            extracted = self._process_table(
                                raw_table,
                                table_index,
                                page_num,
                                filename,
                            )

                            if extracted:
                                tables.append(extracted)
                                table_index += 1

                    except Exception as e:
                        # Record warning but continue processing other pages
                        warnings.append(
                            ExtractionWarning(
                                type="page_extraction_error",
                                location=f"Page {page_num}",
                                message=f"Failed to extract tables from page: {str(e)}",
                            )
                        )

        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
            return self._create_error_result(
                "Invalid or corrupted PDF file",
                {"filename": filename, "error": str(e)},
                partial_tables=tables if tables else None,
            )
        except pdfplumber.pdfminer.pdfdocument.PDFPasswordIncorrect:
            return self._create_error_result(
                "PDF file is encrypted and requires a password",
                {"filename": filename, "encrypted": True},
            )
        except pdfplumber.pdfminer.pdfdocument.PDFEncryptionError as e:
            return self._create_error_result(
                "PDF file is encrypted and cannot be processed",
                {"filename": filename, "encrypted": True, "error": str(e)},
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "password" in error_msg or "encrypt" in error_msg:
                return self._create_error_result(
                    "PDF file is encrypted and cannot be processed",
                    {"filename": filename, "encrypted": True, "error": str(e)},
                )
            return self._create_error_result(
                f"Failed to process PDF: {str(e)}",
                {"filename": filename, "error_type": type(e).__name__},
                partial_tables=tables if tables else None,
            )

        if not tables:
            return self._create_error_result(
                "No tables found in PDF document",
                {"filename": filename, "pages_scanned": len(pdf.pages) if 'pdf' in dir() else 0},
            )

        # Add any accumulated warnings to the last table
        if warnings and tables:
            tables[-1].warnings.extend(warnings)

        return self._create_success_result(tables)

    def _process_table(
        self,
        raw_table: list[list[Any]],
        table_index: int,
        page_num: int,
        filename: str,
    ) -> ExtractedTableData | None:
        """Process a raw table from pdfplumber into ExtractedTableData."""
        if not raw_table:
            return None

        warnings: list[ExtractionWarning] = []

        # First row as headers
        raw_headers = raw_table[0] if raw_table else []
        headers = self._sanitize_headers(raw_headers, warnings, page_num)

        # Skip if no valid headers
        if not headers:
            warnings.append(
                ExtractionWarning(
                    type="empty_headers",
                    location=f"Page {page_num}, Table {table_index + 1}",
                    message="Table has no valid headers",
                )
            )
            return None

        # Process data rows
        data_rows = raw_table[1:] if len(raw_table) > 1 else []
        row_data = []

        for row_idx, row in enumerate(data_rows):
            row_dict = {}
            for col_idx, header in enumerate(headers):
                if col_idx < len(row):
                    value = row[col_idx]
                    # Handle None and empty strings
                    row_dict[header] = self._clean_cell_value(value)
                else:
                    row_dict[header] = None

            # Skip completely empty rows
            if any(v is not None and v != "" for v in row_dict.values()):
                row_data.append(row_dict)

        if not row_data:
            warnings.append(
                ExtractionWarning(
                    type="empty_data",
                    location=f"Page {page_num}, Table {table_index + 1}",
                    message="Table has headers but no data rows",
                )
            )
            # Still return the table structure even if empty
            return ExtractedTableData(
                table_index=table_index,
                source_location=f"Page {page_num}",
                column_headers=headers,
                row_data=[],
                row_count=0,
                column_count=len(headers),
                warnings=warnings,
            )

        return ExtractedTableData(
            table_index=table_index,
            source_location=f"Page {page_num}",
            column_headers=headers,
            row_data=row_data,
            row_count=len(row_data),
            column_count=len(headers),
            warnings=warnings,
        )

    def _sanitize_headers(
        self,
        raw_headers: list[Any],
        warnings: list[ExtractionWarning],
        page_num: int,
    ) -> list[str]:
        """Sanitize and deduplicate column headers."""
        headers = []
        seen = {}

        for idx, header in enumerate(raw_headers):
            # Convert to string and clean
            h = self._clean_cell_value(header)

            if h is None or h == "":
                h = f"Column_{idx + 1}"
                warnings.append(
                    ExtractionWarning(
                        type="missing_header",
                        location=f"Page {page_num}, Column {idx + 1}",
                        message=f"Empty header replaced with '{h}'",
                    )
                )

            # Handle duplicates
            if h in seen:
                seen[h] += 1
                original = h
                h = f"{h}_{seen[h]}"
                warnings.append(
                    ExtractionWarning(
                        type="duplicate_header",
                        location=f"Page {page_num}, Column {idx + 1}",
                        message=f"Duplicate header '{original}' renamed to '{h}'",
                    )
                )
            else:
                seen[h] = 0

            headers.append(h)

        return headers

    def _clean_cell_value(self, value: Any) -> Any:
        """Clean cell value from PDF extraction."""
        if value is None:
            return None

        if isinstance(value, str):
            # Clean whitespace and newlines
            cleaned = " ".join(value.split())
            return cleaned if cleaned else None

        return value
