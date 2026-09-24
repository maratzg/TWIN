import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearnedMapping


class LearnedMappingRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def as_dict(self) -> dict[str, str]:
        rows = self.session.scalars(
            select(LearnedMapping).where(LearnedMapping.company_id == self.company_id)
        ).all()
        return {row.normalized_header: row.canonical_field for row in rows}

    def confirm(
        self,
        source_header: str,
        normalized_header: str,
        canonical_field: str,
        import_job_id: uuid.UUID,
    ) -> LearnedMapping:
        mapping = self.session.scalar(
            select(LearnedMapping).where(
                LearnedMapping.company_id == self.company_id,
                LearnedMapping.normalized_header == normalized_header,
            )
        )
        if mapping:
            mapping.source_header = source_header
            mapping.canonical_field = canonical_field
            mapping.confirmation_count += 1
            mapping.last_import_job_id = import_job_id
            mapping.origin = "user_confirmed"
            return mapping
        mapping = LearnedMapping(
            company_id=self.company_id,
            source_header=source_header,
            normalized_header=normalized_header,
            canonical_field=canonical_field,
            last_import_job_id=import_job_id,
            origin="user_confirmed",
        )
        self.session.add(mapping)
        return mapping

