"""Excel file extractor using openpyxl."""

from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from io import BytesIO

from app.services.extraction.base import (
    BaseExtractor,
    ExtractionResult,
    ExtractedTableData,
    ExtractionWarning,
)


class ExcelExtractor(BaseExtractor):
    """Extract tables from Excel files (.xlsx, .xls)."""

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract tables from Excel file."""
        try:
            # Load workbook from bytes
            workbook = load_workbook(
                filename=BytesIO(file_bytes),
                read_only=True,
                data_only=True,  # Get computed values instead of formulas
            )

            tables: list[ExtractedTableData] = []

            for sheet_index, sheet_name in enumerate(workbook.sheetnames):
                sheet = workbook[sheet_name]

                # Get all rows as list
                rows = list(sheet.iter_rows(values_only=True))

                if not rows:
                    continue

                # First row is headers
                headers = [str(cell) if cell is not None else f"Column_{i}" for i, cell in enumerate(rows[0])]

                # Rest are data rows
                row_data: list[dict[str, Any]] = []
                warnings: list[ExtractionWarning] = []

                for row_index, row in enumerate(rows[1:], start=2):
                    row_dict: dict[str, Any] = {}
                    for col_index, (header, value) in enumerate(zip(headers, row)):
                        # Convert value to appropriate type
                        row_dict[header] = self._convert_value(value)

                        # Check for potential issues
                        if value is None and col_index == 0:
                            warnings.append(
                                ExtractionWarning(
                                    type="EMPTY_CELL",
                                    location=f"Row {row_index}, Column A",
                                    message="First column is empty",
                                )
                            )

                    row_data.append(row_dict)

                # Only add non-empty sheets
                if row_data:
                    tables.append(
                        ExtractedTableData(
                            table_index=sheet_index,
                            source_location=f"Sheet: {sheet_name}",
                            column_headers=headers,
                            row_data=row_data,
                            row_count=len(row_data),
                            column_count=len(headers),
                            warnings=warnings,
                        )
                    )

            workbook.close()

            if not tables:
                return self._create_error_result(
                    message="No data found in Excel file",
                    details={"sheets_checked": len(workbook.sheetnames)},
                )

            return self._create_success_result(tables)

        except InvalidFileException as e:
            return self._create_error_result(
                message="Invalid Excel file format",
                details={"error": str(e)},
            )
        except Exception as e:
            return self._create_error_result(
                message=f"Failed to extract data from Excel file: {str(e)}",
                details={"error_type": type(e).__name__},
            )

    def _convert_value(self, value: Any) -> Any:
        """Convert Excel cell value to appropriate Python type."""
        if value is None:
            return None

        # Handle dates
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle numbers
        if isinstance(value, (int, float)):
            # Check if it's actually an integer
            if isinstance(value, float) and value.is_integer():
                return int(value)
            return value

        # Handle strings
        return str(value)
