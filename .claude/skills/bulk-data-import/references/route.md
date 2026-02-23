# Bulk Import API Routes

API endpoint patterns for bulk data import. Framework-agnostic examples.

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bulk-imports/upload` | Upload file and extract tables |
| GET | `/api/bulk-imports` | List all imports (optional: filter by parent) |
| GET | `/api/bulk-imports/{id}` | Get full import record |
| GET | `/api/bulk-imports/{id}/data` | Get extracted data (JSON/CSV) |
| DELETE | `/api/bulk-imports/{id}` | Soft delete import |

---

## FastAPI (Python)

```python
# routes/bulk_import.py
"""Bulk Import API Routes for FastAPI"""

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import csv
import io

from ..database import get_db
from ..auth import get_current_user  # Your auth dependency
from ..services.bulk_import_service import bulk_import_service
from ..schemas.bulk_import import (
    BulkImportUploadResponse,
    BulkImportRead,
    BulkImportListItem,
    DataFormat
)

router = APIRouter(prefix="/bulk-imports", tags=["Bulk Imports"])


@router.post("/upload", response_model=BulkImportUploadResponse)
async def upload_and_extract(
    file: UploadFile = File(..., description="Document file (PDF, Excel, Word, Image, CSV)"),
    parent_id: Optional[UUID] = Form(None, description="Parent entity ID (optional)"),
    parent_type: Optional[str] = Form(None, description="Parent entity type (e.g., 'project', 'contract')"),
    data_format: DataFormat = Form(DataFormat.JSON, description="Output format: JSON or CSV"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Upload a document and extract table data.

    Supported file types:
    - PDF (.pdf) - Extracts tables using pdfplumber
    - Excel (.xlsx, .xls) - Extracts all sheets
    - Word (.docx, .doc) - Extracts tables from document
    - Image (.png, .jpg, .jpeg) - Uses OCR to extract text/tables
    - CSV (.csv) - Direct parsing

    Returns extracted data preview and stores full data for later retrieval.
    """
    try:
        result = await bulk_import_service.upload_and_extract(
            db=db,
            file=file,
            parent_id=parent_id,
            parent_type=parent_type,
            user_id=current_user.id if current_user else None,
            data_format=data_format
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("", response_model=List[BulkImportListItem])
async def list_imports(
    parent_id: Optional[UUID] = Query(None, description="Filter by parent entity ID"),
    parent_type: Optional[str] = Query(None, description="Filter by parent type"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    List bulk imports, optionally filtered by parent entity.
    """
    if parent_id:
        imports = await bulk_import_service.get_imports_by_parent(
            db, parent_id, parent_type
        )
    else:
        # Implement get_all_imports if needed
        imports = []

    return [BulkImportListItem.model_validate(i) for i in imports]


@router.get("/{import_id}", response_model=BulkImportRead)
async def get_import(
    import_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get a specific bulk import record with full data."""
    result = await bulk_import_service.get_import(db, import_id)
    if not result:
        raise HTTPException(status_code=404, detail="Bulk import not found")
    return BulkImportRead.model_validate(result)


@router.get("/{import_id}/data")
async def get_import_data(
    import_id: UUID,
    format: str = Query("json", description="Output format: json or csv"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get the extracted data from a bulk import.

    Args:
        import_id: Bulk import record ID
        format: Output format - 'json' for JSON array, 'csv' for CSV text

    Returns:
        JSON array of rows or CSV text string
    """
    record = await bulk_import_service.get_import(db, import_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bulk import not found")

    if format.lower() == "csv":
        if record.asset_data_csv:
            return {"format": "csv", "data": record.asset_data_csv, "total_rows": record.total_rows}
        elif record.asset_data:
            # Convert JSON to CSV
            output = io.StringIO()
            if record.asset_data:
                writer = csv.DictWriter(output, fieldnames=record.asset_data[0].keys())
                writer.writeheader()
                writer.writerows(record.asset_data)
            return {"format": "csv", "data": output.getvalue(), "total_rows": record.total_rows}
    else:
        if record.asset_data:
            return {"format": "json", "data": record.asset_data, "total_rows": record.total_rows}
        elif record.asset_data_csv:
            # Convert CSV to JSON
            reader = csv.DictReader(io.StringIO(record.asset_data_csv))
            return {"format": "json", "data": list(reader), "total_rows": record.total_rows}

    return {"format": format, "data": [], "total_rows": 0}


@router.delete("/{import_id}")
async def delete_import(
    import_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Delete a bulk import record (soft delete)."""
    deleted = await bulk_import_service.delete_import(db, import_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bulk import not found")

    await db.commit()
    return {"message": "Bulk import deleted successfully"}


# Register in main.py:
# from .routes.bulk_import import router as bulk_import_router
# app.include_router(bulk_import_router, prefix="/api")
```

---

## Flask (Python)

```python
# routes/bulk_import.py
"""Bulk Import API Routes for Flask"""

from flask import Blueprint, request, jsonify, g
from functools import wraps
import csv
import io

from ..services.bulk_import_service import bulk_import_service
from ..auth import login_required  # Your auth decorator

bp = Blueprint("bulk_imports", __name__, url_prefix="/api/bulk-imports")


def handle_errors(f):
    """Error handling decorator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500
    return decorated


@bp.route("/upload", methods=["POST"])
@login_required
@handle_errors
def upload_and_extract():
    """
    Upload a document and extract table data.

    Form data:
    - file: The document file
    - parent_id: Optional parent entity ID
    - parent_type: Optional parent entity type
    - data_format: JSON or CSV (default: JSON)
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    parent_id = request.form.get("parent_id")
    parent_type = request.form.get("parent_type")
    data_format = request.form.get("data_format", "JSON")

    result = bulk_import_service.upload_and_extract(
        file=file,
        parent_id=parent_id,
        parent_type=parent_type,
        user_id=g.current_user.id if hasattr(g, "current_user") else None,
        data_format=data_format
    )

    return jsonify(result), 201


@bp.route("", methods=["GET"])
@login_required
@handle_errors
def list_imports():
    """List bulk imports, optionally filtered by parent entity."""
    parent_id = request.args.get("parent_id")
    parent_type = request.args.get("parent_type")

    if parent_id:
        imports = bulk_import_service.get_imports_by_parent(parent_id, parent_type)
    else:
        imports = []

    return jsonify([
        {
            "id": str(i.id),
            "parent_id": str(i.parent_id) if i.parent_id else None,
            "parent_type": i.parent_type,
            "source_file_name": i.source_file_name,
            "source_file_type": i.source_file_type,
            "status": i.status,
            "total_rows": i.total_rows,
            "imported_at": i.imported_at.isoformat()
        }
        for i in imports
    ])


@bp.route("/<import_id>", methods=["GET"])
@login_required
@handle_errors
def get_import(import_id):
    """Get a specific bulk import record."""
    record = bulk_import_service.get_import(import_id)
    if not record:
        return jsonify({"error": "Bulk import not found"}), 404

    return jsonify({
        "id": str(record.id),
        "parent_id": str(record.parent_id) if record.parent_id else None,
        "parent_type": record.parent_type,
        "asset_data": record.asset_data,
        "asset_data_csv": record.asset_data_csv,
        "data_format": record.data_format,
        "source_file_type": record.source_file_type,
        "source_file_name": record.source_file_name,
        "source_file_size": record.source_file_size,
        "status": record.status,
        "total_rows": record.total_rows,
        "imported_at": record.imported_at.isoformat()
    })


@bp.route("/<import_id>/data", methods=["GET"])
@login_required
@handle_errors
def get_import_data(import_id):
    """Get the extracted data from a bulk import."""
    record = bulk_import_service.get_import(import_id)
    if not record:
        return jsonify({"error": "Bulk import not found"}), 404

    format = request.args.get("format", "json").lower()

    if format == "csv":
        if record.asset_data_csv:
            return jsonify({"format": "csv", "data": record.asset_data_csv, "total_rows": record.total_rows})
        elif record.asset_data:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=record.asset_data[0].keys())
            writer.writeheader()
            writer.writerows(record.asset_data)
            return jsonify({"format": "csv", "data": output.getvalue(), "total_rows": record.total_rows})
    else:
        if record.asset_data:
            return jsonify({"format": "json", "data": record.asset_data, "total_rows": record.total_rows})
        elif record.asset_data_csv:
            reader = csv.DictReader(io.StringIO(record.asset_data_csv))
            return jsonify({"format": "json", "data": list(reader), "total_rows": record.total_rows})

    return jsonify({"format": format, "data": [], "total_rows": 0})


@bp.route("/<import_id>", methods=["DELETE"])
@login_required
@handle_errors
def delete_import(import_id):
    """Delete a bulk import record (soft delete)."""
    deleted = bulk_import_service.delete_import(import_id)
    if not deleted:
        return jsonify({"error": "Bulk import not found"}), 404

    return jsonify({"message": "Bulk import deleted successfully"})


# Register in app factory:
# app.register_blueprint(bp)
```

---

## Express (Node.js/TypeScript)

```typescript
// routes/bulk-import.routes.ts
import { Router, Request, Response, NextFunction } from "express";
import multer from "multer";
import { v4 as uuidv4 } from "uuid";
import { extractTables } from "../services/table-extractor";
import { BulkImport } from "../models/bulk-import.model";
import { authMiddleware } from "../middleware/auth";

const router = Router();
const upload = multer({ storage: multer.memoryStorage() });

// Error handler wrapper
const asyncHandler = (fn: Function) => (req: Request, res: Response, next: NextFunction) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};

/**
 * POST /api/bulk-imports/upload
 * Upload a document and extract table data
 */
router.post(
  "/upload",
  authMiddleware,
  upload.single("file"),
  asyncHandler(async (req: Request, res: Response) => {
    if (!req.file) {
      return res.status(400).json({ error: "No file provided" });
    }

    const { parentId, parentType, dataFormat = "JSON" } = req.body;
    const file = req.file;

    // Extract tables
    const result = await extractTables(file.buffer, file.originalname);

    if (result.error) {
      return res.status(400).json({ error: result.error });
    }

    if (result.tables.length === 0) {
      return res.status(400).json({ error: "No tables found in the uploaded file" });
    }

    // Convert to storage format
    const allRows = result.tables.flatMap((t) =>
      t.rows.map((row) =>
        Object.fromEntries(t.headers.map((h, i) => [h, row[i] || ""]))
      )
    );

    // Create preview
    const previews = result.tables.map((t, idx) => ({
      headers: t.headers,
      rows: t.rows.slice(0, 10),
      totalRows: t.rows.length,
      tableIndex: idx,
      source: t.source,
    }));

    // Create import record
    const importRecord = await BulkImport.create({
      id: uuidv4(),
      parentId: parentId || null,
      parentType: parentType || null,
      assetData: dataFormat === "JSON" ? allRows : null,
      assetDataCsv: dataFormat === "CSV" ? convertToCsv(allRows) : null,
      dataFormat,
      sourceFileType: result.fileType,
      sourceFileName: file.originalname,
      sourceFileSize: file.size,
      status: "COMPLETED",
      totalRows: result.totalRows,
      successfulRows: result.totalRows,
      previewData: previews,
      importedBy: req.user?.id || null,
      importedAt: new Date(),
      processedAt: new Date(),
    });

    res.status(201).json({
      id: importRecord.id,
      parentId: importRecord.parentId,
      parentType: importRecord.parentType,
      sourceFileName: file.originalname,
      sourceFileType: result.fileType,
      status: "COMPLETED",
      preview: previews,
      totalTables: result.tables.length,
      message: `Extracted ${result.totalRows} rows from ${result.tables.length} table(s)`,
    });
  })
);

/**
 * GET /api/bulk-imports
 * List bulk imports
 */
router.get(
  "/",
  authMiddleware,
  asyncHandler(async (req: Request, res: Response) => {
    const { parentId, parentType } = req.query;

    const where: any = { deletedAt: null };
    if (parentId) where.parentId = parentId;
    if (parentType) where.parentType = parentType;

    const imports = await BulkImport.findAll({
      where,
      order: [["importedAt", "DESC"]],
      attributes: [
        "id",
        "parentId",
        "parentType",
        "sourceFileName",
        "sourceFileType",
        "status",
        "totalRows",
        "importedAt",
      ],
    });

    res.json(imports);
  })
);

/**
 * GET /api/bulk-imports/:id
 * Get a specific bulk import record
 */
router.get(
  "/:id",
  authMiddleware,
  asyncHandler(async (req: Request, res: Response) => {
    const record = await BulkImport.findOne({
      where: { id: req.params.id, deletedAt: null },
    });

    if (!record) {
      return res.status(404).json({ error: "Bulk import not found" });
    }

    res.json(record);
  })
);

/**
 * GET /api/bulk-imports/:id/data
 * Get extracted data from a bulk import
 */
router.get(
  "/:id/data",
  authMiddleware,
  asyncHandler(async (req: Request, res: Response) => {
    const record = await BulkImport.findOne({
      where: { id: req.params.id, deletedAt: null },
    });

    if (!record) {
      return res.status(404).json({ error: "Bulk import not found" });
    }

    const format = (req.query.format as string)?.toLowerCase() || "json";

    if (format === "csv") {
      const csvData = record.assetDataCsv || convertToCsv(record.assetData || []);
      return res.json({ format: "csv", data: csvData, totalRows: record.totalRows });
    }

    const jsonData = record.assetData || parseCsv(record.assetDataCsv || "");
    res.json({ format: "json", data: jsonData, totalRows: record.totalRows });
  })
);

/**
 * DELETE /api/bulk-imports/:id
 * Soft delete a bulk import
 */
router.delete(
  "/:id",
  authMiddleware,
  asyncHandler(async (req: Request, res: Response) => {
    const [updated] = await BulkImport.update(
      { deletedAt: new Date() },
      { where: { id: req.params.id, deletedAt: null } }
    );

    if (!updated) {
      return res.status(404).json({ error: "Bulk import not found" });
    }

    res.json({ message: "Bulk import deleted successfully" });
  })
);

// Helper functions
function convertToCsv(rows: Record<string, any>[]): string {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => `"${String(r[h] || "").replace(/"/g, '""')}"`).join(",")
    ),
  ];
  return lines.join("\n");
}

function parseCsv(csv: string): Record<string, any>[] {
  const lines = csv.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.replace(/^"|"$/g, "").trim());
    return Object.fromEntries(headers.map((h, i) => [h, values[i] || ""]));
  });
}

export default router;

// Register in app.ts:
// import bulkImportRoutes from "./routes/bulk-import.routes";
// app.use("/api/bulk-imports", bulkImportRoutes);
```

---

## Django REST Framework

```python
# views/bulk_import.py
"""Bulk Import API Views for Django REST Framework"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import csv
import io

from ..models import BulkImport
from ..serializers import (
    BulkImportUploadSerializer,
    BulkImportReadSerializer,
    BulkImportListItemSerializer
)
from ..services.bulk_import_service import bulk_import_service


class BulkImportViewSet(viewsets.ModelViewSet):
    """ViewSet for bulk import operations."""

    queryset = BulkImport.objects.filter(deleted_at__isnull=True)
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == "list":
            return BulkImportListItemSerializer
        return BulkImportReadSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        parent_id = self.request.query_params.get("parent_id")
        parent_type = self.request.query_params.get("parent_type")

        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if parent_type:
            queryset = queryset.filter(parent_type=parent_type)

        return queryset.order_by("-imported_at")

    @action(detail=False, methods=["post"])
    def upload(self, request):
        """Upload a document and extract table data."""
        serializer = BulkImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = bulk_import_service.upload_and_extract(
                file=file,
                parent_id=serializer.validated_data.get("parent_id"),
                parent_type=serializer.validated_data.get("parent_type"),
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                data_format=serializer.validated_data.get("data_format", "JSON")
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Extraction failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["get"])
    def data(self, request, pk=None):
        """Get extracted data from a bulk import."""
        instance = self.get_object()
        format = request.query_params.get("format", "json").lower()

        if format == "csv":
            if instance.asset_data_csv:
                data = instance.asset_data_csv
            elif instance.asset_data:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=instance.asset_data[0].keys())
                writer.writeheader()
                writer.writerows(instance.asset_data)
                data = output.getvalue()
            else:
                data = ""
            return Response({
                "format": "csv",
                "data": data,
                "total_rows": instance.total_rows
            })

        if instance.asset_data:
            data = instance.asset_data
        elif instance.asset_data_csv:
            reader = csv.DictReader(io.StringIO(instance.asset_data_csv))
            data = list(reader)
        else:
            data = []

        return Response({
            "format": "json",
            "data": data,
            "total_rows": instance.total_rows
        })

    def destroy(self, request, pk=None):
        """Soft delete a bulk import."""
        instance = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response({"message": "Bulk import deleted successfully"})


# Register in urls.py:
# from rest_framework.routers import DefaultRouter
# from .views.bulk_import import BulkImportViewSet
#
# router = DefaultRouter()
# router.register(r"bulk-imports", BulkImportViewSet)
#
# urlpatterns = [
#     path("api/", include(router.urls)),
# ]
```

---

## Example API Usage

### Upload PDF and Extract Tables

```bash
curl -X POST "http://localhost:8000/api/bulk-imports/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data.pdf" \
  -F "parent_id=uuid-here" \
  -F "parent_type=project" \
  -F "data_format=JSON"
```

### Response

```json
{
  "id": "uuid-of-import",
  "parentId": "uuid-of-project",
  "parentType": "project",
  "sourceFileName": "data.pdf",
  "sourceFileType": "PDF",
  "status": "COMPLETED",
  "preview": [
    {
      "headers": ["Name", "Value", "Date"],
      "rows": [
        ["Item A", "100", "2024-01-01"],
        ["Item B", "200", "2024-01-02"]
      ],
      "totalRows": 50,
      "tableIndex": 0
    }
  ],
  "totalTables": 1,
  "message": "Extracted 50 rows from 1 table(s)"
}
```

### Get Extracted Data as JSON

```bash
curl "http://localhost:8000/api/bulk-imports/{id}/data?format=json" \
  -H "Authorization: Bearer $TOKEN"
```

### Response

```json
{
  "format": "json",
  "data": [
    {"Name": "Item A", "Value": "100", "Date": "2024-01-01"},
    {"Name": "Item B", "Value": "200", "Date": "2024-01-02"}
  ],
  "totalRows": 50
}
```

### Get Extracted Data as CSV

```bash
curl "http://localhost:8000/api/bulk-imports/{id}/data?format=csv" \
  -H "Authorization: Bearer $TOKEN"
```

### Response

```json
{
  "format": "csv",
  "data": "Name,Value,Date\nItem A,100,2024-01-01\nItem B,200,2024-01-02",
  "totalRows": 50
}
```
