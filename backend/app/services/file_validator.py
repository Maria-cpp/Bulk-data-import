"""File validation utilities for upload security."""

import hashlib
import re
from pathlib import Path

from app.config import get_settings
from app.schemas.bulk_import import FileType

settings = get_settings()

# Magic byte signatures for supported file types
MAGIC_SIGNATURES = {
    # PDF
    b"%PDF": FileType.PDF,
    # Excel (ZIP-based OOXML)
    b"PK\x03\x04": FileType.EXCEL,  # Also matches DOCX, need content check
    # Legacy Excel (OLE)
    b"\xd0\xcf\x11\xe0": FileType.EXCEL,  # Also matches legacy DOC
    # PNG
    b"\x89PNG\r\n\x1a\n": FileType.IMAGE,
    # JPEG
    b"\xff\xd8\xff": FileType.IMAGE,
}

# MIME types for each file type
MIME_TYPE_MAP = {
    "application/pdf": FileType.PDF,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.EXCEL,
    "application/vnd.ms-excel": FileType.EXCEL,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.WORD,
    "application/msword": FileType.WORD,
    "image/png": FileType.IMAGE,
    "image/jpeg": FileType.IMAGE,
    "text/csv": FileType.CSV,
    "text/plain": FileType.CSV,  # CSV often detected as text/plain
}

# File extensions for each type
EXTENSION_MAP = {
    ".pdf": FileType.PDF,
    ".xlsx": FileType.EXCEL,
    ".xls": FileType.EXCEL,
    ".docx": FileType.WORD,
    ".doc": FileType.WORD,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".csv": FileType.CSV,
}


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, error_code: str, message: str, details: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validate_file_size(file_size: int) -> None:
    """Validate file size is within limit."""
    if file_size > settings.BULK_IMPORT_MAX_FILE_SIZE:
        raise FileValidationError(
            error_code="FILE_TOO_LARGE",
            message="File size exceeds limit",
            details={
                "max_size_bytes": settings.BULK_IMPORT_MAX_FILE_SIZE,
                "received_size_bytes": file_size,
            },
        )


def detect_file_type_from_magic(file_bytes: bytes) -> FileType | None:
    """Detect file type from magic bytes."""
    for signature, file_type in MAGIC_SIGNATURES.items():
        if file_bytes.startswith(signature):
            return file_type
    return None


def detect_file_type_from_content(file_bytes: bytes, filename: str) -> FileType:
    """Detect file type from content and filename."""
    # Try magic byte detection first
    magic_type = detect_file_type_from_magic(file_bytes)

    # Get extension
    ext = Path(filename).suffix.lower()
    ext_type = EXTENSION_MAP.get(ext)

    # For ZIP-based formats (XLSX, DOCX), we need to check content
    if magic_type == FileType.EXCEL and file_bytes.startswith(b"PK\x03\x04"):
        # Check if it's actually a Word document
        if ext in [".docx", ".doc"]:
            return FileType.WORD
        if ext in [".xlsx", ".xls"]:
            return FileType.EXCEL

    # CSV detection - if no magic signature, check extension
    if magic_type is None and ext == ".csv":
        return FileType.CSV

    # Use magic type if detected
    if magic_type is not None:
        return magic_type

    # Fall back to extension
    if ext_type is not None:
        return ext_type

    raise FileValidationError(
        error_code="INVALID_FILE_TYPE",
        message="File type not supported",
        details={
            "allowed_types": list(EXTENSION_MAP.keys()),
            "received_extension": ext,
        },
    )


def validate_file_type(file_bytes: bytes, filename: str, claimed_mime_type: str | None = None) -> FileType:
    """Validate file type by content inspection."""
    file_type = detect_file_type_from_content(file_bytes, filename)

    # If MIME type was claimed, verify it matches
    if claimed_mime_type and claimed_mime_type in MIME_TYPE_MAP:
        claimed_type = MIME_TYPE_MAP[claimed_mime_type]
        # Allow some flexibility for related types
        if claimed_type != file_type:
            # Special case: text/plain and CSV
            if not (claimed_mime_type == "text/plain" and file_type == FileType.CSV):
                raise FileValidationError(
                    error_code="FILE_TYPE_MISMATCH",
                    message="File content does not match claimed type",
                    details={
                        "claimed_type": claimed_mime_type,
                        "detected_type": file_type.value,
                    },
                )

    return file_type


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    # Get just the filename without any path components
    name = Path(filename).name

    # Remove any path traversal attempts
    name = name.replace("..", "")
    name = name.replace("/", "")
    name = name.replace("\\", "")

    # Remove any control characters
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Limit length
    if len(name) > 255:
        ext = Path(name).suffix
        name = name[: 255 - len(ext)] + ext

    # Ensure we have a valid filename
    if not name or name.startswith("."):
        name = "unnamed_file" + Path(filename).suffix

    return name


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(file_bytes).hexdigest()
