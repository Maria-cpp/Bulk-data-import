"""Initial bulk import tables

Revision ID: 001_initial
Revises:
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create import_status enum
    import_status = postgresql.ENUM(
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED',
        name='import_status',
        create_type=False
    )
    import_status.create(op.get_bind(), checkfirst=True)

    # Create file_type enum
    file_type = postgresql.ENUM(
        'PDF', 'EXCEL', 'WORD', 'IMAGE', 'CSV',
        name='file_type',
        create_type=False
    )
    file_type.create(op.get_bind(), checkfirst=True)

    # Create bulk_imports table
    op.create_table(
        'bulk_imports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('status', import_status, nullable=False, server_default='PENDING'),
        sa.Column('source_file_name', sa.String(255), nullable=False),
        sa.Column('source_file_type', file_type, nullable=False),
        sa.Column('source_file_size', sa.Integer, nullable=False),
        sa.Column('source_file_hash', sa.String(64), nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_details', postgresql.JSONB, nullable=True),
        sa.Column('processing_started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create indexes for bulk_imports
    op.create_index(
        'idx_bulk_import_user_status',
        'bulk_imports',
        ['user_id', 'status', 'deleted_at']
    )
    op.create_index(
        'idx_bulk_import_hash',
        'bulk_imports',
        ['user_id', 'source_file_hash']
    )
    op.create_index(
        'idx_bulk_import_stuck',
        'bulk_imports',
        ['status', 'processing_started_at'],
        postgresql_where="status = 'PROCESSING'"
    )

    # Create extracted_tables table
    op.create_table(
        'extracted_tables',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bulk_import_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('bulk_imports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('table_index', sa.Integer, nullable=False),
        sa.Column('source_location', sa.String(100), nullable=True),
        sa.Column('column_headers', postgresql.JSONB, nullable=False),
        sa.Column('row_data', postgresql.JSONB, nullable=False),
        sa.Column('row_count', sa.Integer, nullable=False),
        sa.Column('column_count', sa.Integer, nullable=False),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('extraction_warnings', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # Create index for extracted_tables
    op.create_index(
        'idx_extracted_table_import',
        'extracted_tables',
        ['bulk_import_id']
    )


def downgrade() -> None:
    op.drop_table('extracted_tables')
    op.drop_table('bulk_imports')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS import_status')
    op.execute('DROP TYPE IF EXISTS file_type')
