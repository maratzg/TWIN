import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(20))
    selected_sheet: Mapped[str | None] = mapped_column(String(200))
    sheet_names: Mapped[list] = mapped_column(JSON, default=list)
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), index=True)
    detected_row_count: Mapped[int] = mapped_column(Integer, default=0)
    ready_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    mapping_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    columns = relationship("ImportColumn", cascade="all, delete-orphan", order_by="ImportColumn.position")
    rows = relationship("ImportRow", cascade="all, delete-orphan", order_by="ImportRow.row_number")
    issues = relationship("ImportIssue", cascade="all, delete-orphan")


class ImportColumn(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_columns"
    __table_args__ = (UniqueConstraint("import_job_id", "source_column"),)

    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    source_column: Mapped[str] = mapped_column(String(300))
    normalized_header: Mapped[str] = mapped_column(String(300))
    sample_values: Mapped[list] = mapped_column(JSON, default=list)
    canonical_field: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float]
    mapping_method: Mapped[str] = mapped_column(String(50))
    user_confirmed: Mapped[bool] = mapped_column(default=False)


class ImportRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("import_job_id", "row_number"),)

    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSON)
    system_normalized_data: Mapped[dict | None] = mapped_column(JSON)
    normalized_data: Mapped[dict | None] = mapped_column(JSON)
    disposition: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(200))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipments.id"), index=True)

    corrections = relationship(
        "ImportCorrection", cascade="all, delete-orphan", order_by="ImportCorrection.created_at"
    )


class ImportIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_issues"

    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    field: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)


class LearnedMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learned_mappings"
    __table_args__ = (UniqueConstraint("company_id", "normalized_header"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    source_header: Mapped[str] = mapped_column(String(300))
    normalized_header: Mapped[str] = mapped_column(String(300), index=True)
    canonical_field: Mapped[str] = mapped_column(String(100))
    confirmation_count: Mapped[int] = mapped_column(Integer, default=1)
    last_import_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_jobs.id"))
    origin: Mapped[str] = mapped_column(String(30), default="user_confirmed")


class ImportCorrection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_corrections"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_rows.id"), index=True)
    correction_type: Mapped[str] = mapped_column(String(30), index=True)
    source_column: Mapped[str | None] = mapped_column(String(300))
    canonical_field: Mapped[str | None] = mapped_column(String(100))
    previous_value: Mapped[object | None] = mapped_column(JSON)
    corrected_value: Mapped[object | None] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    reviewer_reference: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
