# Bulk Import Service

Service layer for extracting table data from documents. Framework-agnostic patterns.

## Dependencies

### Python
```bash
pip install pdfplumber openpyxl python-docx pytesseract Pillow pandas
```

### Node.js
```bash
npm install pdf-parse xlsx mammoth tesseract.js csv-parse
```

### Tesseract (for Image OCR)
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt-get install tesseract-ocr`
- Docker: `RUN apt-get update && apt-get install -y tesseract-ocr`

---

## Core Extraction Logic (Python)

The extraction logic is independent of any web framework. Adapt the wrapper to your needs.

```python
# services/table_extractor.py
"""
Table Extraction Service

Extracts tables from PDF, Excel, Word, Image, and CSV files.
Framework-agnostic - can be used with FastAPI, Flask, Django, or standalone.
"""

import io
import csv
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ===== CONFIGURATION =====

MAX_FILE_SIZE = int(os.environ.get("BULK_IMPORT_MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50 MB
MAX_PREVIEW_ROWS = 10
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".csv"}


# ===== ENUMS =====

class SourceFileType(str, Enum):
    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    IMAGE = "IMAGE"
    CSV = "CSV"


# ===== DATA CLASSES =====

@dataclass
class ExtractedTable:
    """Represents an extracted table."""
    headers: List[str]
    rows: List[List[str]]
    source: str  # e.g., "Page 1, Table 1" or "Sheet: Sales"


@dataclass
class ExtractionResult:
    """Result of table extraction."""
    tables: List[ExtractedTable]
    total_rows: int
    file_type: SourceFileType
    error: Optional[str] = None


# ===== FILE TYPE DETECTION =====

def detect_file_type(filename: str) -> SourceFileType:
    """Detect source file type from filename."""
    ext = Path(filename).suffix.lower()

    type_map = {
        ".pdf": SourceFileType.PDF,
        ".xlsx": SourceFileType.EXCEL,
        ".xls": SourceFileType.EXCEL,
        ".docx": SourceFileType.WORD,
        ".doc": SourceFileType.WORD,
        ".png": SourceFileType.IMAGE,
        ".jpg": SourceFileType.IMAGE,
        ".jpeg": SourceFileType.IMAGE,
        ".gif": SourceFileType.IMAGE,
        ".bmp": SourceFileType.IMAGE,
        ".tiff": SourceFileType.IMAGE,
        ".csv": SourceFileType.CSV,
    }

    if ext not in type_map:
        raise ValueError(f"Unsupported file type: {ext}")

    return type_map[ext]


def validate_file(filename: str, file_size: int) -> Tuple[str, SourceFileType]:
    """Validate uploaded file."""
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise ValueError(f"File size exceeds maximum allowed ({max_mb:.0f} MB)")

    file_type = detect_file_type(filename)
    return ext, file_type


# ===== EXTRACTORS =====

def extract_from_pdf(content: bytes) -> List[ExtractedTable]:
    """Extract tables from PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")

    tables = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for table_idx, table in enumerate(page_tables):
                if not table or len(table) < 2:
                    continue

                # First row as headers
                headers = [str(h).strip() if h else f"Column_{i}"
                           for i, h in enumerate(table[0])]

                # Remaining rows as data
                rows = []
                for row in table[1:]:
                    row_data = [str(cell).strip() if cell else "" for cell in row]
                    rows.append(row_data)

                tables.append(ExtractedTable(
                    headers=headers,
                    rows=rows,
                    source=f"Page {page_num + 1}, Table {table_idx + 1}"
                ))

    return tables


def extract_from_excel(content: bytes) -> List[ExtractedTable]:
    """Extract tables from Excel using openpyxl."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl not installed. Run: pip install openpyxl")

    tables = []
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        data = list(sheet.values)

        if not data or len(data) < 2:
            continue

        # First row as headers
        headers = [str(h).strip() if h else f"Column_{i}"
                   for i, h in enumerate(data[0])]

        # Remaining rows
        rows = []
        for row in data[1:]:
            row_data = [str(cell).strip() if cell else "" for cell in row]
            # Skip completely empty rows
            if any(cell for cell in row_data):
                rows.append(row_data)

        if rows:
            tables.append(ExtractedTable(
                headers=headers,
                rows=rows,
                source=f"Sheet: {sheet_name}"
            ))

    return tables


