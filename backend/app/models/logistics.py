import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Port(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ports"
    __table_args__ = (UniqueConstraint("company_id", "unlocode"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    unlocode: Mapped[str | None] = mapped_column(String(5), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2))


class Vessel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vessels"
    __table_args__ = (UniqueConstraint("company_id", "name", "imo_number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    imo_number: Mapped[str | None] = mapped_column(String(20))


class Voyage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "voyages"
    __table_args__ = (UniqueConstraint("company_id", "vessel_id", "voyage_number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    vessel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vessels.id"), index=True)
    voyage_number: Mapped[str] = mapped_column(String(100), index=True)
    departure_date: Mapped[date | None] = mapped_column(Date)
    arrival_date: Mapped[date | None] = mapped_column(Date)

    vessel: Mapped[Vessel | None] = relationship()


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("company_id", "external_reference"),
        UniqueConstraint(
            "company_id",
            "booking_reference",
            name="uq_shipments_company_booking_reference",
        ),
        Index("ix_shipments_company_etd", "company_id", "etd"),
        Index("ix_shipments_company_customer_etd", "company_id", "customer_id", "etd"),
        Index(
            "ix_shipments_company_route_etd",
            "company_id",
            "origin_port_id",
            "destination_port_id",
            "etd",
        ),
        Index("ix_shipments_company_voyage_etd", "company_id", "voyage_id", "etd"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)
    voyage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("voyages.id"), index=True)
    origin_port_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ports.id"), index=True)
    destination_port_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ports.id"), index=True)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    source_row_number: Mapped[int | None]
    external_reference: Mapped[str | None] = mapped_column(String(200), index=True)
    booking_reference: Mapped[str | None] = mapped_column(String(200), index=True)
    source_system_reference: Mapped[str | None] = mapped_column(String(200))
    etd: Mapped[date | None] = mapped_column(Date)
    eta: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(50))
    gross_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))

    customer = relationship("Customer")
    voyage = relationship("Voyage")
    origin_port = relationship("Port", foreign_keys=[origin_port_id])
    destination_port = relationship("Port", foreign_keys=[destination_port_id])
    containers = relationship("Container", back_populates="shipment", cascade="all, delete-orphan")
    bills_of_lading = relationship("BillOfLading", back_populates="shipment", cascade="all, delete-orphan")


class Container(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "containers"
    __table_args__ = (UniqueConstraint("company_id", "container_number", "shipment_id"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), index=True)
    source_candidate_group: Mapped[str | None] = mapped_column(String(100))
    container_number: Mapped[str] = mapped_column(String(20), index=True)
    size_type: Mapped[str | None] = mapped_column(String(20))
    seal_number: Mapped[str | None] = mapped_column(String(100))
    package_count: Mapped[int | None] = mapped_column(Integer)
    package_type: Mapped[str | None] = mapped_column(String(100))
    teu: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    gross_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    status: Mapped[str | None] = mapped_column(String(50))

    shipment: Mapped[Shipment] = relationship(back_populates="containers")


class BillOfLading(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bills_of_lading"
    __table_args__ = (UniqueConstraint("company_id", "number"),)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id"), unique=True, index=True
    )
    shipper_supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    consignee_customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"), index=True)
    number: Mapped[str] = mapped_column(String(200), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date)
    carrier: Mapped[str | None] = mapped_column(String(200))
    shipper: Mapped[str | None] = mapped_column(String(300))
    consignee: Mapped[str | None] = mapped_column(String(300))
    notify_party: Mapped[str | None] = mapped_column(String(300))
    references: Mapped[str | None] = mapped_column(String(500))
    description_of_goods: Mapped[str | None] = mapped_column(Text)
    total_packages: Mapped[int | None] = mapped_column(Integer)
    total_gross_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    measurement: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    measurement_unit: Mapped[str | None] = mapped_column(String(20))

    shipment: Mapped[Shipment] = relationship(back_populates="bills_of_lading")
    shipper_supplier = relationship("Supplier", foreign_keys=[shipper_supplier_id])
    consignee_customer = relationship("Customer", foreign_keys=[consignee_customer_id])
