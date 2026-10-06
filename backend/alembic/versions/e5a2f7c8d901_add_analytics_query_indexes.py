"""add analytics query indexes

Revision ID: e5a2f7c8d901
Revises: d4c9b81f3a27
Create Date: 2026-09-24 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e5a2f7c8d901"
down_revision: Union[str, Sequence[str], None] = "d4c9b81f3a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_shipments_company_etd", "shipments", ["company_id", "etd"], unique=False)
    op.create_index(
        "ix_shipments_company_customer_etd",
        "shipments",
        ["company_id", "customer_id", "etd"],
        unique=False,
    )
    op.create_index(
        "ix_shipments_company_route_etd",
        "shipments",
        ["company_id", "origin_port_id", "destination_port_id", "etd"],
        unique=False,
    )
    op.create_index(
        "ix_shipments_company_voyage_etd",
        "shipments",
        ["company_id", "voyage_id", "etd"],
        unique=False,
    )
    op.create_index(
        "ix_invoices_company_direction_currency_date",
        "invoices",
        ["company_id", "direction", "currency", "invoice_date"],
        unique=False,
    )
    op.create_index(
        "ix_invoices_company_customer_date",
        "invoices",
        ["company_id", "customer_id", "invoice_date"],
        unique=False,
    )
    op.create_index(
        "ix_invoices_company_due_date",
        "invoices",
        ["company_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_payments_company_invoice_date",
        "payments",
        ["company_id", "invoice_id", "payment_date"],
        unique=False,
    )
    op.create_index(
        "ix_costs_company_shipment_currency",
        "costs",
        ["company_id", "shipment_id", "currency"],
        unique=False,
    )
    op.create_index(
        "ix_costs_company_date",
        "costs",
        ["company_id", "cost_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_costs_company_date", table_name="costs")
    op.drop_index("ix_costs_company_shipment_currency", table_name="costs")
    op.drop_index("ix_payments_company_invoice_date", table_name="payments")
    op.drop_index("ix_invoices_company_due_date", table_name="invoices")
    op.drop_index("ix_invoices_company_customer_date", table_name="invoices")
    op.drop_index("ix_invoices_company_direction_currency_date", table_name="invoices")
    op.drop_index("ix_shipments_company_voyage_etd", table_name="shipments")
    op.drop_index("ix_shipments_company_route_etd", table_name="shipments")
    op.drop_index("ix_shipments_company_customer_etd", table_name="shipments")
    op.drop_index("ix_shipments_company_etd", table_name="shipments")
