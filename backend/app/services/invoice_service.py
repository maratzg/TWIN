import math
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Invoice, Supplier
from app.repositories.invoices import InvoiceRepository


class InvoiceService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id
        self.repository = InvoiceRepository(session, company_id)

    def history(self, *, search: str | None, page: int, page_size: int) -> dict:
        invoices, total = self.repository.list(
            search=search,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._response(invoice) for invoice in invoices],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def detail(self, invoice_id: uuid.UUID) -> dict:
        invoice = self.repository.get(invoice_id)
        if invoice is None:
            raise LookupError("Invoice not found.")
        return self._response(invoice)

    def _response(self, invoice: Invoice) -> dict:
        customer_name = self.session.scalar(
            select(Customer.name).where(
                Customer.id == invoice.customer_id,
                Customer.company_id == self.company_id,
            )
        ) if invoice.customer_id else None
        supplier_name = self.session.scalar(
            select(Supplier.name).where(
                Supplier.id == invoice.supplier_id,
                Supplier.company_id == self.company_id,
            )
        ) if invoice.supplier_id else None
        return {
            "id": invoice.id,
            "source_document_id": invoice.source_document_id,
            "invoice_number": invoice.invoice_number,
            "direction": invoice.direction,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "subtotal": invoice.subtotal,
            "vat": invoice.vat,
            "total": invoice.total,
            "currency": invoice.currency,
            "status": invoice.status,
            "customer_id": invoice.customer_id,
            "customer_name": customer_name,
            "supplier_id": invoice.supplier_id,
            "supplier_name": supplier_name,
            "shipment_id": invoice.shipment_id,
            "created_at": invoice.created_at,
        }

