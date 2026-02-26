"""Pytest configuration and shared fixtures."""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.models import Base
from app.api.deps import get_db, get_current_user
from app.config import get_settings, Settings


# Test database URL (use SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    def override_get_current_user():
        return {"user_id": str(uuid4())}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def test_user_id() -> str:
    """Generate a test user ID."""
    return str(uuid4())


@pytest.fixture
def fixtures_path() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_excel_path(fixtures_path: Path) -> Path:
    """Path to sample Excel file."""
    return fixtures_path / "sample_data.xlsx"


@pytest.fixture
def sample_csv_path(fixtures_path: Path) -> Path:
    """Path to sample CSV file."""
    return fixtures_path / "sample_data.csv"


@pytest.fixture
def sample_pdf_single_table(fixtures_path: Path) -> Path:
    """Path to single table PDF."""
    return fixtures_path / "single_table.pdf"


@pytest.fixture
def sample_pdf_multi_table(fixtures_path: Path) -> Path:
    """Path to multi table PDF."""
    return fixtures_path / "multi_table.pdf"


@pytest.fixture
def sample_image_clear(fixtures_path: Path) -> Path:
    """Path to clear table image."""
    return fixtures_path / "clear_table.png"


@pytest.fixture
def sample_image_low_quality(fixtures_path: Path) -> Path:
    """Path to low quality table image."""
    return fixtures_path / "low_quality.jpg"


@pytest.fixture
def sample_docx_tables_only(fixtures_path: Path) -> Path:
    """Path to Word doc with tables only."""
    return fixtures_path / "tables_only.docx"


@pytest.fixture
def sample_docx_mixed(fixtures_path: Path) -> Path:
    """Path to Word doc with mixed content."""
    return fixtures_path / "mixed_content.docx"
