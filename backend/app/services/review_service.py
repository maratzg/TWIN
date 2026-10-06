import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Company,
    DocumentFieldCandidate,
    ImportCorrection,
    ImportIssue,
    ImportJob,
    ImportRow,
    SourceDocument,
)
from app.repositories.imports import ImportRepository
from app.services.import_service import ImportService


class ImportReviewService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id
        self.repository = ImportRepository(session, company_id)
        self.imports = ImportService(session, company_id)

    def history(
        self,
        *,
        search: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        jobs, total = self.repository.list_jobs(
            search=search,
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def detail(self, import_id: uuid.UUID) -> dict:
        job = self.imports.get(import_id)
        company = self.session.scalar(
            select(Company).where(Company.id == self.company_id)
        )
        return {
            "job": job,
            "company_name": company.name if company else "Unknown company",
            "mapping_complete": all(
                column.canonical_field or column.user_confirmed for column in job.columns
            ),
            "validation_complete": all(
                row.last_validated_at is not None or row.disposition == "committed"
                for row in job.rows
            ),
            "canonical_fields": self.imports.mapper.canonical_fields,
        }

    def rows(
        self,
        import_id: uuid.UUID,
        *,
        disposition: str | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        self.imports.get(import_id)
        rows, total = self.repository.list_rows(
            import_id,
            disposition=disposition,
            search=search,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        row_ids = [row.id for row in rows]
        issues = self.repository.issues_for_rows(row_ids)
        correction_counts = self.repository.correction_counts(row_ids)
        return {
            "items": [
                {
                    "row": row,
                    "issue_codes": [issue.code for issue in issues.get(row.id, [])],
                    "issue_count": len(issues.get(row.id, [])),
                    "correction_count": correction_counts.get(row.id, 0),
                    "summary": self._row_summary(row),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def row_detail(self, import_id: uuid.UUID, row_id: uuid.UUID) -> dict:
        job = self.imports.get(import_id)
        row = self.imports._row(import_id, row_id)
        issues = list(
            self.session.scalars(
                select(ImportIssue)
                .where(
                    ImportIssue.import_job_id == job.id,
                    ImportIssue.import_row_id == row.id,
                )
                .order_by(ImportIssue.severity.desc(), ImportIssue.field)
            ).all()
        )
        corrections = list(
            self.session.scalars(
                select(ImportCorrection)
                .where(
                    ImportCorrection.company_id == self.company_id,
                    ImportCorrection.import_job_id == job.id,
                    ImportCorrection.import_row_id == row.id,
                )
                .order_by(ImportCorrection.created_at.desc())
            ).all()
        )
        cells = self._cells(job, row, issues)
        return {
            "row": row,
            "cells": cells,
            "issues": issues,
            "corrections": corrections,
            "canonical_fields": self.imports.mapper.canonical_fields,
        }

    def data_quality(self) -> dict:
        job_filter = ImportJob.company_id == self.company_id
        imports_requiring_review = self.session.scalar(
            select(func.count(ImportJob.id)).where(
                job_filter,
                ImportJob.status.in_(["needs_review", "partially_committed"]),
            )
        ) or 0
        dispositions = dict(
            self.session.execute(
                select(ImportRow.disposition, func.count(ImportRow.id))
                .join(ImportJob, ImportJob.id == ImportRow.import_job_id)
                .where(job_filter, ImportRow.disposition != "pending")
                .group_by(ImportRow.disposition)
            ).all()
        )
        since = datetime.now(UTC) - timedelta(days=30)
        recent_successful = self.session.scalar(
            select(func.count(ImportJob.id)).where(
                job_filter,
                ImportJob.status == "committed",
                ImportJob.created_at >= since,
            )
        ) or 0
        recent_failed = self.session.scalar(
            select(func.count(ImportJob.id)).where(
                job_filter,
                ImportJob.status == "failed",
                ImportJob.created_at >= since,
            )
        ) or 0
        document_filter = SourceDocument.company_id == self.company_id
        documents_awaiting_review = self.session.scalar(
            select(func.count(SourceDocument.id)).where(
                document_filter,
                SourceDocument.status == "needs_review",
            )
        ) or 0
        failed_document_processing = self.session.scalar(
            select(func.count(SourceDocument.id)).where(
                document_filter,
                SourceDocument.status == "failed",
            )
        ) or 0
        unresolved_document_fields = self.session.scalar(
            select(func.count(DocumentFieldCandidate.id))
            .join(SourceDocument, SourceDocument.id == DocumentFieldCandidate.document_id)
            .where(
                document_filter,
                DocumentFieldCandidate.status.in_(["review", "error"]),
                SourceDocument.status != "committed",
            )
        ) or 0
        recent_processed_documents = self.session.scalar(
            select(func.count(SourceDocument.id)).where(
                document_filter,
                SourceDocument.status.not_in(["uploaded", "extracting"]),
                SourceDocument.created_at >= since,
            )
        ) or 0
        ready = dispositions.get("ready", 0) + dispositions.get("committed", 0)
        review = dispositions.get("review", 0)
        invalid = dispositions.get("invalid", 0)
        total = ready + review + invalid
        return {
            "ready_rows": ready,
            "review_rows": review,
            "invalid_rows": invalid,
            "total_evaluated_rows": total,
            "ready_percent": round(ready / total * 100, 1) if total else 0.0,
            "review_percent": round(review / total * 100, 1) if total else 0.0,
            "invalid_percent": round(invalid / total * 100, 1) if total else 0.0,
            "unresolved_issues": review + invalid,
            "imports_requiring_review": imports_requiring_review,
            "recent_successful_imports": recent_successful,
            "recent_failed_imports": recent_failed,
            "documents_awaiting_review": documents_awaiting_review,
            "failed_document_processing": failed_document_processing,
            "unresolved_document_fields": unresolved_document_fields,
            "recent_processed_documents": recent_processed_documents,
        }

    @staticmethod
    def _row_summary(row: ImportRow) -> dict[str, Any]:
        data = row.normalized_data or {}
        return {
            "reference": data.get("shipment_reference")
            or data.get("booking_reference")
            or data.get("bill_of_lading_number")
            or data.get("container_number"),
            "customer": data.get("customer_name"),
            "container": data.get("container_number"),
            "gross_weight": data.get("gross_weight"),
        }

    @staticmethod
    def _cells(job: ImportJob, row: ImportRow, issues: list[ImportIssue]) -> list[dict]:
        cells: list[dict] = []
        represented_fields: set[str] = set()
        for column in job.columns:
            field = column.canonical_field
            if field:
                represented_fields.add(field)
            cell_issues = [
                issue
                for issue in issues
                if issue.field in {column.source_column, field}
            ]
            cells.append(
                {
                    "source_column": column.source_column,
                    "raw_value": row.raw_data.get(column.source_column),
                    "canonical_field": field,
                    "system_normalized_value": (row.system_normalized_data or {}).get(field)
                    if field
                    else None,
                    "normalized_value": (row.normalized_data or {}).get(field)
                    if field
                    else None,
                    "status": ImportReviewService._cell_status(cell_issues, row.disposition),
                    "issues": cell_issues,
                }
            )
        for field, value in (row.normalized_data or {}).items():
            if field not in represented_fields:
                cell_issues = [issue for issue in issues if issue.field == field]
                cells.append(
                    {
                        "source_column": None,
                        "raw_value": None,
                        "canonical_field": field,
                        "system_normalized_value": (row.system_normalized_data or {}).get(field),
                        "normalized_value": value,
                        "status": ImportReviewService._cell_status(cell_issues, row.disposition),
                        "issues": cell_issues,
                    }
                )
        return cells

    @staticmethod
    def _cell_status(issues: list[ImportIssue], disposition: str) -> str:
        if disposition == "committed":
            return "committed"
        severities = {issue.severity for issue in issues}
        if "ERROR" in severities:
            return "error"
        if "WARNING" in severities:
            return "review"
        return "valid"
