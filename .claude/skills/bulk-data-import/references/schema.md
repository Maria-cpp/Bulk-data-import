# Bulk Import Schemas

Generic validation schemas for request/response handling. Adapt to your framework.

## Core Data Structures

### Enums (shared across all frameworks)

```
ImportStatus: PENDING | PROCESSING | COMPLETED | FAILED | PARTIAL
DataFormat: JSON | CSV
SourceFileType: PDF | EXCEL | WORD | IMAGE | CSV
```

### Request Schemas

| Schema | Fields | Purpose |
|--------|--------|---------|
| `BulkImportUploadRequest` | parent_id, parent_type, data_format, column_mapping | Upload file request |
| `BulkImportProcessRequest` | import_id, create_records, column_mapping | Process extracted data |

### Response Schemas

| Schema | Fields | Purpose |
|--------|--------|---------|
| `ExtractedTablePreview` | headers, rows, total_rows, table_index | Preview of extracted table |
| `BulkImportUploadResponse` | id, parent_id, status, preview, message | Upload result |
| `BulkImportRead` | Full record with all fields | Complete import record |
| `BulkImportListItem` | id, source_file_name, status, total_rows, imported_at | Summary for list |

---

## Pydantic (Python - FastAPI/Flask)

```python
# schemas/bulk_import.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


class ImportStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class DataFormat(str, Enum):
    JSON = "JSON"
    CSV = "CSV"


class SourceFileType(str, Enum):
    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    IMAGE = "IMAGE"
    CSV = "CSV"


# ===== Request Schemas =====

class BulkImportUploadRequest(BaseModel):
    """Request for uploading a file for bulk import."""
    parent_id: Optional[UUID] = Field(None, description="Parent entity ID (optional)")
    parent_type: Optional[str] = Field(None, description="Parent entity type (e.g., 'contract', 'project')")
    data_format: DataFormat = Field(DataFormat.JSON, description="Output format: JSON or CSV")
    column_mapping: Optional[Dict[str, str]] = Field(
        None,
        description="Optional mapping: {source_column: target_field}"
    )


class BulkImportProcessRequest(BaseModel):
    """Request to process extracted data into records."""
    import_id: UUID = Field(..., description="Bulk import record ID")
    create_records: bool = Field(False, description="Actually create records")
    column_mapping: Optional[Dict[str, str]] = Field(
        None,
        description="Column mapping for record creation"
    )


# ===== Response Schemas =====

class ExtractedTablePreview(BaseModel):
    """Preview of extracted table data."""
    headers: List[str] = Field(..., description="Column headers")
    rows: List[List[Any]] = Field(..., description="Data rows (first N)")
    total_rows: int = Field(..., description="Total rows in the table")
    table_index: int = Field(0, description="Index if multiple tables found")

    class Config:
        from_attributes = True  # Pydantic v2 (use orm_mode=True for v1)


class BulkImportUploadResponse(BaseModel):
    """Response after file upload and extraction."""
    id: UUID
    parent_id: Optional[UUID] = None
    parent_type: Optional[str] = None
    source_file_name: str
    source_file_type: SourceFileType
    status: ImportStatus
    preview: Optional[List[ExtractedTablePreview]] = Field(
        None,
        description="Preview of extracted tables"
    )
    total_tables: int = Field(0, description="Number of tables found")
    message: str

    class Config:
        from_attributes = True


class BulkImportRead(BaseModel):
    """Full bulk import record for reading."""
    id: UUID
    parent_id: Optional[UUID] = None
    parent_type: Optional[str] = None
    asset_data: Optional[List[Dict[str, Any]]] = None
    asset_data_csv: Optional[str] = None
    data_format: DataFormat
    source_file_type: SourceFileType
    source_file_name: str
    source_file_size: Optional[int] = None
    status: ImportStatus
    total_rows: int
    successful_rows: int
    failed_rows: int
    error_message: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None
    preview_data: Optional[List[Dict[str, Any]]] = None
    imported_by: Optional[UUID] = None
    imported_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkImportListItem(BaseModel):
    """Summary item for listing bulk imports."""
    id: UUID
    parent_id: Optional[UUID] = None
    parent_type: Optional[str] = None
    source_file_name: str
    source_file_type: SourceFileType
    status: ImportStatus
    total_rows: int
    imported_at: datetime

    class Config:
        from_attributes = True


class BulkImportDataResponse(BaseModel):
    """Response for getting extracted data."""
    format: str = Field(..., description="'json' or 'csv'")
    data: Any = Field(..., description="JSON array or CSV string")
    total_rows: int


class BulkImportProcessResult(BaseModel):
    """Result of processing bulk import."""
    import_id: UUID
    status: ImportStatus
    total_rows: int
    successful_rows: int
    failed_rows: int
    created_ids: List[UUID] = []
    errors: List[Dict[str, Any]] = []
    message: str


# ===== Data Validation Schemas =====

class ExtractedRow(BaseModel):
    """Single row of extracted data."""
    row_number: int
    data: Dict[str, Any]
    is_valid: bool = True
    validation_errors: List[str] = []


class ExtractedDataTable(BaseModel):
    """Complete extracted data table."""
    headers: List[str]
    rows: List[ExtractedRow]
    total_rows: int
    valid_rows: int
    invalid_rows: int
```

