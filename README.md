
# 📦 Bulk Data Import Module

Bulk data import system for extracting tabular data from documents (PDF, Excel, Word, Image, CSV) and storing it in structured database format (JSON or CSV).

This module enables automated table extraction and conversion of document data into database-ready records.

---

## 🚀 Purpose

Use this module when:

- Users want to import data in bulk from documents
- Tables need to be extracted from PDF, Excel, Word, Image (OCR), or CSV
- Document tables must be converted into structured database records
- The system requires preview, validation, and structured import history
- Keywords like:
  - bulk import
  - data extraction
  - table parsing
  - OCR import
  - document to database

---

## 🏗 Architecture Overview

Upload Document → Extract Tables → Normalize Data → Store JSON/CSV → Save Metadata

---

## 📂 Supported File Types

| Type  | Extension |
|-------|----------|
| PDF   | .pdf     |
| Excel | .xlsx, .xls |
| Word  | .docx, .doc |
| Image | .png, .jpg, .jpeg |
| CSV   | .csv     |

---

## 🛠 Installation (Python)

pip install pdfplumber openpyxl python-docx pytesseract Pillow pandas

For OCR:
- Windows: Install Tesseract manually
- Linux: sudo apt-get install tesseract-ocr
- Docker: RUN apt-get update && apt-get install -y tesseract-ocr

---

## 🗄 Database Schema (Generic)

CREATE TABLE bulk_imports (
    id UUID PRIMARY KEY,
    parent_id UUID,
    parent_type VARCHAR(50),
    asset_data JSONB,
    asset_data_csv TEXT,
    data_format VARCHAR(10),
    source_file_type VARCHAR(10),
    source_file_name VARCHAR(255),
    source_file_size INTEGER,
    status VARCHAR(20),
    total_rows INTEGER,
    imported_by UUID,
    imported_at TIMESTAMP,
    created_at TIMESTAMP,
    deleted_at TIMESTAMP
);

---

## 🔐 Status Lifecycle

- PENDING
- PROCESSING
- COMPLETED
- FAILED

---

## ⚙ Configuration

Environment Variables:

BULK_IMPORT_MAX_FILE_SIZE=52428800
TESSERACT_CMD=Path to tesseract executable

---

## 📋 Implementation Checklist

- Add dependencies
- Create model
- Run database migration
- Create validation schemas
- Implement extraction service
- Add API routes
- Register router
- Create frontend upload component
- Create preview table
- Test with sample files

---

## 📦 Use Cases

- Import vendor asset lists
- Extract inventory data from PDFs
- Convert scanned documents to structured data
- Upload Excel sheets to auto-create database entries
- OCR invoice parsing

---

## 🎯 Summary

This module provides a production-ready, extensible system for extracting structured data from documents and importing it into your application database with validation, tracking, and flexible integration support.
