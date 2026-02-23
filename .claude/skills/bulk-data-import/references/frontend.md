# Frontend Components

UI components for bulk data import. Framework-agnostic patterns.

## Components Overview

| Component | Purpose |
|-----------|---------|
| `BulkImportUpload` | File upload with drag-drop and preview |
| `BulkImportDataTable` | Paginated data table display |
| `BulkImportList` | Import history list |

---

## API Service Layer

### React/Next.js (TypeScript)

```typescript
// services/bulk-import.service.ts

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Types
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
  sourceFileType: "PDF" | "EXCEL" | "WORD" | "IMAGE" | "CSV";
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "PARTIAL";
  preview: ExtractedTablePreview[] | null;
  totalTables: number;
  message: string;
}

export interface BulkImportRecord {
  id: string;
  parentId?: string | null;
  parentType?: string | null;
  assetData: Record<string, unknown>[] | null;
  assetDataCsv: string | null;
  dataFormat: "JSON" | "CSV";
  sourceFileType: string;
  sourceFileName: string;
  status: string;
  totalRows: number;
  importedAt: string;
}

export interface BulkImportListItem {
  id: string;
  parentId?: string | null;
  parentType?: string | null;
  sourceFileName: string;
  sourceFileType: string;
  status: string;
  totalRows: number;
  importedAt: string;
}

// API Functions

export async function uploadBulkImport(
  file: File,
  options: {
    parentId?: string;
    parentType?: string;
    dataFormat?: "JSON" | "CSV";
  } = {}
): Promise<BulkImportUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options.parentId) formData.append("parent_id", options.parentId);
  if (options.parentType) formData.append("parent_type", options.parentType);
  formData.append("data_format", options.dataFormat || "JSON");

  const res = await fetch(`${BASE_URL}/bulk-imports/upload`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || err.error || "Failed to upload file");
  }

  return res.json();
}

export async function fetchImports(
  parentId?: string,
  parentType?: string
): Promise<BulkImportListItem[]> {
  const params = new URLSearchParams();
  if (parentId) params.append("parent_id", parentId);
  if (parentType) params.append("parent_type", parentType);

  const url = `${BASE_URL}/bulk-imports${params.toString() ? `?${params}` : ""}`;
  const res = await fetch(url, { headers: getAuthHeaders() });

  if (!res.ok) throw new Error("Failed to fetch imports");
  return res.json();
}

export async function fetchImportData(
  importId: string,
  format: "json" | "csv" = "json"
): Promise<{ format: string; data: Record<string, unknown>[] | string; totalRows: number }> {
  const res = await fetch(
    `${BASE_URL}/bulk-imports/${importId}/data?format=${format}`,
    { headers: getAuthHeaders() }
  );

  if (!res.ok) throw new Error("Failed to fetch import data");
  return res.json();
}

export async function deleteImport(importId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/bulk-imports/${importId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!res.ok) throw new Error("Failed to delete import");
}
```

### Vue 3 (TypeScript)

```typescript
// services/bulk-import.service.ts
import { ref } from "vue";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Same types as React version...

export function useBulkImport() {
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function uploadFile(
    file: File,
    options: { parentId?: string; parentType?: string; dataFormat?: "JSON" | "CSV" } = {}
  ) {
    loading.value = true;
    error.value = null;

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (options.parentId) formData.append("parent_id", options.parentId);
      if (options.parentType) formData.append("parent_type", options.parentType);
      formData.append("data_format", options.dataFormat || "JSON");

      const res = await fetch(`${BASE_URL}/bulk-imports/upload`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || err.error || "Upload failed");
      }

      return await res.json();
    } catch (e) {
      error.value = (e as Error).message;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  return { loading, error, uploadFile };
}
```

---

## Upload Component

### React/Next.js

