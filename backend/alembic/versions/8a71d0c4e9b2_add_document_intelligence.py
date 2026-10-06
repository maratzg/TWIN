"""add document intelligence

Revision ID: 8a71d0c4e9b2
Revises: 3f52b308ef13
Create Date: 2026-09-24 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a71d0c4e9b2"
down_revision: Union[str, Sequence[str], None] = "3f52b308ef13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(sa.Column("registration_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("vat_number", sa.String(length=100), nullable=True))

    op.create_table(
        "documents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=False),
        sa.Column("classification_method", sa.String(length=80), nullable=True),
        sa.Column("classification_signals", sa.JSON(), nullable=False),
        sa.Column("extraction_version", sa.String(length=80), nullable=True),
        sa.Column("extraction_method", sa.String(length=50), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("field_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_documents_company_id_companies")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
    )
    op.create_index(op.f("ix_documents_checksum_sha256"), "documents", ["checksum_sha256"], unique=False)
    op.create_index(op.f("ix_documents_company_id"), "documents", ["company_id"], unique=False)
    op.create_index(op.f("ix_documents_document_type"), "documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    op.create_table(
        "document_pages",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("blocks", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(length=50), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_pages_document_id_documents")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_pages")),
        sa.UniqueConstraint("document_id", "page_number", name=op.f("uq_document_pages_document_id")),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False)

    op.create_table(
        "document_field_candidates",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("system_normalized_value", sa.JSON(), nullable=True),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("matched_entity_type", sa.String(length=50), nullable=True),
        sa.Column("matched_entity_id", sa.Uuid(), nullable=True),
        sa.Column("match_method", sa.String(length=50), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_field_candidates_document_id_documents")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_field_candidates")),
        sa.UniqueConstraint("document_id", "field_name", name=op.f("uq_document_field_candidates_document_id")),
    )
    op.create_index(op.f("ix_document_field_candidates_document_id"), "document_field_candidates", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_field_candidates_field_name"), "document_field_candidates", ["field_name"], unique=False)
    op.create_index(op.f("ix_document_field_candidates_matched_entity_id"), "document_field_candidates", ["matched_entity_id"], unique=False)
    op.create_index(op.f("ix_document_field_candidates_status"), "document_field_candidates", ["status"], unique=False)

    op.create_table(
        "document_issues",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("field", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_issues_document_id_documents")),
        sa.ForeignKeyConstraint(["field_candidate_id"], ["document_field_candidates.id"], name=op.f("fk_document_issues_field_candidate_id_document_field_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_issues")),
    )
    op.create_index(op.f("ix_document_issues_code"), "document_issues", ["code"], unique=False)
    op.create_index(op.f("ix_document_issues_document_id"), "document_issues", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_issues_field_candidate_id"), "document_issues", ["field_candidate_id"], unique=False)
    op.create_index(op.f("ix_document_issues_severity"), "document_issues", ["severity"], unique=False)

    op.create_table(
        "document_corrections",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_reference", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_document_corrections_company_id_companies")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_corrections_document_id_documents")),
        sa.ForeignKeyConstraint(["field_candidate_id"], ["document_field_candidates.id"], name=op.f("fk_document_corrections_field_candidate_id_document_field_candidates")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_corrections")),
    )
    op.create_index(op.f("ix_document_corrections_company_id"), "document_corrections", ["company_id"], unique=False)
    op.create_index(op.f("ix_document_corrections_document_id"), "document_corrections", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_corrections_field_candidate_id"), "document_corrections", ["field_candidate_id"], unique=False)

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("source_document_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_invoices_source_document_id_documents"),
            "documents",
            ["source_document_id"],
            ["id"],
        )
        batch_op.create_index(op.f("ix_invoices_source_document_id"), ["source_document_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_index(op.f("ix_invoices_source_document_id"))
        batch_op.drop_constraint(op.f("fk_invoices_source_document_id_documents"), type_="foreignkey")
        batch_op.drop_column("source_document_id")
    op.drop_index(op.f("ix_document_corrections_field_candidate_id"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_document_id"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_company_id"), table_name="document_corrections")
    op.drop_table("document_corrections")
    op.drop_index(op.f("ix_document_issues_severity"), table_name="document_issues")
    op.drop_index(op.f("ix_document_issues_field_candidate_id"), table_name="document_issues")
    op.drop_index(op.f("ix_document_issues_document_id"), table_name="document_issues")
    op.drop_index(op.f("ix_document_issues_code"), table_name="document_issues")
    op.drop_table("document_issues")
    op.drop_index(op.f("ix_document_field_candidates_status"), table_name="document_field_candidates")
    op.drop_index(op.f("ix_document_field_candidates_matched_entity_id"), table_name="document_field_candidates")
    op.drop_index(op.f("ix_document_field_candidates_field_name"), table_name="document_field_candidates")
    op.drop_index(op.f("ix_document_field_candidates_document_id"), table_name="document_field_candidates")
    op.drop_table("document_field_candidates")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_document_type"), table_name="documents")
    op.drop_index(op.f("ix_documents_company_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_checksum_sha256"), table_name="documents")
    op.drop_table("documents")
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_column("vat_number")
        batch_op.drop_column("registration_number")