---

## Zod (TypeScript - Express/NestJS)

```typescript
// schemas/bulk-import.schema.ts
import { z } from "zod";

// Enums
export const ImportStatusSchema = z.enum([
  "PENDING",
  "PROCESSING",
  "COMPLETED",
  "FAILED",
  "PARTIAL",
]);
export type ImportStatus = z.infer<typeof ImportStatusSchema>;

export const DataFormatSchema = z.enum(["JSON", "CSV"]);
export type DataFormat = z.infer<typeof DataFormatSchema>;

export const SourceFileTypeSchema = z.enum([
  "PDF",
  "EXCEL",
  "WORD",
  "IMAGE",
  "CSV",
]);
export type SourceFileType = z.infer<typeof SourceFileTypeSchema>;

// ===== Request Schemas =====

export const BulkImportUploadRequestSchema = z.object({
  parentId: z.string().uuid().optional(),
  parentType: z.string().max(50).optional(),
  dataFormat: DataFormatSchema.default("JSON"),
  columnMapping: z.record(z.string()).optional(),
});
export type BulkImportUploadRequest = z.infer<typeof BulkImportUploadRequestSchema>;

export const BulkImportProcessRequestSchema = z.object({
  importId: z.string().uuid(),
  createRecords: z.boolean().default(false),
  columnMapping: z.record(z.string()).optional(),
});
export type BulkImportProcessRequest = z.infer<typeof BulkImportProcessRequestSchema>;

// ===== Response Schemas =====

export const ExtractedTablePreviewSchema = z.object({
  headers: z.array(z.string()),
  rows: z.array(z.array(z.any())),
  totalRows: z.number(),
  tableIndex: z.number().default(0),
});
export type ExtractedTablePreview = z.infer<typeof ExtractedTablePreviewSchema>;

export const BulkImportUploadResponseSchema = z.object({
  id: z.string().uuid(),
  parentId: z.string().uuid().nullable().optional(),
  parentType: z.string().nullable().optional(),
  sourceFileName: z.string(),
  sourceFileType: SourceFileTypeSchema,
  status: ImportStatusSchema,
  preview: z.array(ExtractedTablePreviewSchema).nullable().optional(),
  totalTables: z.number().default(0),
  message: z.string(),
});
export type BulkImportUploadResponse = z.infer<typeof BulkImportUploadResponseSchema>;

export const BulkImportReadSchema = z.object({
  id: z.string().uuid(),
  parentId: z.string().uuid().nullable().optional(),
  parentType: z.string().nullable().optional(),
  assetData: z.array(z.record(z.any())).nullable().optional(),
  assetDataCsv: z.string().nullable().optional(),
  dataFormat: DataFormatSchema,
  sourceFileType: SourceFileTypeSchema,
  sourceFileName: z.string(),
  sourceFileSize: z.number().nullable().optional(),
  status: ImportStatusSchema,
  totalRows: z.number(),
  successfulRows: z.number(),
  failedRows: z.number(),
  errorMessage: z.string().nullable().optional(),
  columnMapping: z.record(z.string()).nullable().optional(),
  previewData: z.array(z.record(z.any())).nullable().optional(),
  importedBy: z.string().uuid().nullable().optional(),
  importedAt: z.string().datetime(),
  processedAt: z.string().datetime().nullable().optional(),
});
export type BulkImportRead = z.infer<typeof BulkImportReadSchema>;

export const BulkImportListItemSchema = z.object({
  id: z.string().uuid(),
  parentId: z.string().uuid().nullable().optional(),
  parentType: z.string().nullable().optional(),
  sourceFileName: z.string(),
  sourceFileType: SourceFileTypeSchema,
  status: ImportStatusSchema,
  totalRows: z.number(),
  importedAt: z.string().datetime(),
});
export type BulkImportListItem = z.infer<typeof BulkImportListItemSchema>;

export const BulkImportDataResponseSchema = z.object({
  format: z.enum(["json", "csv"]),
  data: z.any(),
  totalRows: z.number(),
});
export type BulkImportDataResponse = z.infer<typeof BulkImportDataResponseSchema>;
```