def extract_from_word(content: bytes) -> List[ExtractedTable]:
    """Extract tables from Word documents using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")

    tables = []
    doc = Document(io.BytesIO(content))

    for table_idx, table in enumerate(doc.tables):
        if len(table.rows) < 2:
            continue

        # First row as headers
        headers = [cell.text.strip() if cell.text else f"Column_{i}"
                   for i, cell in enumerate(table.rows[0].cells)]

        # Remaining rows
        rows = []
        for row in table.rows[1:]:
            row_data = [cell.text.strip() for cell in row.cells]
            if any(cell for cell in row_data):
                rows.append(row_data)

        if rows:
            tables.append(ExtractedTable(
                headers=headers,
                rows=rows,
                source=f"Table {table_idx + 1}"
            ))

    return tables


def extract_from_image(content: bytes) -> List[ExtractedTable]:
    """Extract tables from images using OCR (pytesseract)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError("pytesseract and Pillow required. Run: pip install pytesseract Pillow")

    # Configure tesseract path if set
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # Open image
    image = Image.open(io.BytesIO(content))

    # Get OCR data with position info
    ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DATAFRAME)

    # Filter out empty text
    ocr_data = ocr_data[ocr_data['text'].notna() & (ocr_data['text'].str.strip() != '')]

    if ocr_data.empty:
        return []

    # Group by block_num and line_num to get rows
    grouped = ocr_data.groupby(['block_num', 'line_num'])

    extracted_rows = []
    for (block, line), group in grouped:
        # Sort by left position to get column order
        group_sorted = group.sort_values('left')
        row_text = group_sorted['text'].tolist()
        if row_text:
            extracted_rows.append(row_text)

    if len(extracted_rows) < 2:
        return []

    # Normalize column count
    max_cols = max(len(row) for row in extracted_rows)
    normalized_rows = []
    for row in extracted_rows:
        while len(row) < max_cols:
            row.append("")
        normalized_rows.append(row[:max_cols])

    return [ExtractedTable(
        headers=normalized_rows[0],
        rows=normalized_rows[1:],
        source="OCR Extraction"
    )]


def extract_from_csv(content: bytes) -> List[ExtractedTable]:
    """Extract data from CSV files."""
    # Try to decode with different encodings
    text = None
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError("Could not decode CSV file")

    reader = csv.reader(io.StringIO(text))
    rows_list = list(reader)

    if len(rows_list) < 2:
        return []

    headers = [h.strip() if h else f"Column_{i}" for i, h in enumerate(rows_list[0])]
    rows = [row for row in rows_list[1:] if any(cell.strip() for cell in row)]

    return [ExtractedTable(
        headers=headers,
        rows=rows,
        source="CSV File"
    )]


# ===== MAIN EXTRACTION FUNCTION =====

def extract_tables(content: bytes, filename: str) -> ExtractionResult:
    """
    Extract tables from any supported file type.

    Args:
        content: File content as bytes
        filename: Original filename (for type detection)

    Returns:
        ExtractionResult with tables and metadata
    """
    try:
        file_type = detect_file_type(filename)

        extractors = {
            SourceFileType.PDF: extract_from_pdf,
            SourceFileType.EXCEL: extract_from_excel,
            SourceFileType.WORD: extract_from_word,
            SourceFileType.IMAGE: extract_from_image,
            SourceFileType.CSV: extract_from_csv,
        }

        extractor = extractors.get(file_type)
        if not extractor:
            return ExtractionResult(
                tables=[],
                total_rows=0,
                file_type=file_type,
                error=f"No extractor available for {file_type}"
            )

        tables = extractor(content)
        total_rows = sum(len(t.rows) for t in tables)

        return ExtractionResult(
            tables=tables,
            total_rows=total_rows,
            file_type=file_type
        )

    except Exception as e:
        logger.exception(f"Table extraction failed: {e}")
        return ExtractionResult(
            tables=[],
            total_rows=0,
            file_type=detect_file_type(filename),
            error=str(e)
        )