```tsx
// components/BulkImportUpload.tsx
"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  uploadBulkImport,
  BulkImportUploadResponse,
  ExtractedTablePreview,
} from "@/services/bulk-import.service";

interface BulkImportUploadProps {
  parentId?: string;
  parentType?: string;
  onUploadSuccess?: (response: BulkImportUploadResponse) => void;
  onUploadError?: (error: Error) => void;
}

const humanFileSize = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

export default function BulkImportUpload({
  parentId,
  parentType,
  onUploadSuccess,
  onUploadError,
}: BulkImportUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataFormat, setDataFormat] = useState<"JSON" | "CSV">("JSON");
  const [response, setResponse] = useState<BulkImportUploadResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptedTypes = ".pdf,.xlsx,.xls,.docx,.doc,.png,.jpg,.jpeg,.csv";

  const handleFile = useCallback((selectedFile: File) => {
    setFile(selectedFile);
    setResponse(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    try {
      const result = await uploadBulkImport(file, {
        parentId,
        parentType,
        dataFormat,
      });
      setResponse(result);
      onUploadSuccess?.(result);
    } catch (error) {
      onUploadError?.(error as Error);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setResponse(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="rounded-lg border p-6 bg-white dark:bg-gray-800">
      <h3 className="text-lg font-semibold mb-4">Bulk Data Import</h3>

      {/* Drop Zone */}
      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors
          ${dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300"}
          ${file ? "border-green-500 bg-green-50" : ""}
        `}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptedTypes}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          className="hidden"
        />

        {file ? (
          <div>
            <p className="font-medium">{file.name}</p>
            <p className="text-sm text-gray-500">{humanFileSize(file.size)}</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleClear();
              }}
              className="mt-2 text-red-500 hover:underline text-sm"
            >
              Remove
            </button>
          </div>
        ) : (
          <div>
            <p className="text-gray-600">
              Drag & drop a file here, or click to select
            </p>
            <p className="text-sm text-gray-400 mt-1">
              PDF, Excel, Word, Image, or CSV
            </p>
          </div>
        )}
      </div>

      {/* Format Selection */}
      <div className="mt-4 flex items-center gap-4">
        <span className="text-sm font-medium">Output Format:</span>
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="radio"
            name="format"
            checked={dataFormat === "JSON"}
            onChange={() => setDataFormat("JSON")}
          />
          <span>JSON</span>
        </label>
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="radio"
            name="format"
            checked={dataFormat === "CSV"}
            onChange={() => setDataFormat("CSV")}
          />
          <span>CSV</span>
        </label>
      </div>

      {/* Upload Button */}
      <button
        onClick={handleUpload}
        disabled={!file || loading}
        className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg
                   disabled:opacity-50 disabled:cursor-not-allowed
                   hover:bg-blue-700 transition-colors"
      >
        {loading ? "Extracting..." : "Upload & Extract"}
      </button>

      {/* Preview */}
      {response?.preview && (
        <div className="mt-6">
          <h4 className="font-semibold mb-2">
            Preview ({response.totalTables} table(s),{" "}
            {response.preview.reduce((s, t) => s + t.totalRows, 0)} total rows)
          </h4>
          {response.preview.map((table, idx) => (
            <TablePreview key={idx} table={table} />
          ))}
        </div>
      )}
    </div>
  );
}

