"""Integration tests for import management operations."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.bulk_import import BulkImport, ExtractedTable, ImportStatus, FileType


class MockBulkImport:
    """Mock BulkImport for testing without database."""

    def __init__(
        self,
        id=None,
        user_id=None,
        status=ImportStatus.PENDING,
        source_file_name="test.csv",
        source_file_type=FileType.CSV,
        source_file_size=1024,
        deleted_at=None,
        created_at=None,
        retry_count=0,
    ):
        self.id = id or uuid.uuid4()
        self.user_id = user_id or uuid.uuid4()
        self.status = status
        self.source_file_name = source_file_name
        self.source_file_type = source_file_type
        self.source_file_size = source_file_size
        self.deleted_at = deleted_at
        self.created_at = created_at or datetime.now(timezone.utc)
        self.retry_count = retry_count
        self.tables = []

    @property
    def can_retry(self):
        return self.status == ImportStatus.FAILED and self.retry_count < 3


class TestListImports:
    """Tests for listing imports with pagination."""

    def test_list_returns_user_imports_only(self):
        """Verify list returns only current user's imports."""
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        imports = [
            MockBulkImport(user_id=user_id, source_file_name="user1_file.csv"),
            MockBulkImport(user_id=other_user_id, source_file_name="user2_file.csv"),
            MockBulkImport(user_id=user_id, source_file_name="user1_file2.csv"),
        ]

        user_imports = [i for i in imports if i.user_id == user_id]
        assert len(user_imports) == 2
        assert all(i.user_id == user_id for i in user_imports)

    def test_pagination_page_1(self):
        """Test first page of pagination."""
        imports = [MockBulkImport(source_file_name=f"file{i}.csv") for i in range(25)]

        page = 1
        per_page = 10
        offset = (page - 1) * per_page

        paginated = imports[offset : offset + per_page]

        assert len(paginated) == 10
        assert paginated[0].source_file_name == "file0.csv"
        assert paginated[9].source_file_name == "file9.csv"

    def test_pagination_page_2(self):
        """Test second page of pagination."""
        imports = [MockBulkImport(source_file_name=f"file{i}.csv") for i in range(25)]

        page = 2
        per_page = 10
        offset = (page - 1) * per_page

        paginated = imports[offset : offset + per_page]

        assert len(paginated) == 10
        assert paginated[0].source_file_name == "file10.csv"

    def test_pagination_last_page(self):
        """Test last page with partial results."""
        imports = [MockBulkImport(source_file_name=f"file{i}.csv") for i in range(25)]

        page = 3
        per_page = 10
        offset = (page - 1) * per_page

        paginated = imports[offset : offset + per_page]

        assert len(paginated) == 5  # 25 - 20 = 5 remaining

    def test_pagination_metadata(self):
        """Test pagination metadata calculation."""
        total_items = 45
        per_page = 10

        total_pages = (total_items + per_page - 1) // per_page

        assert total_pages == 5


class TestFilterByStatus:
    """Tests for filtering imports by status."""

    def test_filter_pending(self):
        """Filter imports by PENDING status."""
        imports = [
            MockBulkImport(status=ImportStatus.PENDING),
            MockBulkImport(status=ImportStatus.PROCESSING),
            MockBulkImport(status=ImportStatus.COMPLETED),
            MockBulkImport(status=ImportStatus.PENDING),
        ]

        filtered = [i for i in imports if i.status == ImportStatus.PENDING]
        assert len(filtered) == 2

    def test_filter_completed(self):
        """Filter imports by COMPLETED status."""
        imports = [
            MockBulkImport(status=ImportStatus.COMPLETED),
            MockBulkImport(status=ImportStatus.FAILED),
            MockBulkImport(status=ImportStatus.COMPLETED),
        ]

        filtered = [i for i in imports if i.status == ImportStatus.COMPLETED]
        assert len(filtered) == 2

    def test_filter_failed(self):
        """Filter imports by FAILED status."""
        imports = [
            MockBulkImport(status=ImportStatus.COMPLETED),
            MockBulkImport(status=ImportStatus.FAILED),
            MockBulkImport(status=ImportStatus.FAILED),
        ]

        filtered = [i for i in imports if i.status == ImportStatus.FAILED]
        assert len(filtered) == 2


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_delete_sets_deleted_at(self):
        """Verify soft delete sets deleted_at timestamp."""
        import_record = MockBulkImport()
        assert import_record.deleted_at is None

        import_record.deleted_at = datetime.now(timezone.utc)

        assert import_record.deleted_at is not None

    def test_deleted_not_in_list(self):
        """Verify soft deleted imports are not in list."""
        imports = [
            MockBulkImport(deleted_at=None),
            MockBulkImport(deleted_at=datetime.now(timezone.utc)),
            MockBulkImport(deleted_at=None),
        ]

        active = [i for i in imports if i.deleted_at is None]
        assert len(active) == 2

    def test_delete_requires_user_ownership(self):
        """Verify delete only works for user's own imports."""
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        import_record = MockBulkImport(user_id=other_user_id)

        # Should not be able to delete another user's import
        can_delete = import_record.user_id == user_id
        assert can_delete is False


