# Bulk Data Extraction - Project Guidelines

## Project Overview

Bulk data extraction tool for importing tabular data from documents (PDF, Excel, Word, Image, CSV) into databases. Supports JSON and CSV output formats.

## Before Any Implementation

### 1. Check Existing Skills

Before planning or implementing features, check `.claude/skills/` for existing implementation patterns:

```
.claude/skills/
├── bulk-data-import/       # Core extraction feature patterns
│   ├── SKILL.md            # Main skill with workflow and checklist
│   └── references/
│       ├── model.md        # Database model patterns
│       ├── schema.md       # Validation schema patterns
│       ├── service.md      # Extraction service patterns
│       ├── route.md        # API endpoint patterns
│       └── frontend.md     # UI component patterns
```

**When running speckit commands**:
- `/speckit.specify` - Extract user stories from skill documentation
- `/speckit.plan` - Use skill `references/` for technical design decisions
- `/speckit.tasks` - Map tasks to skill's Implementation Checklist
- `/speckit.implement` - Follow skill patterns exactly

### 2. Check Constitution

Read `.specify/memory/constitution.md` for project principles:

- **Data Integrity** - Preserve source data faithfully
- **Format Agnostic** - Pluggable extractor architecture
- **Error Transparency** - Clear, actionable errors
- **Security First** - Validate all file uploads
- **Simplicity** - YAGNI, avoid over-engineering

### 3. Check Existing Code

Before creating new files, search for existing implementations that can be extended.

## Tech Stack Flexibility

This project is stack-agnostic. Skills provide patterns for:
- **Python**: FastAPI/Flask + SQLAlchemy + pdfplumber/openpyxl
- **Node.js**: Express/Nest + TypeORM/Prisma + pdf-parse/xlsx

Determine the target stack from existing codebase or ask the user.

## File Structure Conventions

```
src/
├── models/          # Database models
├── services/        # Business logic (extractors here)
├── api/ or routes/  # API endpoints
└── schemas/         # Validation schemas

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests (per file format)
└── contract/        # API contract tests
```

## Key Reminders

- Always validate file types by content (magic bytes), not extension
- Store original file metadata alongside extracted data
- Use soft delete for all records
- Respect configured file size limits
- Tests SHOULD accompany implementation (Test-With approach)