# ===== UTILITY FUNCTIONS =====

def tables_to_dict_rows(tables: List[ExtractedTable]) -> List[Dict[str, Any]]:
    """Convert extracted tables to list of dictionaries."""
    all_rows = []
    for table in tables:
        for row in table.rows:
            row_dict = {table.headers[i]: row[i] if i < len(row) else ""
                        for i in range(len(table.headers))}
            all_rows.append(row_dict)
    return all_rows


def tables_to_csv_string(tables: List[ExtractedTable]) -> str:
    """Convert extracted tables to CSV string."""
    all_rows = tables_to_dict_rows(tables)
    if not all_rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_rows[0].keys())
    writer.writeheader()
    writer.writerows(all_rows)
    return output.getvalue()


def create_preview(tables: List[ExtractedTable], max_rows: int = MAX_PREVIEW_ROWS) -> List[Dict[str, Any]]:
    """Create preview data for tables."""
    previews = []
    for idx, table in enumerate(tables):
        preview_rows = table.rows[:max_rows]
        previews.append({
            "headers": table.headers,
            "rows": preview_rows,
            "total_rows": len(table.rows),
            "table_index": idx,
            "source": table.source
        })
    return previews
```

---

## FastAPI Integration

```python
# services/bulk_import_service.py (FastAPI)
"""Bulk Import Service for FastAPI"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile

from .table_extractor import (
    extract_tables, validate_file, tables_to_dict_rows,
    tables_to_csv_string, create_preview, SourceFileType
)
from ..models import BulkImport, ImportStatus, DataFormat
from ..schemas import BulkImportUploadResponse, ExtractedTablePreview


class BulkImportService:
    """Service for bulk importing data from documents."""

    async def upload_and_extract(
        self,
        db: AsyncSession,
        file: UploadFile,
        parent_id: Optional[UUID] = None,
        parent_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        data_format: DataFormat = DataFormat.JSON
    ) -> BulkImportUploadResponse:
        """Upload a file and extract table data."""
        filename = file.filename or "unknown"
        content = await file.read()
        file_size = len(content)

        # Validate
        ext, file_type = validate_file(filename, file_size)

        # Extract tables
        result = extract_tables(content, filename)

        if result.error:
            raise ValueError(f"Extraction failed: {result.error}")

        if not result.tables:
            raise ValueError("No tables found in the uploaded file")

        # Convert to storage format
        all_rows = tables_to_dict_rows(result.tables)
        previews = create_preview(result.tables)

        asset_data_json = None
        asset_data_csv = None

        if data_format == DataFormat.JSON:
            asset_data_json = all_rows
        else:
            asset_data_csv = tables_to_csv_string(result.tables)

        # Create import record
        import_record = BulkImport(
            id=uuid.uuid4(),
            parent_id=parent_id,
            parent_type=parent_type,
            asset_data=asset_data_json,
            asset_data_csv=asset_data_csv,
            data_format=data_format,
            source_file_type=file_type,
            source_file_name=filename,
            source_file_size=file_size,
            status=ImportStatus.COMPLETED,
            total_rows=len(all_rows),
            successful_rows=len(all_rows),
            preview_data=previews,
            imported_by=user_id,
            imported_at=datetime.utcnow(),
            processed_at=datetime.utcnow()
        )

        db.add(import_record)
        await db.flush()

        return BulkImportUploadResponse(
            id=import_record.id,
            parent_id=parent_id,
            parent_type=parent_type,
            source_file_name=filename,
            source_file_type=file_type,
            status=ImportStatus.COMPLETED,
            preview=[ExtractedTablePreview(**p) for p in previews],
            total_tables=len(result.tables),
            message=f"Extracted {len(all_rows)} rows from {len(result.tables)} table(s)"
        )

    async def get_import(self, db: AsyncSession, import_id: UUID):
        """Get a bulk import record by ID."""
        stmt = select(BulkImport).where(
            BulkImport.id == import_id,
            BulkImport.deleted_at == None
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_imports_by_parent(
        self,
        db: AsyncSession,
        parent_id: UUID,
        parent_type: Optional[str] = None
    ):
        """Get all bulk imports for a parent entity."""
        conditions = [
            BulkImport.parent_id == parent_id,
            BulkImport.deleted_at == None
        ]
        if parent_type:
            conditions.append(BulkImport.parent_type == parent_type)

        stmt = select(BulkImport).where(*conditions).order_by(
            BulkImport.imported_at.desc()
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def delete_import(self, db: AsyncSession, import_id: UUID) -> bool:
        """Soft delete a bulk import record."""
        record = await self.get_import(db, import_id)
        if not record:
            return False

        record.deleted_at = datetime.utcnow()
        db.add(record)
        await db.flush()
        return True


# Singleton instance
bulk_import_service = BulkImportService()
```

---

## Flask Integration

```python
# services/bulk_import_service.py (Flask)
"""Bulk Import Service for Flask"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from werkzeug.datastructures import FileStorage