---

## TypeScript Interfaces (without Zod)

```typescript
// types/bulk-import.types.ts

export type ImportStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "PARTIAL";
export type DataFormat = "JSON" | "CSV";
export type SourceFileType = "PDF" | "EXCEL" | "WORD" | "IMAGE" | "CSV";

// Request types
export interface BulkImportUploadRequest {
  parentId?: string;
  parentType?: string;
  dataFormat?: DataFormat;
  columnMapping?: Record<string, string>;
}

export interface BulkImportProcessRequest {
  importId: string;
  createRecords?: boolean;
  columnMapping?: Record<string, string>;
}

// Response types
export interface ExtractedTablePreview {
  headers: string[];
  rows: (string | number | null)[][];
  totalRows: number;
  tableIndex: number;
}

export interface BulkImportUploadResponse {
  id: string;
  parentId?: string | null;
  parentType?: string | null;
  sourceFileName: string;
  sourceFileType: SourceFileType;
  status: ImportStatus;
  preview?: ExtractedTablePreview[] | null;
  totalTables: number;
  message: string;
}

export interface BulkImportRead {
  id: string;
  parentId?: string | null;
  parentType?: string | null;
  assetData?: Record<string, unknown>[] | null;
  assetDataCsv?: string | null;
  dataFormat: DataFormat;
  sourceFileType: SourceFileType;
  sourceFileName: string;
  sourceFileSize?: number | null;
  status: ImportStatus;
  totalRows: number;
  successfulRows: number;
  failedRows: number;
  errorMessage?: string | null;
  columnMapping?: Record<string, string> | null;
  previewData?: Record<string, unknown>[] | null;
  importedBy?: string | null;
  importedAt: string;
  processedAt?: string | null;
}

export interface BulkImportListItem {
  id: string;
  parentId?: string | null;
  parentType?: string | null;
  sourceFileName: string;
  sourceFileType: SourceFileType;
  status: ImportStatus;
  totalRows: number;
  importedAt: string;
}

export interface BulkImportDataResponse {
  format: "json" | "csv";
  data: Record<string, unknown>[] | string;
  totalRows: number;
}
```

---

## class-validator (NestJS)

