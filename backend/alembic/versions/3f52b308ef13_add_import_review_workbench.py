"""add import review workbench

Revision ID: 3f52b308ef13
Revises: c33c81015de5
Create Date: 2026-09-23 21:24:05.144666
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3f52b308ef13'
down_revision: Union[str, Sequence[str], None] = 'c33c81015de5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('import_corrections',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('import_job_id', sa.Uuid(), nullable=False),
    sa.Column('import_row_id', sa.Uuid(), nullable=True),
    sa.Column('correction_type', sa.String(length=30), nullable=False),
    sa.Column('source_column', sa.String(length=300), nullable=True),
    sa.Column('canonical_field', sa.String(length=100), nullable=True),
    sa.Column('previous_value', sa.JSON(), nullable=True),
    sa.Column('corrected_value', sa.JSON(), nullable=True),
    sa.Column('unit', sa.String(length=30), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('reviewer_reference', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_import_corrections_company_id_companies')),
    sa.ForeignKeyConstraint(['import_job_id'], ['import_jobs.id'], name=op.f('fk_import_corrections_import_job_id_import_jobs')),
    sa.ForeignKeyConstraint(['import_row_id'], ['import_rows.id'], name=op.f('fk_import_corrections_import_row_id_import_rows')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_corrections'))
    )
    op.create_index(op.f('ix_import_corrections_company_id'), 'import_corrections', ['company_id'], unique=False)
    op.create_index(op.f('ix_import_corrections_correction_type'), 'import_corrections', ['correction_type'], unique=False)
    op.create_index(op.f('ix_import_corrections_import_job_id'), 'import_corrections', ['import_job_id'], unique=False)
    op.create_index(op.f('ix_import_corrections_import_row_id'), 'import_corrections', ['import_row_id'], unique=False)
    op.add_column(
        'import_jobs',
        sa.Column('ready_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    with op.batch_alter_table('import_rows') as batch_op:
        batch_op.add_column(sa.Column('system_normalized_data', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_by', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('committed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('canonical_record_id', sa.Uuid(), nullable=True))
        batch_op.create_index(
            op.f('ix_import_rows_canonical_record_id'),
            ['canonical_record_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            op.f('fk_import_rows_canonical_record_id_shipments'),
            'shipments',
            ['canonical_record_id'],
            ['id'],
        )
    with op.batch_alter_table('shipments') as batch_op:
        batch_op.add_column(sa.Column('booking_reference', sa.String(length=200), nullable=True))
        batch_op.create_index(
            op.f('ix_shipments_booking_reference'),
            ['booking_reference'],
            unique=False,
        )
        batch_op.create_unique_constraint(
            'uq_shipments_company_booking_reference',
            ['company_id', 'booking_reference'],
        )

    # Preserve Milestone 1 normalized candidates and convert its terminal ready rows
    # into explicit row-level committed state.
    op.execute(
        "UPDATE import_rows SET system_normalized_data = normalized_data "
        "WHERE normalized_data IS NOT NULL"
    )
    op.execute(
        "UPDATE import_rows SET canonical_record_id = ("
        "SELECT shipments.id FROM shipments "
        "WHERE shipments.import_job_id = import_rows.import_job_id "
        "AND shipments.source_row_number = import_rows.row_number LIMIT 1"
        "), committed_at = ("
        "SELECT import_jobs.committed_at FROM import_jobs "
        "WHERE import_jobs.id = import_rows.import_job_id"
        "), disposition = 'committed' "
        "WHERE disposition = 'ready' AND import_job_id IN ("
        "SELECT id FROM import_jobs WHERE status = 'committed'"
        ")"
    )
    op.execute(
        "UPDATE import_jobs SET ready_count = ("
        "SELECT COUNT(*) FROM import_rows "
        "WHERE import_rows.import_job_id = import_jobs.id "
        "AND import_rows.disposition = 'ready'"
        ")"
    )
    op.execute(
        "UPDATE import_jobs SET status = 'needs_review' "
        "WHERE status = 'validated' AND (review_count > 0 OR rejected_count > 0)"
    )
    op.execute(
        "UPDATE import_jobs SET status = 'partially_committed' "
        "WHERE status = 'committed' AND imported_count < detected_row_count"
    )


def downgrade() -> None:
    op.execute("UPDATE import_jobs SET status = 'validated' WHERE status = 'needs_review'")
    op.execute("UPDATE import_jobs SET status = 'committed' WHERE status = 'partially_committed'")
    op.execute("UPDATE import_rows SET disposition = 'ready' WHERE disposition = 'committed'")
    with op.batch_alter_table('shipments') as batch_op:
        batch_op.drop_constraint('uq_shipments_company_booking_reference', type_='unique')
        batch_op.drop_index(op.f('ix_shipments_booking_reference'))
        batch_op.drop_column('booking_reference')
    with op.batch_alter_table('import_rows') as batch_op:
        batch_op.drop_constraint(
            op.f('fk_import_rows_canonical_record_id_shipments'),
            type_='foreignkey',
        )
        batch_op.drop_index(op.f('ix_import_rows_canonical_record_id'))
        batch_op.drop_column('canonical_record_id')
        batch_op.drop_column('committed_at')
        batch_op.drop_column('approved_by')
        batch_op.drop_column('approved_at')
        batch_op.drop_column('last_validated_at')
        batch_op.drop_column('system_normalized_data')
    op.drop_column('import_jobs', 'ready_count')
    op.drop_index(op.f('ix_import_corrections_import_row_id'), table_name='import_corrections')
    op.drop_index(op.f('ix_import_corrections_import_job_id'), table_name='import_corrections')
    op.drop_index(op.f('ix_import_corrections_correction_type'), table_name='import_corrections')
    op.drop_index(op.f('ix_import_corrections_company_id'), table_name='import_corrections')
    op.drop_table('import_corrections')
