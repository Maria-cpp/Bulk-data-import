# Bulk Import Model

Generic model patterns for storing bulk imported data. Adapt to your ORM/database.

## Core Fields

Every bulk import model should include:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID/String | Primary key |
| `parent_id` | UUID/String | Link to parent entity (nullable) |
| `parent_type` | String | Type of parent (for polymorphic relations) |
| `asset_data` | JSON/JSONB | Extracted data as array of objects |
| `asset_data_csv` | Text | Alternative CSV storage |
| `data_format` | Enum | JSON or CSV |
| `source_file_type` | Enum | PDF, EXCEL, WORD, IMAGE, CSV |
| `source_file_name` | String | Original filename |
| `source_file_size` | Integer | File size in bytes |
| `status` | Enum | PENDING, PROCESSING, COMPLETED, FAILED |
| `total_rows` | Integer | Number of extracted rows |
| `imported_by` | UUID/String | User ID (optional) |
| `imported_at` | Timestamp | When imported |
| `created_at` | Timestamp | Record creation |
| `deleted_at` | Timestamp | Soft delete (nullable) |

## Enums

```python
# Python Enum pattern
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
```

```typescript
// TypeScript Enum pattern
enum ImportStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  PARTIAL = "PARTIAL"
}

enum DataFormat {
  JSON = "JSON",
  CSV = "CSV"
}

enum SourceFileType {
  PDF = "PDF",
  EXCEL = "EXCEL",
  WORD = "WORD",
  IMAGE = "IMAGE",
  CSV = "CSV"
}
```

---

## SQLAlchemy (Python)

```python
# models/bulk_import.py
from sqlalchemy import Column, String, DateTime, Text, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
import enum

from .base import Base  # Your base model


class ImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class DataFormat(str, enum.Enum):
    JSON = "JSON"
    CSV = "CSV"


class SourceFileType(str, enum.Enum):
    PDF = "PDF"
    EXCEL = "EXCEL"
    WORD = "WORD"
    IMAGE = "IMAGE"
    CSV = "CSV"


class BulkImport(Base):
    """Stores bulk imported data from documents."""
    __tablename__ = "bulk_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Flexible parent linking (adapt to your needs)
    parent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    parent_type = Column(String(50), nullable=True)  # e.g., "contract", "project"

    # Extracted data storage
    asset_data = Column(JSONB, nullable=True)
    asset_data_csv = Column(Text, nullable=True)
    data_format = Column(
        SQLEnum(DataFormat, name="data_format_enum", create_type=True),
        default=DataFormat.JSON,
        nullable=False
    )

    # Source file info
    source_file_type = Column(
        SQLEnum(SourceFileType, name="source_file_type_enum", create_type=True),
        nullable=False
    )
    source_file_name = Column(String(255), nullable=False)
    source_file_size = Column(Integer, nullable=True)
    storage_key = Column(String(500), nullable=True)  # For file storage reference

    # Processing status
    status = Column(
        SQLEnum(ImportStatus, name="import_status_enum", create_type=True),
        default=ImportStatus.PENDING,
        nullable=False
    )

    # Row counts
    total_rows = Column(Integer, default=0)
    successful_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # Column mapping (for data transformation)
    column_mapping = Column(JSONB, nullable=True)

    # Preview data
    preview_data = Column(JSONB, nullable=True)

    # Audit fields
    imported_by = Column(UUID(as_uuid=True), nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<BulkImport(id={self.id}, status={self.status}, rows={self.total_rows})>"
```

### SQLAlchemy Migration (Alembic)

```python
# alembic/versions/xxx_add_bulk_imports.py
"""Add bulk_imports table"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create enums
    import_status_enum = postgresql.ENUM(
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'PARTIAL',
        name='import_status_enum'
    )
    import_status_enum.create(op.get_bind(), checkfirst=True)

    data_format_enum = postgresql.ENUM('JSON', 'CSV', name='data_format_enum')
    data_format_enum.create(op.get_bind(), checkfirst=True)

    source_file_type_enum = postgresql.ENUM(
        'PDF', 'EXCEL', 'WORD', 'IMAGE', 'CSV',
        name='source_file_type_enum'
    )
    source_file_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'bulk_imports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('parent_type', sa.String(50), nullable=True),
        sa.Column('asset_data', postgresql.JSONB, nullable=True),
        sa.Column('asset_data_csv', sa.Text, nullable=True),
        sa.Column('data_format', sa.Enum('JSON', 'CSV', name='data_format_enum'),
                  default='JSON', nullable=False),
        sa.Column('source_file_type', sa.Enum('PDF', 'EXCEL', 'WORD', 'IMAGE', 'CSV',
                  name='source_file_type_enum'), nullable=False),
        sa.Column('source_file_name', sa.String(255), nullable=False),
        sa.Column('source_file_size', sa.Integer, nullable=True),
        sa.Column('storage_key', sa.String(500), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'PARTIAL',
                  name='import_status_enum'), default='PENDING', nullable=False),
        sa.Column('total_rows', sa.Integer, default=0),
        sa.Column('successful_rows', sa.Integer, default=0),
        sa.Column('failed_rows', sa.Integer, default=0),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_details', postgresql.JSONB, nullable=True),
        sa.Column('column_mapping', postgresql.JSONB, nullable=True),
        sa.Column('preview_data', postgresql.JSONB, nullable=True),
        sa.Column('imported_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('imported_at', sa.DateTime, default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
    )

    op.create_index('ix_bulk_imports_parent_id', 'bulk_imports', ['parent_id'])
    op.create_index('ix_bulk_imports_status', 'bulk_imports', ['status'])
    op.create_index('ix_bulk_imports_parent_type', 'bulk_imports', ['parent_type'])

def downgrade():
    op.drop_table('bulk_imports')
    op.execute("DROP TYPE IF EXISTS import_status_enum")
    op.execute("DROP TYPE IF EXISTS data_format_enum")
    op.execute("DROP TYPE IF EXISTS source_file_type_enum")
```

