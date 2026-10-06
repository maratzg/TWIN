import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SourceDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    document_type: Mapped[str] = mapped_column(String(30), default="UNKNOWN", index=True)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0)
    classification_method: Mapped[str | None] = mapped_column(String(80))
    classification_signals: Mapped[list] = mapped_column(JSON, default=list)
    extraction_version: Mapped[str | None] = mapped_column(String(80))
    extraction_method: Mapped[str | None] = mapped_column(String(50))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(200))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pages = relationship("DocumentPage", cascade="all, delete-orphan", order_by="DocumentPage.page_number")
    candidates = relationship("DocumentFieldCandidate", cascade="all, delete-orphan", order_by="DocumentFieldCandidate.field_name")
    issues = relationship("DocumentIssue", cascade="all, delete-orphan")
    corrections = relationship("DocumentCorrection", cascade="all, delete-orphan", order_by="DocumentCorrection.created_at")


class DocumentPage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    extraction_method: Mapped[str] = mapped_column(String(50))
    char_count: Mapped[int] = mapped_column(Integer, default=0)


class DocumentFieldCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_field_candidates"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "group_type", "group_index", "field_name",
            name="uq_doc_candidates_group_field",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100), index=True)
    group_type: Mapped[str] = mapped_column(String(50), default="document", index=True)
    group_index: Mapped[int] = mapped_column(Integer, default=0)
    raw_value: Mapped[str | None] = mapped_column(Text)
    system_normalized_value: Mapped[object | None] = mapped_column(JSON)
    normalized_value: Mapped[object | None] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(80))
    page_number: Mapped[int | None] = mapped_column(Integer)
    evidence: Mapped[str | None] = mapped_column(Text)
    bounding_box: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)
    matched_entity_type: Mapped[str | None] = mapped_column(String(50))
    matched_entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    match_method: Mapped[str | None] = mapped_column(String(50))
    match_confidence: Mapped[float | None] = mapped_column(Float)


class DocumentIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_issues"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    field_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_field_candidates.id"), index=True
    )
    field: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(10), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)


class DocumentCorrection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_corrections"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    field_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_field_candidates.id"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(100))
    previous_value: Mapped[object | None] = mapped_column(JSON)
    corrected_value: Mapped[object | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    reviewer_reference: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
