import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Customer, Invoice, Supplier


class InvoiceRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def get(self, invoice_id: uuid.UUID) -> Invoice | None:
        return self.session.scalar(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == self.company_id)
        )

    def list(self, *, search: str | None, offset: int, limit: int) -> tuple[list[Invoice], int]:
        filters = [Invoice.company_id == self.company_id]
        if search:
            pattern = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(Invoice.invoice_number).like(pattern),
                    Invoice.customer_id.in_(
                        select(Customer.id).where(
                            Customer.company_id == self.company_id,
                            func.lower(Customer.name).like(pattern),
                        )
                    ),
                    Invoice.supplier_id.in_(
                        select(Supplier.id).where(
                            Supplier.company_id == self.company_id,
                            func.lower(Supplier.name).like(pattern),
                        )
                    ),
                )
            )
        total = self.session.scalar(select(func.count(Invoice.id)).where(*filters)) or 0
        items = list(
            self.session.scalars(
                select(Invoice)
                .where(*filters)
                .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return items, total