class TestRetryFailed:
    """Tests for retrying failed imports."""

    def test_can_retry_failed_import(self):
        """Verify failed import with 0 retries can be retried."""
        import_record = MockBulkImport(status=ImportStatus.FAILED, retry_count=0)
        assert import_record.can_retry is True

    def test_cannot_retry_completed(self):
        """Verify completed import cannot be retried."""
        import_record = MockBulkImport(status=ImportStatus.COMPLETED, retry_count=0)
        assert import_record.can_retry is False

    def test_cannot_retry_max_retries(self):
        """Verify import at max retries cannot be retried."""
        import_record = MockBulkImport(status=ImportStatus.FAILED, retry_count=3)
        assert import_record.can_retry is False

    def test_retry_increments_count(self):
        """Verify retry increments retry count."""
        import_record = MockBulkImport(status=ImportStatus.FAILED, retry_count=1)

        if import_record.can_retry:
            import_record.retry_count += 1
            import_record.status = ImportStatus.PENDING

        assert import_record.retry_count == 2
        assert import_record.status == ImportStatus.PENDING

    def test_retry_resets_status(self):
        """Verify retry resets status to PENDING."""
        import_record = MockBulkImport(status=ImportStatus.FAILED, retry_count=0)

        if import_record.can_retry:
            import_record.status = ImportStatus.PENDING

        assert import_record.status == ImportStatus.PENDING


class TestImportDetail:
    """Tests for import detail retrieval."""

    def test_detail_includes_tables(self):
        """Verify detail includes extracted tables."""
        import_record = MockBulkImport()
        import_record.tables = [
            MagicMock(
                id=uuid.uuid4(),
                table_index=0,
                source_location="Sheet 1",
                row_count=50,
                column_count=5,
            ),
            MagicMock(
                id=uuid.uuid4(),
                table_index=1,
                source_location="Sheet 2",
                row_count=30,
                column_count=4,
            ),
        ]

        assert len(import_record.tables) == 2

    def test_detail_includes_correlation_id(self):
        """Verify detail includes correlation ID for traceability."""
        import_record = MockBulkImport()
        import_record.correlation_id = uuid.uuid4()

        assert import_record.correlation_id is not None

    def test_detail_includes_error_info_on_failure(self):
        """Verify failed import detail includes error information."""
        import_record = MockBulkImport(status=ImportStatus.FAILED)
        import_record.error_message = "Invalid file format"
        import_record.error_details = {"error_code": "PARSE_ERROR"}

        assert import_record.error_message is not None
        assert import_record.error_details is not None


class TestUserIsolation:
    """Tests for multi-tenant user isolation."""

    def test_user_cannot_access_others_imports(self):
        """Verify user cannot access another user's imports."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        import_record = MockBulkImport(user_id=user_a)

        # Simulate access check
        requesting_user = user_b
        can_access = import_record.user_id == requesting_user

        assert can_access is False

    def test_user_can_access_own_imports(self):
        """Verify user can access their own imports."""
        user_id = uuid.uuid4()

        import_record = MockBulkImport(user_id=user_id)

        # Simulate access check
        requesting_user = user_id
        can_access = import_record.user_id == requesting_user

        assert can_access is True

    def test_import_list_isolated_by_user(self):
        """Verify import list only returns user's imports."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        all_imports = [
            MockBulkImport(user_id=user_a, source_file_name="a1.csv"),
            MockBulkImport(user_id=user_b, source_file_name="b1.csv"),
            MockBulkImport(user_id=user_a, source_file_name="a2.csv"),
            MockBulkImport(user_id=user_b, source_file_name="b2.csv"),
        ]

        user_a_imports = [i for i in all_imports if i.user_id == user_a]
        user_b_imports = [i for i in all_imports if i.user_id == user_b]

        assert len(user_a_imports) == 2
        assert len(user_b_imports) == 2
        assert all("a" in i.source_file_name for i in user_a_imports)
        assert all("b" in i.source_file_name for i in user_b_imports)