from flask import current_app
from ..extensions import db
from .table_extractor import (
    extract_tables, validate_file, tables_to_dict_rows,
    tables_to_csv_string, create_preview
)
from ..models import BulkImport, ImportStatus, DataFormat


class BulkImportService:
    """Service for bulk importing data from documents."""

    def upload_and_extract(
        self,
        file: FileStorage,
        parent_id: Optional[str] = None,
        parent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        data_format: str = "JSON"
    ) -> Dict[str, Any]:
        """Upload a file and extract table data."""
        filename = file.filename or "unknown"
        content = file.read()
        file_size = len(content)

        # Validate
        ext, file_type = validate_file(filename, file_size)

        # Extract tables
        result = extract_tables(content, filename)

        if result.error:
            raise ValueError(f"Extraction failed: {result.error}")

        if not result.tables:
            raise ValueError("No tables found in the uploaded file")

        # Convert to storage format
        all_rows = tables_to_dict_rows(result.tables)
        previews = create_preview(result.tables)

        asset_data_json = None
        asset_data_csv = None

        if data_format == "JSON":
            asset_data_json = all_rows
        else:
            asset_data_csv = tables_to_csv_string(result.tables)

        # Create import record
        import_record = BulkImport(
            id=str(uuid.uuid4()),
            parent_id=parent_id,
            parent_type=parent_type,
            asset_data=asset_data_json,
            asset_data_csv=asset_data_csv,
            data_format=data_format,
            source_file_type=file_type.value,
            source_file_name=filename,
            source_file_size=file_size,
            status=ImportStatus.COMPLETED.value,
            total_rows=len(all_rows),
            successful_rows=len(all_rows),
            preview_data=previews,
            imported_by=user_id,
            imported_at=datetime.utcnow(),
            processed_at=datetime.utcnow()
        )

        db.session.add(import_record)
        db.session.commit()

        return {
            "id": import_record.id,
            "parent_id": parent_id,
            "parent_type": parent_type,
            "source_file_name": filename,
            "source_file_type": file_type.value,
            "status": ImportStatus.COMPLETED.value,
            "preview": previews,
            "total_tables": len(result.tables),
            "message": f"Extracted {len(all_rows)} rows from {len(result.tables)} table(s)"
        }

    def get_import(self, import_id: str) -> Optional[BulkImport]:
        """Get a bulk import record by ID."""
        return BulkImport.query.filter_by(
            id=import_id,
            deleted_at=None
        ).first()

    def get_imports_by_parent(
        self,
        parent_id: str,
        parent_type: Optional[str] = None
    ) -> List[BulkImport]:
        """Get all bulk imports for a parent entity."""
        query = BulkImport.query.filter_by(
            parent_id=parent_id,
            deleted_at=None
        )
        if parent_type:
            query = query.filter_by(parent_type=parent_type)

        return query.order_by(BulkImport.imported_at.desc()).all()


