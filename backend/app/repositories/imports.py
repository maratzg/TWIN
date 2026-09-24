import uuid

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import ImportCorrection, ImportIssue, ImportJob, ImportRow


class ImportRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def list_jobs(
        self,
        *,
        search: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ImportJob], int]:
        filters = [ImportJob.company_id == self.company_id]
        if search:
            filters.append(ImportJob.filename.ilike(f"%{search.strip()}%"))
        if status:
            filters.append(ImportJob.status == status)
        total = self.session.scalar(select(func.count(ImportJob.id)).where(*filters)) or 0
        jobs = self.session.scalars(
            select(ImportJob)
            .where(*filters)
            .order_by(ImportJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(jobs), total

    def list_rows(
        self,
        import_id: uuid.UUID,
        *,
        disposition: str | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ImportRow], int]:
        filters = [
            ImportRow.import_job_id == import_id,
            ImportJob.company_id == self.company_id,
        ]
        if disposition and disposition != "all":
            filters.append(ImportRow.disposition == disposition)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    cast(ImportRow.row_number, Text).ilike(pattern),
                    cast(ImportRow.raw_data, Text).ilike(pattern),
                    cast(ImportRow.normalized_data, Text).ilike(pattern),
                )
            )
        base = select(ImportRow).join(ImportJob, ImportJob.id == ImportRow.import_job_id).where(*filters)
        total = self.session.scalar(
            select(func.count(ImportRow.id))
            .join(ImportJob, ImportJob.id == ImportRow.import_job_id)
            .where(*filters)
        ) or 0
        rows = self.session.scalars(
            base.order_by(ImportRow.row_number).offset(offset).limit(limit)
        ).all()
        return list(rows), total

    def issues_for_rows(self, row_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ImportIssue]]:
        if not row_ids:
            return {}
        issues = self.session.scalars(
            select(ImportIssue)
            .join(ImportJob, ImportJob.id == ImportIssue.import_job_id)
            .where(
                ImportIssue.import_row_id.in_(row_ids),
                ImportJob.company_id == self.company_id,
            )
            .order_by(ImportIssue.row_number, ImportIssue.severity)
        ).all()
        grouped: dict[uuid.UUID, list[ImportIssue]] = {}
        for issue in issues:
            if issue.import_row_id:
                grouped.setdefault(issue.import_row_id, []).append(issue)
        return grouped

    def correction_counts(self, row_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not row_ids:
            return {}
        rows = self.session.execute(
            select(ImportCorrection.import_row_id, func.count(ImportCorrection.id))
            .where(
                ImportCorrection.company_id == self.company_id,
                ImportCorrection.import_row_id.in_(row_ids),
                ImportCorrection.correction_type == "value",
            )
            .group_by(ImportCorrection.import_row_id)
        ).all()
        return {row_id: count for row_id, count in rows if row_id is not None}
