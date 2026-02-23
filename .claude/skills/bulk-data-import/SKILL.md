---
name: bulk-data-import
description: |
  Bulk data import from documents (PDF, Excel, Word, Image) to database.
  Extracts table data from uploaded files and stores as JSON or CSV.
  Use when: (1) User wants to import data in bulk from documents, (2) User needs to extract tables from PDF/Excel/Word/Image files, (3) User wants to convert document tables to database records, (4) User mentions "bulk import", "data extraction", "table parsing", or "OCR import".
---

# Bulk Data Import

Extract and import tabular data from documents (PDF, Excel, Word, Image, CSV) into any database or application.

## Before Implementation

Gather context to ensure successful integration:

| Source | Gather |
|--------|--------|
| **Codebase** | Existing models, ORM (SQLAlchemy/Django/Prisma/etc.), API framework (FastAPI/Flask/Express/etc.), frontend framework |
| **Conversation** | What entity should imports be linked to? What fields are needed? Authentication approach? |
| **Skill References** | Extraction patterns from `references/`, adapt examples to project's stack |
| **User Guidelines** | Project-specific conventions, folder structure, naming patterns |

## Quick Decision Tree

```
1. What backend framework?
   ├── FastAPI/Flask → See references/service.md (Python patterns)
   ├── Express/Nest → Adapt to TypeScript, use similar extraction libs
   └── Django → Use Django ORM patterns, adapt service layer

2. What database/ORM?
   ├── SQLAlchemy → See references/model.md
   ├── Django ORM → Convert to Django model syntax
   ├── Prisma → Convert to Prisma schema
   └── TypeORM → Convert to TypeORM entity

3. What frontend?
   ├── React/Next.js → See references/frontend.md
   ├── Vue/Nuxt → Adapt component patterns
   └── Angular → Adapt to Angular components
```

## Core Workflow

```
+------------------+     +-------------------+     +-----------------+
| Upload Document  | --> | Extract Tables    | --> | Store Data      |
| (PDF/Excel/etc.) |     | (type-specific)   |     | (JSON/CSV)      |
+------------------+     +-------------------+     +-----------------+
                                |
              +-----------------+------------------+
              |                 |                  |
       +------v------+  +-------v-------+  +-------v-------+
       |PDFExtractor |  |ExcelExtractor |  |ImageExtractor |
       |WordExtractor|  |CSVExtractor   |  |(OCR)          |
       +-------------+  +---------------+  +---------------+
```

## Implementation Steps

### 1. Add Dependencies

**Python:**
```bash
pip install pdfplumber openpyxl python-docx pytesseract Pillow pandas
```

**Node.js alternative:**
```bash
npm install pdf-parse xlsx mammoth tesseract.js
```

For Image OCR, also install Tesseract:
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt-get install tesseract-ocr`
- Docker: `RUN apt-get update && apt-get install -y tesseract-ocr`

### 2. Create Data Model

See [references/model.md](references/model.md) for:
- Generic model structure (adapt to your ORM)
- Required fields: `id`, `parent_id`, `asset_data`, `source_file_*`, `status`
- Migration patterns

### 3. Create Validation Schemas

See [references/schema.md](references/schema.md) for:
- Request/response validation (Pydantic, Zod, class-validator)
- Preview data structures
- Error response formats

### 4. Create Extraction Service

See [references/service.md](references/service.md) for:
- File type detection
- Type-specific extractors (PDF, Excel, Word, Image, CSV)
- Table normalization
- Error handling patterns

### 5. Create API Routes

See [references/route.md](references/route.md) for:
- Upload endpoint (multipart form)
- List/get endpoints
- Data retrieval (JSON/CSV format)
- Delete endpoint

### 6. Create Frontend

See [references/frontend.md](references/frontend.md) for:
- File upload component with preview
- Data table display with pagination
- Import history list

## Generic Database Schema

Adapt to your ORM:

```sql
CREATE TABLE bulk_imports (
    id UUID PRIMARY KEY,
    parent_id UUID,                    -- Link to parent entity (contract, project, etc.)
    parent_type VARCHAR(50),           -- Type of parent entity (for polymorphic relations)
    asset_data JSONB,                  -- Extracted data as JSON array
    asset_data_csv TEXT,               -- Alternative: CSV text
    data_format VARCHAR(10),           -- 'JSON' or 'CSV'
    source_file_type VARCHAR(10),      -- PDF, EXCEL, WORD, IMAGE, CSV
    source_file_name VARCHAR(255),
    source_file_size INTEGER,
    status VARCHAR(20),                -- PENDING, PROCESSING, COMPLETED, FAILED
    total_rows INTEGER,
    imported_by UUID,                  -- User who imported (optional)
    imported_at TIMESTAMP,
    created_at TIMESTAMP,
    deleted_at TIMESTAMP               -- Soft delete
);
```

## File Type Support

| Type | Extension | Python Library | Node.js Library |
|------|-----------|----------------|-----------------|
| PDF | .pdf | pdfplumber | pdf-parse |
| Excel | .xlsx, .xls | openpyxl | xlsx |
| Word | .docx, .doc | python-docx | mammoth |
| Image | .png, .jpg, .jpeg | pytesseract | tesseract.js |
| CSV | .csv | csv module | csv-parse |

## Configuration

```bash
# Environment variables
BULK_IMPORT_MAX_FILE_SIZE=52428800  # 50 MB

# For Windows Tesseract
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Standalone Extraction Script

For CLI usage or testing without full app integration:

```bash
# Extract and output JSON
python scripts/extract_tables.py assets.pdf --output extracted.json

# Extract and output CSV
python scripts/extract_tables.py data.xlsx --format csv --output extracted.csv
```

See [scripts/extract_tables.py](scripts/extract_tables.py) for full standalone script.

## Implementation Checklist

Adapt to your project structure:

- [ ] Add dependencies to requirements.txt/package.json
- [ ] Create bulk import model (adapt path to your project)
- [ ] Run database migration
- [ ] Create validation schemas
- [ ] Implement extraction service
- [ ] Add API routes
- [ ] Register router in main app
- [ ] Create frontend service layer
- [ ] Create upload component
- [ ] Create data table component
- [ ] Test with sample documents

## Resources

- [Model Definition](references/model.md) - Generic model patterns for any ORM
- [Schema Definitions](references/schema.md) - Validation schemas for any framework
- [Service Implementation](references/service.md) - File extraction service
- [API Routes](references/route.md) - Endpoint patterns for any framework
- [Frontend Components](references/frontend.md) - UI components for any framework