bulk_import_service = BulkImportService()
```

---

## Django Integration

```python
# services/bulk_import_service.py (Django)
"""Bulk Import Service for Django"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from .table_extractor import (
    extract_tables, validate_file, tables_to_dict_rows,
    tables_to_csv_string, create_preview
)
from ..models import BulkImport, ImportStatus, DataFormat


class BulkImportService:
    """Service for bulk importing data from documents."""

    def upload_and_extract(
        self,
        file: UploadedFile,
        parent_id: Optional[str] = None,
        parent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        data_format: str = "JSON"
    ) -> Dict[str, Any]:
        """Upload a file and extract table data."""
        filename = file.name or "unknown"
        content = file.read()
        file_size = len(content)

        # Validate
        ext, file_type = validate_file(filename, file_size)

        # Extract tables
        result = extract_tables(content, filename)

        if result.error:
            raise ValueError(f"Extraction failed: {result.error}")

        if not result.tables:
            raise ValueError("No tables found in the uploaded file")

        # Convert to storage format
        all_rows = tables_to_dict_rows(result.tables)
        previews = create_preview(result.tables)

        asset_data_json = None
        asset_data_csv = None

        if data_format == "JSON":
            asset_data_json = all_rows
        else:
            asset_data_csv = tables_to_csv_string(result.tables)

        # Create import record
        import_record = BulkImport.objects.create(
            parent_id=parent_id,
            parent_type=parent_type,
            asset_data=asset_data_json,
            asset_data_csv=asset_data_csv,
            data_format=data_format,
            source_file_type=file_type.value,
            source_file_name=filename,
            source_file_size=file_size,
            status=ImportStatus.COMPLETED,
            total_rows=len(all_rows),
            successful_rows=len(all_rows),
            preview_data=previews,
            imported_by=user_id,
            processed_at=timezone.now()
        )

        return {
            "id": str(import_record.id),
            "parent_id": parent_id,
            "parent_type": parent_type,
            "source_file_name": filename,
            "source_file_type": file_type.value,
            "status": ImportStatus.COMPLETED,
            "preview": previews,
            "total_tables": len(result.tables),
            "message": f"Extracted {len(all_rows)} rows from {len(result.tables)} table(s)"
        }

    def get_import(self, import_id: str) -> Optional[BulkImport]:
        """Get a bulk import record by ID."""
        try:
            return BulkImport.objects.get(id=import_id, deleted_at__isnull=True)
        except BulkImport.DoesNotExist:
            return None

    def get_imports_by_parent(
        self,
        parent_id: str,
        parent_type: Optional[str] = None
    ) -> List[BulkImport]:
        """Get all bulk imports for a parent entity."""
        queryset = BulkImport.objects.filter(
            parent_id=parent_id,
            deleted_at__isnull=True
        )
        if parent_type:
            queryset = queryset.filter(parent_type=parent_type)

        return list(queryset.order_by('-imported_at'))


bulk_import_service = BulkImportService()
```

---

## Node.js/TypeScript Integration

```typescript
// services/table-extractor.ts
import * as pdfParse from "pdf-parse";
import * as xlsx from "xlsx";
import * as mammoth from "mammoth";
import Tesseract from "tesseract.js";
import { parse } from "csv-parse/sync";

export interface ExtractedTable {
  headers: string[];
  rows: string[][];
  source: string;
}

export interface ExtractionResult {
  tables: ExtractedTable[];
  totalRows: number;
  fileType: string;
  error?: string;
}

export async function extractFromPdf(buffer: Buffer): Promise<ExtractedTable[]> {
  // Note: pdf-parse extracts text, not tables. For table extraction,
  // consider using pdf-table-extractor or pdf.js with custom logic
  const data = await pdfParse(buffer);
  // Basic text-to-table conversion (customize as needed)
  const lines = data.text.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];

  // Simple assumption: first line is headers
  const headers = lines[0].split(/\s{2,}/).map((h) => h.trim());
  const rows = lines.slice(1).map((line) =>
    line.split(/\s{2,}/).map((c) => c.trim())
  );

  return [{ headers, rows, source: "PDF Document" }];
}

export function extractFromExcel(buffer: Buffer): ExtractedTable[] {
  const workbook = xlsx.read(buffer, { type: "buffer" });
  const tables: ExtractedTable[] = [];

  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    const data = xlsx.utils.sheet_to_json<string[]>(sheet, { header: 1 });

    if (data.length < 2) continue;

    const headers = (data[0] as string[]).map((h, i) =>
      h ? String(h).trim() : `Column_${i}`
    );
    const rows = data.slice(1).map((row) =>
      (row as string[]).map((c) => (c ? String(c).trim() : ""))
    );

    tables.push({ headers, rows, source: `Sheet: ${sheetName}` });
  }

  return tables;
}

export async function extractFromWord(buffer: Buffer): Promise<ExtractedTable[]> {
  // mammoth extracts text, tables need custom handling
  const result = await mammoth.extractRawText({ buffer });
  // Basic implementation - would need enhanced for real table extraction
  const lines = result.value.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];

  return [
    {
      headers: lines[0].split("\t").map((h) => h.trim()),
      rows: lines.slice(1).map((line) => line.split("\t").map((c) => c.trim())),
      source: "Word Document",
    },
  ];
}

export async function extractFromImage(buffer: Buffer): Promise<ExtractedTable[]> {
  const { data } = await Tesseract.recognize(buffer, "eng");
  const lines = data.text.split("\n").filter((l) => l.trim());

  if (lines.length < 2) return [];

  // Simple space-based column detection
  const headers = lines[0].split(/\s{2,}/).map((h) => h.trim());
  const rows = lines.slice(1).map((line) =>
    line.split(/\s{2,}/).map((c) => c.trim())
  );

  return [{ headers, rows, source: "OCR Extraction" }];
}

export function extractFromCsv(buffer: Buffer): ExtractedTable[] {
  const text = buffer.toString("utf-8");
  const records = parse(text, { columns: false, skip_empty_lines: true });

  if (records.length < 2) return [];

  const headers = (records[0] as string[]).map((h, i) =>
    h ? h.trim() : `Column_${i}`
  );
  const rows = records.slice(1).map((row: string[]) =>
    row.map((c) => (c ? c.trim() : ""))
  );

  return [{ headers, rows, source: "CSV File" }];
}

export async function extractTables(
  buffer: Buffer,
  filename: string
): Promise<ExtractionResult> {
  const ext = filename.toLowerCase().split(".").pop();

  try {
    let tables: ExtractedTable[] = [];

    switch (ext) {
      case "pdf":
        tables = await extractFromPdf(buffer);
        break;
      case "xlsx":
      case "xls":
        tables = extractFromExcel(buffer);
        break;
      case "docx":
      case "doc":
        tables = await extractFromWord(buffer);
        break;
      case "png":
      case "jpg":
      case "jpeg":
        tables = await extractFromImage(buffer);
        break;
      case "csv":
        tables = extractFromCsv(buffer);
        break;
      default:
        return {
          tables: [],
          totalRows: 0,
          fileType: ext || "unknown",
          error: `Unsupported file type: ${ext}`,
        };
    }

    const totalRows = tables.reduce((sum, t) => sum + t.rows.length, 0);

    return {
      tables,
      totalRows,
      fileType: ext?.toUpperCase() || "UNKNOWN",
    };
  } catch (error) {
    return {
      tables: [],
      totalRows: 0,
      fileType: ext || "unknown",
      error: String(error),
    };
  }
}
```

---

## Environment Variables

```bash
# Common settings
BULK_IMPORT_MAX_FILE_SIZE=52428800  # 50 MB

# Tesseract path (Windows)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Tesseract path (Linux/Mac - usually auto-detected)
# TESSERACT_CMD=/usr/bin/tesseract
```