function TablePreview({ table }: { table: ExtractedTablePreview }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <p className="text-sm text-gray-500 mb-2">
        Table {table.tableIndex + 1}: {table.totalRows} rows
      </p>
      <table className="min-w-full border">
        <thead className="bg-gray-50">
          <tr>
            {table.headers.map((h, i) => (
              <th key={i} className="px-4 py-2 text-left text-sm font-semibold border-b">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.slice(0, 5).map((row, ri) => (
            <tr key={ri} className="hover:bg-gray-50">
              {row.map((cell, ci) => (
                <td key={ci} className="px-4 py-2 text-sm border-b">
                  {String(cell ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.totalRows > 5 && (
        <p className="text-sm text-gray-500 mt-1">
          Showing 5 of {table.totalRows} rows
        </p>
      )}
    </div>
  );
}
```

### Vue 3

```vue
<!-- components/BulkImportUpload.vue -->
<template>
  <div class="rounded-lg border p-6 bg-white dark:bg-gray-800">
    <h3 class="text-lg font-semibold mb-4">Bulk Data Import</h3>

    <!-- Drop Zone -->
    <div
      :class="[
        'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
        dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300',
        file ? 'border-green-500 bg-green-50' : ''
      ]"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="handleDrop"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="acceptedTypes"
        class="hidden"
        @change="handleFileChange"
      />

      <div v-if="file">
        <p class="font-medium">{{ file.name }}</p>
        <p class="text-sm text-gray-500">{{ humanFileSize(file.size) }}</p>
        <button
          class="mt-2 text-red-500 hover:underline text-sm"
          @click.stop="handleClear"
        >
          Remove
        </button>
      </div>
      <div v-else>
        <p class="text-gray-600">Drag & drop a file here, or click to select</p>
        <p class="text-sm text-gray-400 mt-1">PDF, Excel, Word, Image, or CSV</p>
      </div>
    </div>

    <!-- Format Selection -->
    <div class="mt-4 flex items-center gap-4">
      <span class="text-sm font-medium">Output Format:</span>
      <label class="flex items-center gap-1 cursor-pointer">
        <input type="radio" v-model="dataFormat" value="JSON" />
        <span>JSON</span>
      </label>
      <label class="flex items-center gap-1 cursor-pointer">
        <input type="radio" v-model="dataFormat" value="CSV" />
        <span>CSV</span>
      </label>
    </div>

    <!-- Upload Button -->
    <button
      :disabled="!file || loading"
      class="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg
             disabled:opacity-50 disabled:cursor-not-allowed
             hover:bg-blue-700 transition-colors"
      @click="handleUpload"
    >
      {{ loading ? 'Extracting...' : 'Upload & Extract' }}
    </button>

    <!-- Preview -->
    <div v-if="response?.preview" class="mt-6">
      <h4 class="font-semibold mb-2">
        Preview ({{ response.totalTables }} table(s))
      </h4>
      <TablePreview
        v-for="(table, idx) in response.preview"
        :key="idx"
        :table="table"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { uploadBulkImport, type BulkImportUploadResponse } from '@/services/bulk-import.service';

interface Props {
  parentId?: string;
  parentType?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'success', response: BulkImportUploadResponse): void;
  (e: 'error', error: Error): void;
}>();

const acceptedTypes = '.pdf,.xlsx,.xls,.docx,.doc,.png,.jpg,.jpeg,.csv';

const file = ref<File | null>(null);
const loading = ref(false);
const dataFormat = ref<'JSON' | 'CSV'>('JSON');
const response = ref<BulkImportUploadResponse | null>(null);
const dragOver = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const humanFileSize = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement;
  if (target.files?.[0]) {
    file.value = target.files[0];
    response.value = null;
  }
};

const handleDrop = (e: DragEvent) => {
  dragOver.value = false;
  const droppedFile = e.dataTransfer?.files[0];
  if (droppedFile) {
    file.value = droppedFile;
    response.value = null;
  }
};

const handleClear = () => {
  file.value = null;
  response.value = null;
  if (fileInput.value) fileInput.value.value = '';
};

const handleUpload = async () => {
  if (!file.value) return;

  loading.value = true;
  try {
    const result = await uploadBulkImport(file.value, {
      parentId: props.parentId,
      parentType: props.parentType,
      dataFormat: dataFormat.value,
    });
    response.value = result;
    emit('success', result);
  } catch (error) {
    emit('error', error as Error);
  } finally {
    loading.value = false;
  }
};
</script>
```

---

## Data Table Component

### React/Next.js

```tsx
// components/BulkImportDataTable.tsx
"use client";

import React, { useState, useEffect } from "react";
import { fetchImportData } from "@/services/bulk-import.service";

interface Props {
  importId: string;
  pageSize?: number;
}

export default function BulkImportDataTable({ importId, pageSize = 20 }: Props) {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const result = await fetchImportData(importId, "json");
        if (Array.isArray(result.data)) {
          setData(result.data);
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [importId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return <div className="p-4 bg-red-50 text-red-600 rounded-lg">Error: {error}</div>;
  }

  if (!data.length) {
    return <div className="p-4 text-gray-500">No data available</div>;
  }

  const headers = Object.keys(data[0]);
  const totalPages = Math.ceil(data.length / pageSize);
  const paginatedData = data.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="rounded-lg border bg-white">
      {/* Header */}
      <div className="p-4 border-b flex justify-between items-center">
        <span className="font-semibold">{data.length} rows</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1 rounded border disabled:opacity-50"
          >
            Prev
          </button>
          <span className="text-sm">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 rounded border disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-semibold border-b">#</th>
              {headers.map((h) => (
                <th key={h} className="px-4 py-2 text-left text-sm font-semibold border-b">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm border-b text-gray-500">
                  {(page - 1) * pageSize + idx + 1}
                </td>
                {headers.map((h) => (
                  <td key={h} className="px-4 py-2 text-sm border-b">
                    {String(row[h] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## Import List Component

### React/Next.js

```tsx
// components/BulkImportList.tsx
"use client";

import React, { useState, useEffect } from "react";
import {
  fetchImports,
  deleteImport,
  BulkImportListItem,
} from "@/services/bulk-import.service";

interface Props {
  parentId?: string;
  parentType?: string;
  onSelectImport?: (importId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: "bg-green-100 text-green-800",
  PENDING: "bg-yellow-100 text-yellow-800",
  PROCESSING: "bg-blue-100 text-blue-800",
  FAILED: "bg-red-100 text-red-800",
  PARTIAL: "bg-orange-100 text-orange-800",
};

export default function BulkImportList({
  parentId,
  parentType,
  onSelectImport,
}: Props) {
  const [imports, setImports] = useState<BulkImportListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadImports = async () => {
    try {
      setLoading(true);
      const data = await fetchImports(parentId, parentType);
      setImports(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadImports();
  }, [parentId, parentType]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this import?")) return;
    await deleteImport(id);
    loadImports();
  };

  if (loading) return <div className="p-4">Loading...</div>;

  if (!imports.length) {
    return (
      <div className="p-4 text-gray-500">
        No imports yet. Upload a document to get started.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-white">
      <h3 className="px-4 py-3 font-semibold border-b">Import History</h3>
      <ul className="divide-y">
        {imports.map((item) => (
          <li
            key={item.id}
            className="p-4 hover:bg-gray-50 cursor-pointer"
            onClick={() => onSelectImport?.(item.id)}
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium">{item.sourceFileName}</p>
                <p className="text-sm text-gray-500">
                  {item.sourceFileType} | {item.totalRows} rows |{" "}
                  {new Date(item.importedAt).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-1 text-xs rounded-full ${
                    STATUS_COLORS[item.status] || "bg-gray-100"
                  }`}
                >
                  {item.status}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(item.id);
                  }}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Page Integration Example

### React/Next.js

```tsx
// app/bulk-import/page.tsx
"use client";

import React, { useState } from "react";
import BulkImportUpload from "@/components/BulkImportUpload";
import BulkImportList from "@/components/BulkImportList";
import BulkImportDataTable from "@/components/BulkImportDataTable";

export default function BulkImportPage() {
  const [selectedImportId, setSelectedImportId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Optional: If linking to a specific parent entity
  const parentId = undefined; // or from route params
  const parentType = undefined;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Bulk Data Import</h1>

      {/* Upload Section */}
      <BulkImportUpload
        parentId={parentId}
        parentType={parentType}
        onUploadSuccess={() => setRefreshKey((k) => k + 1)}
      />

      {/* Import History */}
      <BulkImportList
        key={refreshKey}
        parentId={parentId}
        parentType={parentType}
        onSelectImport={setSelectedImportId}
      />

      {/* Data Table */}
      {selectedImportId && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Imported Data</h2>
          <BulkImportDataTable importId={selectedImportId} />
        </div>
      )}
    </div>
  );
}
```

### Vue 3

```vue
<!-- pages/BulkImportPage.vue -->
<template>
  <div class="p-6 max-w-6xl mx-auto space-y-6">
    <h1 class="text-2xl font-bold">Bulk Data Import</h1>

    <BulkImportUpload
      :parent-id="parentId"
      :parent-type="parentType"
      @success="refreshList"
    />

    <BulkImportList
      :key="refreshKey"
      :parent-id="parentId"
      :parent-type="parentType"
      @select="selectedImportId = $event"
    />

    <div v-if="selectedImportId">
      <h2 class="text-xl font-semibold mb-4">Imported Data</h2>
      <BulkImportDataTable :import-id="selectedImportId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import BulkImportUpload from '@/components/BulkImportUpload.vue';
import BulkImportList from '@/components/BulkImportList.vue';
import BulkImportDataTable from '@/components/BulkImportDataTable.vue';

const parentId = ref<string | undefined>(undefined);
const parentType = ref<string | undefined>(undefined);
const selectedImportId = ref<string | null>(null);
const refreshKey = ref(0);

const refreshList = () => {
  refreshKey.value++;
};
</script>
```

---

## Styling Notes

The examples use Tailwind CSS classes. Adapt to your styling approach:

- **Tailwind CSS**: Use classes as shown
- **CSS Modules**: Replace with `.module.css` imports
- **Styled Components**: Convert to styled components
- **Material-UI/Chakra**: Use corresponding component libraries

Key UI patterns to preserve:
- Drag-and-drop file upload zone
- Loading states with spinners
- Status badges with colors
- Paginated data tables
- Confirmation dialogs for destructive actions