---

## Django ORM (Python)

```python
# models.py
from django.db import models
import uuid


class ImportStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    PARTIAL = "PARTIAL", "Partial"


class DataFormat(models.TextChoices):
    JSON = "JSON", "JSON"
    CSV = "CSV", "CSV"


class SourceFileType(models.TextChoices):
    PDF = "PDF", "PDF"
    EXCEL = "EXCEL", "Excel"
    WORD = "WORD", "Word"
    IMAGE = "IMAGE", "Image"
    CSV = "CSV", "CSV"


class BulkImport(models.Model):
    """Stores bulk imported data from documents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Flexible parent linking
    parent_id = models.UUIDField(null=True, blank=True, db_index=True)
    parent_type = models.CharField(max_length=50, null=True, blank=True)

    # Extracted data storage
    asset_data = models.JSONField(null=True, blank=True)
    asset_data_csv = models.TextField(null=True, blank=True)
    data_format = models.CharField(
        max_length=10,
        choices=DataFormat.choices,
        default=DataFormat.JSON
    )

    # Source file info
    source_file_type = models.CharField(max_length=10, choices=SourceFileType.choices)
    source_file_name = models.CharField(max_length=255)
    source_file_size = models.IntegerField(null=True, blank=True)
    storage_key = models.CharField(max_length=500, null=True, blank=True)

    # Processing status
    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING,
        db_index=True
    )

    # Row counts
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)

    # Error tracking
    error_message = models.TextField(null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True)

    # Column mapping
    column_mapping = models.JSONField(null=True, blank=True)
    preview_data = models.JSONField(null=True, blank=True)

    # Audit fields
    imported_by = models.UUIDField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bulk_imports"
        indexes = [
            models.Index(fields=['parent_type']),
        ]

    def __str__(self):
        return f"BulkImport({self.id}, {self.status}, {self.total_rows} rows)"
```

---

## Prisma (TypeScript/Node.js)

```prisma
// schema.prisma

enum ImportStatus {
  PENDING
  PROCESSING
  COMPLETED
  FAILED
  PARTIAL
}

enum DataFormat {
  JSON
  CSV
}

enum SourceFileType {
  PDF
  EXCEL
  WORD
  IMAGE
  CSV
}

model BulkImport {
  id              String          @id @default(uuid())

  // Flexible parent linking
  parentId        String?         @map("parent_id")
  parentType      String?         @map("parent_type") @db.VarChar(50)

  // Extracted data storage
  assetData       Json?           @map("asset_data")
  assetDataCsv    String?         @map("asset_data_csv") @db.Text
  dataFormat      DataFormat      @default(JSON) @map("data_format")

  // Source file info
  sourceFileType  SourceFileType  @map("source_file_type")
  sourceFileName  String          @map("source_file_name") @db.VarChar(255)
  sourceFileSize  Int?            @map("source_file_size")
  storageKey      String?         @map("storage_key") @db.VarChar(500)

  // Processing status
  status          ImportStatus    @default(PENDING)

  // Row counts
  totalRows       Int             @default(0) @map("total_rows")
  successfulRows  Int             @default(0) @map("successful_rows")
  failedRows      Int             @default(0) @map("failed_rows")

  // Error tracking
  errorMessage    String?         @map("error_message") @db.Text
  errorDetails    Json?           @map("error_details")

  // Column mapping
  columnMapping   Json?           @map("column_mapping")
  previewData     Json?           @map("preview_data")

  // Audit fields
  importedBy      String?         @map("imported_by")
  importedAt      DateTime        @default(now()) @map("imported_at")
  processedAt     DateTime?       @map("processed_at")
  createdAt       DateTime        @default(now()) @map("created_at")
  updatedAt       DateTime        @updatedAt @map("updated_at")
  deletedAt       DateTime?       @map("deleted_at")

  @@index([parentId])
  @@index([status])
  @@index([parentType])
  @@map("bulk_imports")
}
```

---

## TypeORM (TypeScript/Node.js)

