from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BillOfLading, DocumentFieldCandidate, Invoice, SourceDocument


class DocumentRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def get(self, document_id: uuid.UUID) -> SourceDocument | None:
        return self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.id == document_id,
                SourceDocument.company_id == self.company_id,
            )
        )

    def list(
        self,
        *,
        search: str | None,
        status: str | None,
        document_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[SourceDocument], int]:
        filters = [SourceDocument.company_id == self.company_id]
        if search:
            filters.append(func.lower(SourceDocument.original_filename).contains(search.lower()))
        if status:
            filters.append(SourceDocument.status == status)
        if document_type:
            filters.append(SourceDocument.document_type == document_type)
        total = self.session.scalar(select(func.count(SourceDocument.id)).where(*filters)) or 0
        items = list(
            self.session.scalars(
                select(SourceDocument)
                .where(*filters)
                .order_by(SourceDocument.created_at.desc(), SourceDocument.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return items, total

    def candidate_status_counts(self, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        result: dict[uuid.UUID, dict[str, int]] = {document_id: {} for document_id in document_ids}
        if not document_ids:
            return result
        for document_id, status, count in self.session.execute(
            select(
                DocumentFieldCandidate.document_id,
                DocumentFieldCandidate.status,
                func.count(DocumentFieldCandidate.id),
            )
            .where(DocumentFieldCandidate.document_id.in_(document_ids))
            .group_by(DocumentFieldCandidate.document_id, DocumentFieldCandidate.status)
        ):
            result[document_id][status] = count
        return result

    def invoice_for_document(self, document_id: uuid.UUID) -> Invoice | None:
        return self.session.scalar(
            select(Invoice).where(
                Invoice.company_id == self.company_id,
                Invoice.source_document_id == document_id,
            )
        )

    def invoice_references(self, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, Invoice]:
        if not document_ids:
            return {}
        invoices = self.session.scalars(
            select(Invoice).where(
                Invoice.company_id == self.company_id,
                Invoice.source_document_id.in_(document_ids),
            )
        ).all()
        return {invoice.source_document_id: invoice for invoice in invoices if invoice.source_document_id}

    def bill_of_lading_for_document(self, document_id: uuid.UUID) -> BillOfLading | None:
        return self.session.scalar(
            select(BillOfLading).where(
                BillOfLading.company_id == self.company_id,
                BillOfLading.source_document_id == document_id,
            )
        )

    def bill_of_lading_references(
        self, document_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, BillOfLading]:
        if not document_ids:
            return {}
        bills = self.session.scalars(
            select(BillOfLading).where(
                BillOfLading.company_id == self.company_id,
                BillOfLading.source_document_id.in_(document_ids),
            )
        ).all()
        return {bill.source_document_id: bill for bill in bills if bill.source_document_id}
