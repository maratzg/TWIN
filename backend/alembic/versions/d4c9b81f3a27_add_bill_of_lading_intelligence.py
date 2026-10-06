"""add bill of lading intelligence

Revision ID: d4c9b81f3a27
Revises: 8a71d0c4e9b2
Create Date: 2026-09-24 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4c9b81f3a27"
down_revision: Union[str, Sequence[str], None] = "8a71d0c4e9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("document_field_candidates") as batch_op:
        batch_op.add_column(
            sa.Column("group_type", sa.String(length=50), server_default="document", nullable=False)
        )
        batch_op.add_column(
            sa.Column("group_index", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.drop_constraint("uq_document_field_candidates_document_id", type_="unique")
        batch_op.create_unique_constraint(
            "uq_doc_candidates_group_field",
            ["document_id", "group_type", "group_index", "field_name"],
        )
        batch_op.create_index(
            op.f("ix_document_field_candidates_group_type"), ["group_type"], unique=False
        )

    with op.batch_alter_table("bills_of_lading") as batch_op:
        batch_op.add_column(sa.Column("source_document_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("shipper_supplier_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("consignee_customer_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("description_of_goods", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("total_packages", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("total_gross_weight", sa.Numeric(18, 3), nullable=True))
        batch_op.add_column(sa.Column("measurement", sa.Numeric(18, 3), nullable=True))
        batch_op.add_column(sa.Column("measurement_unit", sa.String(length=20), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_bills_of_lading_source_document_id_documents"),
            "documents", ["source_document_id"], ["id"],
        )
        batch_op.create_foreign_key(
            op.f("fk_bills_of_lading_shipper_supplier_id_suppliers"),
            "suppliers", ["shipper_supplier_id"], ["id"],
        )
        batch_op.create_foreign_key(
            op.f("fk_bills_of_lading_consignee_customer_id_customers"),
            "customers", ["consignee_customer_id"], ["id"],
        )
        batch_op.create_index(op.f("ix_bills_of_lading_source_document_id"), ["source_document_id"], unique=True)
        batch_op.create_index(op.f("ix_bills_of_lading_shipper_supplier_id"), ["shipper_supplier_id"], unique=False)
        batch_op.create_index(op.f("ix_bills_of_lading_consignee_customer_id"), ["consignee_customer_id"], unique=False)

    with op.batch_alter_table("containers") as batch_op:
        batch_op.add_column(sa.Column("source_document_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("source_candidate_group", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("seal_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("package_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("package_type", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_containers_source_document_id_documents"),
            "documents", ["source_document_id"], ["id"],
        )
        batch_op.create_index(op.f("ix_containers_source_document_id"), ["source_document_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("containers") as batch_op:
        batch_op.drop_index(op.f("ix_containers_source_document_id"))
        batch_op.drop_constraint(op.f("fk_containers_source_document_id_documents"), type_="foreignkey")
        batch_op.drop_column("package_type")
        batch_op.drop_column("package_count")
        batch_op.drop_column("seal_number")
        batch_op.drop_column("source_candidate_group")
        batch_op.drop_column("source_document_id")

    with op.batch_alter_table("bills_of_lading") as batch_op:
        batch_op.drop_index(op.f("ix_bills_of_lading_consignee_customer_id"))
        batch_op.drop_index(op.f("ix_bills_of_lading_shipper_supplier_id"))
        batch_op.drop_index(op.f("ix_bills_of_lading_source_document_id"))
        batch_op.drop_constraint(op.f("fk_bills_of_lading_consignee_customer_id_customers"), type_="foreignkey")
        batch_op.drop_constraint(op.f("fk_bills_of_lading_shipper_supplier_id_suppliers"), type_="foreignkey")
        batch_op.drop_constraint(op.f("fk_bills_of_lading_source_document_id_documents"), type_="foreignkey")
        batch_op.drop_column("measurement_unit")
        batch_op.drop_column("measurement")
        batch_op.drop_column("total_gross_weight")
        batch_op.drop_column("total_packages")
        batch_op.drop_column("description_of_goods")
        batch_op.drop_column("consignee_customer_id")
        batch_op.drop_column("shipper_supplier_id")
        batch_op.drop_column("source_document_id")

    with op.batch_alter_table("document_field_candidates") as batch_op:
        batch_op.drop_index(op.f("ix_document_field_candidates_group_type"))
        batch_op.drop_constraint("uq_doc_candidates_group_field", type_="unique")
        batch_op.create_unique_constraint(
            "uq_document_field_candidates_document_id", ["document_id", "field_name"]
        )
        batch_op.drop_column("group_index")
        batch_op.drop_column("group_type")