```typescript
// entities/bulk-import.entity.ts
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from "typeorm";

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

@Entity("bulk_imports")
export class BulkImport {
  @PrimaryGeneratedColumn("uuid")
  id: string;

  @Column({ type: "uuid", nullable: true })
  @Index()
  parentId: string | null;

  @Column({ type: "varchar", length: 50, nullable: true })
  @Index()
  parentType: string | null;

  @Column({ type: "jsonb", nullable: true })
  assetData: Record<string, unknown>[] | null;

  @Column({ type: "text", nullable: true })
  assetDataCsv: string | null;

  @Column({ type: "enum", enum: DataFormat, default: DataFormat.JSON })
  dataFormat: DataFormat;

  @Column({ type: "enum", enum: SourceFileType })
  sourceFileType: SourceFileType;

  @Column({ type: "varchar", length: 255 })
  sourceFileName: string;

  @Column({ type: "int", nullable: true })
  sourceFileSize: number | null;

  @Column({ type: "varchar", length: 500, nullable: true })
  storageKey: string | null;

  @Column({ type: "enum", enum: ImportStatus, default: ImportStatus.PENDING })
  @Index()
  status: ImportStatus;

  @Column({ type: "int", default: 0 })
  totalRows: number;

  @Column({ type: "int", default: 0 })
  successfulRows: number;

  @Column({ type: "int", default: 0 })
  failedRows: number;

  @Column({ type: "text", nullable: true })
  errorMessage: string | null;

  @Column({ type: "jsonb", nullable: true })
  errorDetails: Record<string, unknown> | null;

  @Column({ type: "jsonb", nullable: true })
  columnMapping: Record<string, string> | null;

  @Column({ type: "jsonb", nullable: true })
  previewData: Record<string, unknown>[] | null;

  @Column({ type: "uuid", nullable: true })
  importedBy: string | null;

  @Column({ type: "timestamp", default: () => "CURRENT_TIMESTAMP" })
  importedAt: Date;

  @Column({ type: "timestamp", nullable: true })
  processedAt: Date | null;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;

  @Column({ type: "timestamp", nullable: true })
  deletedAt: Date | null;
}
```

---

## Raw SQL (Any Database)

### PostgreSQL

```sql
CREATE TYPE import_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'PARTIAL');
CREATE TYPE data_format AS ENUM ('JSON', 'CSV');
CREATE TYPE source_file_type AS ENUM ('PDF', 'EXCEL', 'WORD', 'IMAGE', 'CSV');

CREATE TABLE bulk_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID,
    parent_type VARCHAR(50),
    asset_data JSONB,
    asset_data_csv TEXT,
    data_format data_format NOT NULL DEFAULT 'JSON',
    source_file_type source_file_type NOT NULL,
    source_file_name VARCHAR(255) NOT NULL,
    source_file_size INTEGER,
    storage_key VARCHAR(500),
    status import_status NOT NULL DEFAULT 'PENDING',
    total_rows INTEGER DEFAULT 0,
    successful_rows INTEGER DEFAULT 0,
    failed_rows INTEGER DEFAULT 0,
    error_message TEXT,
    error_details JSONB,
    column_mapping JSONB,
    preview_data JSONB,
    imported_by UUID,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_bulk_imports_parent_id ON bulk_imports(parent_id);
CREATE INDEX idx_bulk_imports_status ON bulk_imports(status);
CREATE INDEX idx_bulk_imports_parent_type ON bulk_imports(parent_type);
```

### MySQL

```sql
CREATE TABLE bulk_imports (
    id CHAR(36) PRIMARY KEY,
    parent_id CHAR(36),
    parent_type VARCHAR(50),
    asset_data JSON,
    asset_data_csv LONGTEXT,
    data_format ENUM('JSON', 'CSV') NOT NULL DEFAULT 'JSON',
    source_file_type ENUM('PDF', 'EXCEL', 'WORD', 'IMAGE', 'CSV') NOT NULL,
    source_file_name VARCHAR(255) NOT NULL,
    source_file_size INT,
    storage_key VARCHAR(500),
    status ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'PARTIAL') NOT NULL DEFAULT 'PENDING',
    total_rows INT DEFAULT 0,
    successful_rows INT DEFAULT 0,
    failed_rows INT DEFAULT 0,
    error_message TEXT,
    error_details JSON,
    column_mapping JSON,
    preview_data JSON,
    imported_by CHAR(36),
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    INDEX idx_parent_id (parent_id),
    INDEX idx_status (status),
    INDEX idx_parent_type (parent_type)
);
```

---

## Linking to Parent Entity

The `parent_id` and `parent_type` fields allow flexible linking to any entity:

```python
# Example: Link to Contract
bulk_import = BulkImport(
    parent_id=contract.id,
    parent_type="contract",
    # ...
)

# Example: Link to Project
bulk_import = BulkImport(
    parent_id=project.id,
    parent_type="project",
    # ...
)

# Query by parent
imports = BulkImport.query.filter_by(
    parent_id=contract.id,
    parent_type="contract"
).all()
```

For strict foreign key constraints, add a specific relationship:

```python
# If you need strict FK to a specific table:
contract_id = Column(
    UUID(as_uuid=True),
    ForeignKey("contracts.id", ondelete="CASCADE"),
    nullable=True
)
contract = relationship("Contract", back_populates="bulk_imports")
```
