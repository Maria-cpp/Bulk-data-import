"""Image table extraction using PaddleOCR with border detection."""

import io
import re
from typing import Any

import cv2
from PIL import Image
import numpy as np

from app.services.extraction.base import (
    BaseExtractor,
    ExtractionResult,
    ExtractedTableData,
    ExtractionWarning,
)

# Lazy load PaddleOCR to avoid slow startup
_ocr_instance = None


def get_ocr():
    """Get or create PaddleOCR instance (lazy loaded)."""
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=False,
        )
    return _ocr_instance


class ImageExtractor(BaseExtractor):
    """Extract tables from images using PaddleOCR with border detection."""

    @property
    def supported_mime_types(self) -> list[str]:
        return ["image/png", "image/jpeg", "image/jpg"]

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract tables from image using OCR and border detection."""
        try:
            # Load image
            image = Image.open(io.BytesIO(file_bytes))

            # Convert to RGB if needed
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            # Convert to numpy array
            img_array = np.array(image)
            img_height, img_width = img_array.shape[:2]

            # Get OCR instance and run OCR
            ocr = get_ocr()
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                return self._create_error_result(
                    "No text detected in image",
                    {"filename": filename, "text_detected": False},
                )

            # Extract text and positions
            ocr_data = []
            confidences = []

            for line in result[0]:
                box = line[0]
                text, confidence = line[1]

                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]

                ocr_data.append({
                    "text": text.strip(),
                    "left": min(x_coords),
                    "top": min(y_coords),
                    "right": max(x_coords),
                    "bottom": max(y_coords),
                    "center_x": (min(x_coords) + max(x_coords)) / 2,
                    "center_y": (min(y_coords) + max(y_coords)) / 2,
                    "confidence": confidence,
                })
                confidences.append(confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Detect table structure
            tables = self._extract_table_with_borders(
                img_array, ocr_data, filename, avg_confidence
            )

            if not tables:
                # Fallback to gap-based detection
                tables = self._extract_table_by_gaps(
                    ocr_data, filename, avg_confidence, img_width, img_height
                )

            if not tables:
                return self._create_error_result(
                    "No table structure detected in image",
                    {
                        "filename": filename,
                        "confidence_score": avg_confidence,
                        "text_detected": True,
                        "text_count": len(ocr_data),
                    },
                )

            return self._create_success_result(tables)

        except ImportError as e:
            return self._create_error_result(
                "PaddleOCR not installed. Install with: pip install paddlepaddle paddleocr",
                {"filename": filename, "error_type": "import_error"},
            )
        except Exception as e:
            return self._create_error_result(
                f"Failed to process image: {str(e)}",
                {"filename": filename, "error_type": type(e).__name__},
            )

    def _detect_lines(self, img_array: np.ndarray) -> tuple[list, list]:
        """Detect horizontal and vertical lines in the image."""
        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Apply threshold to get binary image
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)

        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)

        # Find contours for horizontal lines
        h_contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_lines_y = []
        for cnt in h_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > img_array.shape[1] * 0.1:  # Line must be at least 10% of image width
                h_lines_y.append(y + h // 2)

        # Find contours for vertical lines
        v_contours, _ = cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        v_lines_x = []
        for cnt in v_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > img_array.shape[0] * 0.05:  # Line must be at least 5% of image height
                v_lines_x.append(x + w // 2)

        # Sort and remove duplicates (merge close lines)
        h_lines_y = self._merge_close_values(sorted(h_lines_y), threshold=10)
        v_lines_x = self._merge_close_values(sorted(v_lines_x), threshold=10)

        return h_lines_y, v_lines_x

    def _merge_close_values(self, values: list, threshold: int = 10) -> list:
        """Merge values that are close together."""
        if not values:
            return []

        merged = [values[0]]
        for v in values[1:]:
            if v - merged[-1] > threshold:
                merged.append(v)
            else:
                # Average the close values
                merged[-1] = (merged[-1] + v) // 2

        return merged

    def _extract_table_with_borders(
        self,
        img_array: np.ndarray,
        ocr_data: list[dict],
        filename: str,
        overall_confidence: float,
    ) -> list[ExtractedTableData]:
        """Extract table using detected borders."""
        h_lines, v_lines = self._detect_lines(img_array)

        # Need at least 2 horizontal lines (top and bottom of header) and 2 vertical lines
        if len(h_lines) < 2 or len(v_lines) < 2:
            return []

        # Find table boundaries
        table_top = min(h_lines)
        table_bottom = max(h_lines)
        table_left = min(v_lines)
        table_right = max(v_lines)

        # Filter OCR data to only include text within table boundaries
        table_ocr = [
            item for item in ocr_data
            if (table_left <= item["center_x"] <= table_right and
                table_top <= item["center_y"] <= table_bottom)
        ]

        if not table_ocr:
            return []

        # Build cell grid
        rows = []
        for i in range(len(h_lines) - 1):
            row_top = h_lines[i]
            row_bottom = h_lines[i + 1]

            row_cells = []
            for j in range(len(v_lines) - 1):
                col_left = v_lines[j]
                col_right = v_lines[j + 1]

                # Find all text in this cell
                cell_texts = []
                for item in table_ocr:
                    if (col_left <= item["center_x"] <= col_right and
                        row_top <= item["center_y"] <= row_bottom):
                        cell_texts.append(item)

                # Sort by y then x and merge text
                cell_texts.sort(key=lambda x: (x["top"], x["left"]))
                cell_value = " ".join(t["text"] for t in cell_texts)
                row_cells.append(cell_value)

            if any(cell.strip() for cell in row_cells):  # Skip empty rows
                rows.append(row_cells)

        if len(rows) < 2:
            return []

        # First row is header
        headers = rows[0]
        data_rows = rows[1:]

        # Clean headers (deduplicate)
        clean_headers = self._deduplicate_headers(headers)

        # Convert to row dictionaries
        row_data = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(clean_headers):
                row_dict[header] = row[i] if i < len(row) else ""
            row_data.append(row_dict)

        warnings = []
        if overall_confidence < 0.7:
            warnings.append(
                ExtractionWarning(
                    type="low_ocr_confidence",
                    location="Image",
                    message=f"OCR confidence is low ({overall_confidence:.1%}). Results may be inaccurate.",
                    confidence=overall_confidence,
                )
            )

        return [
            ExtractedTableData(
                table_index=0,
                source_location="Image (PaddleOCR + Border Detection)",
                column_headers=clean_headers,
                row_data=row_data,
                row_count=len(row_data),
                column_count=len(clean_headers),
                confidence_score=overall_confidence,
                warnings=warnings,
            )
        ]

    def _extract_table_by_gaps(
        self,
        ocr_data: list[dict],
        filename: str,
        overall_confidence: float,
        img_width: int,
        img_height: int,
    ) -> list[ExtractedTableData]:
        """Extract table by analyzing gaps between text blocks (fallback method)."""
        if len(ocr_data) < 4:
            return []

        # Find column boundaries by analyzing X-position gaps
        x_positions = sorted(set(item["left"] for item in ocr_data))
        column_boundaries = self._find_column_boundaries(ocr_data, img_width)

        if len(column_boundaries) < 2:
            return []

        # Find row boundaries by analyzing Y-position gaps
        row_boundaries = self._find_row_boundaries(ocr_data, img_height)

        if len(row_boundaries) < 2:
            return []

        # Build cell grid
        rows = []
        for i in range(len(row_boundaries) - 1):
            row_top = row_boundaries[i]
            row_bottom = row_boundaries[i + 1]

            row_cells = []
            for j in range(len(column_boundaries) - 1):
                col_left = column_boundaries[j]
                col_right = column_boundaries[j + 1]

                # Find all text in this cell
                cell_texts = []
                for item in ocr_data:
                    item_center_x = (item["left"] + item["right"]) / 2
                    item_center_y = (item["top"] + item["bottom"]) / 2

                    if (col_left <= item_center_x <= col_right and
                        row_top <= item_center_y <= row_bottom):
                        cell_texts.append(item)

                # Sort by y then x and merge text
                cell_texts.sort(key=lambda x: (x["top"], x["left"]))
                cell_value = " ".join(t["text"] for t in cell_texts)
                row_cells.append(cell_value)

            if any(cell.strip() for cell in row_cells):
                rows.append(row_cells)

        if len(rows) < 2:
            return []

        # First row is header
        headers = rows[0]
        data_rows = rows[1:]

        clean_headers = self._deduplicate_headers(headers)

        row_data = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(clean_headers):
                row_dict[header] = row[i] if i < len(row) else ""
            row_data.append(row_dict)

        warnings = []
        if overall_confidence < 0.7:
            warnings.append(
                ExtractionWarning(
                    type="low_ocr_confidence",
                    location="Image",
                    message=f"OCR confidence is low ({overall_confidence:.1%}). Results may be inaccurate.",
                    confidence=overall_confidence,
                )
            )

        return [
            ExtractedTableData(
                table_index=0,
                source_location="Image (PaddleOCR + Gap Analysis)",
                column_headers=clean_headers,
                row_data=row_data,
                row_count=len(row_data),
                column_count=len(clean_headers),
                confidence_score=overall_confidence,
                warnings=warnings,
            )
        ]

    def _find_column_boundaries(self, ocr_data: list[dict], img_width: int) -> list[int]:
        """Find column boundaries by analyzing gaps in X positions."""
        # Get all left edges
        left_edges = sorted(item["left"] for item in ocr_data)

        # Find significant gaps
        min_gap = img_width * 0.02  # At least 2% of image width
        boundaries = [0]  # Start at left edge

        for i in range(1, len(left_edges)):
            gap = left_edges[i] - left_edges[i - 1]
            if gap > min_gap:
                # Add midpoint of gap as boundary
                boundaries.append((left_edges[i - 1] + left_edges[i]) // 2)

        boundaries.append(img_width)  # End at right edge

        # Merge boundaries that are too close
        return self._merge_close_values(boundaries, threshold=int(img_width * 0.02))

    def _find_row_boundaries(self, ocr_data: list[dict], img_height: int) -> list[int]:
        """Find row boundaries by analyzing gaps in Y positions."""
        # Get all top edges, sorted
        items_by_y = sorted(ocr_data, key=lambda x: x["top"])

        # Find significant vertical gaps
        min_gap = img_height * 0.015  # At least 1.5% of image height

        boundaries = [0]  # Start at top
        prev_bottom = items_by_y[0]["bottom"] if items_by_y else 0

        for item in items_by_y[1:]:
            gap = item["top"] - prev_bottom
            if gap > min_gap:
                # Add boundary between rows
                boundaries.append((prev_bottom + item["top"]) // 2)
            prev_bottom = max(prev_bottom, item["bottom"])

        boundaries.append(img_height)  # End at bottom

        return boundaries

    def _deduplicate_headers(self, headers: list[str]) -> list[str]:
        """Deduplicate header names by adding suffix."""
        seen = {}
        clean_headers = []
        for h in headers:
            h = h.strip() if h else "Column"
            if not h:
                h = "Column"
            if h in seen:
                seen[h] += 1
                clean_headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                clean_headers.append(h)
        return clean_headers