```typescript
// dto/bulk-import.dto.ts
import {
  IsUUID,
  IsOptional,
  IsEnum,
  IsObject,
  IsString,
  IsBoolean,
  IsNumber,
  IsArray,
  ValidateNested,
} from "class-validator";
import { Type } from "class-transformer";

export enum ImportStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  PARTIAL = "PARTIAL",
}

export enum DataFormat {
  JSON = "JSON",
  CSV = "CSV",
}

export enum SourceFileType {
  PDF = "PDF",
  EXCEL = "EXCEL",
  WORD = "WORD",
  IMAGE = "IMAGE",
  CSV = "CSV",
}

// Request DTOs
export class BulkImportUploadDto {
  @IsOptional()
  @IsUUID()
  parentId?: string;

  @IsOptional()
  @IsString()
  parentType?: string;

  @IsOptional()
  @IsEnum(DataFormat)
  dataFormat?: DataFormat = DataFormat.JSON;

  @IsOptional()
  @IsObject()
  columnMapping?: Record<string, string>;
}

export class BulkImportProcessDto {
  @IsUUID()
  importId: string;

  @IsOptional()
  @IsBoolean()
  createRecords?: boolean = false;

  @IsOptional()
  @IsObject()
  columnMapping?: Record<string, string>;
}

// Response DTOs
export class ExtractedTablePreviewDto {
  @IsArray()
  headers: string[];

  @IsArray()
  rows: any[][];

  @IsNumber()
  totalRows: number;

  @IsNumber()
  tableIndex: number;
}

export class BulkImportUploadResponseDto {
  @IsUUID()
  id: string;

  @IsOptional()
  @IsUUID()
  parentId?: string;

  @IsOptional()
  @IsString()
  parentType?: string;

  @IsString()
  sourceFileName: string;

  @IsEnum(SourceFileType)
  sourceFileType: SourceFileType;

  @IsEnum(ImportStatus)
  status: ImportStatus;

  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => ExtractedTablePreviewDto)
  preview?: ExtractedTablePreviewDto[];

  @IsNumber()
  totalTables: number;

  @IsString()
  message: string;
}

export class BulkImportReadDto {
  @IsUUID()
  id: string;

  @IsOptional()
  @IsUUID()
  parentId?: string;

  @IsOptional()
  @IsString()
  parentType?: string;

  @IsOptional()
  assetData?: Record<string, unknown>[];

  @IsOptional()
  @IsString()
  assetDataCsv?: string;

  @IsEnum(DataFormat)
  dataFormat: DataFormat;

  @IsEnum(SourceFileType)
  sourceFileType: SourceFileType;

  @IsString()
  sourceFileName: string;

  @IsOptional()
  @IsNumber()
  sourceFileSize?: number;

  @IsEnum(ImportStatus)
  status: ImportStatus;

  @IsNumber()
  totalRows: number;

  @IsNumber()
  successfulRows: number;

  @IsNumber()
  failedRows: number;

  @IsOptional()
  @IsString()
  errorMessage?: string;

  @IsOptional()
  columnMapping?: Record<string, string>;

  @IsOptional()
  previewData?: Record<string, unknown>[];

  @IsOptional()
  @IsUUID()
  importedBy?: string;

  importedAt: Date;

  @IsOptional()
  processedAt?: Date;
}

export class BulkImportListItemDto {
  @IsUUID()
  id: string;

  @IsOptional()
  @IsUUID()
  parentId?: string;

  @IsOptional()
  @IsString()
  parentType?: string;

  @IsString()
  sourceFileName: string;

  @IsEnum(SourceFileType)
  sourceFileType: SourceFileType;

  @IsEnum(ImportStatus)
  status: ImportStatus;

  @IsNumber()
  totalRows: number;

  importedAt: Date;
}
```

---

## Django REST Framework Serializers

```python
# serializers.py
from rest_framework import serializers


class BulkImportUploadSerializer(serializers.Serializer):
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    parent_type = serializers.CharField(max_length=50, required=False, allow_null=True)
    data_format = serializers.ChoiceField(choices=["JSON", "CSV"], default="JSON")
    column_mapping = serializers.JSONField(required=False, allow_null=True)


class ExtractedTablePreviewSerializer(serializers.Serializer):
    headers = serializers.ListField(child=serializers.CharField())
    rows = serializers.ListField(child=serializers.ListField())
    total_rows = serializers.IntegerField()
    table_index = serializers.IntegerField(default=0)


class BulkImportUploadResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    parent_id = serializers.UUIDField(allow_null=True)
    parent_type = serializers.CharField(allow_null=True)
    source_file_name = serializers.CharField()
    source_file_type = serializers.ChoiceField(choices=["PDF", "EXCEL", "WORD", "IMAGE", "CSV"])
    status = serializers.ChoiceField(choices=["PENDING", "PROCESSING", "COMPLETED", "FAILED", "PARTIAL"])
    preview = ExtractedTablePreviewSerializer(many=True, allow_null=True)
    total_tables = serializers.IntegerField(default=0)
    message = serializers.CharField()


class BulkImportReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkImport  # Import your model
        fields = "__all__"


class BulkImportListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkImport
        fields = [
            "id",
            "parent_id",
            "parent_type",
            "source_file_name",
            "source_file_type",
            "status",
            "total_rows",
            "imported_at",
        ]
```

---

## Usage Patterns

### FastAPI Example

```python
from fastapi import APIRouter, UploadFile, File, Form, Depends
from .schemas import BulkImportUploadResponse, DataFormat

router = APIRouter()

@router.post("/upload", response_model=BulkImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    parent_id: str = Form(None),
    parent_type: str = Form(None),
    data_format: DataFormat = Form(DataFormat.JSON),
):
    # Implementation
    pass
```

### Express Example

```typescript
import { Router } from "express";
import multer from "multer";
import { BulkImportUploadRequestSchema } from "./schemas/bulk-import.schema";

const router = Router();
const upload = multer();

router.post("/upload", upload.single("file"), async (req, res) => {
  const body = BulkImportUploadRequestSchema.parse(req.body);
  // Implementation
});
```
