import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.input_engine.mapping import MappingService
from app.input_engine.normalization import normalize_value
from app.input_engine.parsers import TabularParser
from app.input_engine.validation import ValidationIssue, validate_rows
from app.models import (
    BillOfLading,
    Container,
    Customer,
    ImportColumn,
    ImportCorrection,
    ImportIssue,
    ImportJob,
    ImportRow,
    Port,
    Shipment,
    Vessel,
    Voyage,
)
from app.repositories.mappings import LearnedMappingRepository
from app.repositories.shipments import ShipmentRepository


ALLOWED_TRANSITIONS = {
    "analyzed": {"mapped", "validated", "needs_review"},
    "mapped": {"mapped", "validated", "needs_review"},
    "validated": {"mapped", "validated", "needs_review", "partially_committed", "committed"},
    "needs_review": {"mapped", "validated", "needs_review", "partially_committed", "committed"},
    "partially_committed": {"partially_committed", "committed"},
    "failed": {"mapped"},
    "committed": set(),
}


class ImportStateError(ValueError):
    pass


class ImportService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id
        self.parser = TabularParser()
        self.mapper = MappingService()

    def _job(self, import_id: uuid.UUID) -> ImportJob:
        job = self.session.scalar(
            select(ImportJob).where(
                ImportJob.id == import_id,
                ImportJob.company_id == self.company_id,
            )
        )
        if job is None:
            raise LookupError("Import job not found.")
        return job

    def _row(self, import_id: uuid.UUID, row_id: uuid.UUID) -> ImportRow:
        row = self.session.scalar(
            select(ImportRow)
            .join(ImportJob, ImportJob.id == ImportRow.import_job_id)
            .where(
                ImportRow.id == row_id,
                ImportRow.import_job_id == import_id,
                ImportJob.company_id == self.company_id,
            )
        )
        if row is None:
            raise LookupError("Import row not found.")
        return row

    @staticmethod
    def _transition(job: ImportJob, target: str) -> None:
        if target == job.status:
            return
        if target not in ALLOWED_TRANSITIONS.get(job.status, set()):
            raise ImportStateError(f"Cannot transition import from {job.status} to {target}.")
        job.status = target

    def analyze(self, filename: str, content: bytes) -> ImportJob:
        parsed = self.parser.parse(filename, content)
        learned = LearnedMappingRepository(self.session, self.company_id).as_dict()
        job = ImportJob(
            company_id=self.company_id,
            filename=Path(filename).name,
            source_type=parsed.source_type,
            selected_sheet=parsed.selected_sheet,
            sheet_names=parsed.sheet_names,
            header_row=parsed.header_row,
            status="analyzed",
            detected_row_count=len(parsed.rows),
        )
        self.session.add(job)
        self.session.flush()
        for position, source_column in enumerate(parsed.columns):
            proposal = self.mapper.propose(source_column, learned)
            job.columns.append(
                ImportColumn(
                    position=position,
                    source_column=source_column,
                    normalized_header=self._normalized(source_column),
                    sample_values=parsed.samples[source_column],
                    canonical_field=proposal.canonical_field,
                    confidence=proposal.confidence,
                    mapping_method=proposal.mapping_method,
                    user_confirmed=False,
                )
            )
        for index, raw in enumerate(parsed.rows, start=parsed.header_row + 1):
            job.rows.append(ImportRow(row_number=index, raw_data=raw, disposition="pending"))
        job.mapping_snapshot = self._mapping_snapshot(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    @staticmethod
    def _normalized(header: str) -> str:
        from app.input_engine.mapping import normalize_header

        return normalize_header(header)

    @staticmethod
    def _mapping_snapshot(job: ImportJob) -> dict:
        return {
            column.source_column: {
                "canonical_field": column.canonical_field,
                "confidence": column.confidence,
                "mapping_method": column.mapping_method,
                "user_confirmed": column.user_confirmed,
            }
            for column in job.columns
        }

    def get(self, import_id: uuid.UUID) -> ImportJob:
        return self._job(import_id)

    def update_mapping(
        self,
        import_id: uuid.UUID,
        updates: list[dict],
        *,
        reprocess: bool = False,
        reviewer_reference: str = "demo-reviewer",
    ) -> ImportJob:
        job = self._job(import_id)
        if any(row.disposition == "committed" for row in job.rows):
            raise ImportStateError("Mappings cannot change after any row has been committed.")
        if job.status == "committed":
            raise ImportStateError("Completed imports cannot be remapped.")

        columns = {column.source_column: column for column in job.columns}
        requested = {item["source_column"] for item in updates}
        unknown = requested - set(columns)
        if unknown:
            raise ValueError(f"Unknown source columns: {', '.join(sorted(unknown))}")

        learned_repository = LearnedMappingRepository(self.session, self.company_id)
        for item in updates:
            field = item.get("canonical_field")
            if field is not None and field not in self.mapper.canonical_fields:
                raise ValueError(f"Unknown canonical field: {field}")
            column = columns[item["source_column"]]
            previous_field = column.canonical_field
            column.canonical_field = field
            column.user_confirmed = bool(item.get("user_confirmed", True))
            if column.user_confirmed:
                column.confidence = 1.0 if field else 0.0
                column.mapping_method = "user_confirmed" if field else "user_unmapped"
            if previous_field != field:
                self.session.add(
                    ImportCorrection(
                        company_id=self.company_id,
                        import_job_id=job.id,
                        correction_type="mapping",
                        source_column=column.source_column,
                        canonical_field=field,
                        previous_value=previous_field,
                        corrected_value=field,
                        reviewer_reference=reviewer_reference,
                    )
                )
            if field and column.user_confirmed:
                learned_repository.confirm(
                    column.source_column,
                    column.normalized_header,
                    field,
                    job.id,
                )

        self._transition(job, "mapped")
        job.mapping_snapshot = self._mapping_snapshot(job)
        self.session.commit()
        self.session.refresh(job)
        if reprocess:
            self.validate(job.id)
            self.session.refresh(job)
        return job

    def validate(self, import_id: uuid.UUID) -> list:
        job = self._job(import_id)
        if job.status == "committed":
            raise ImportStateError("Completed imports cannot be revalidated.")

        rows = [row for row in job.rows if row.disposition != "committed"]
        mapping = {
            column.source_column: column.canonical_field
            for column in job.columns
            if column.canonical_field
        }
        unresolved = {
            column.source_column
            for column in job.columns
            if not column.canonical_field and not column.user_confirmed
        }
        corrections = self._value_corrections(rows)
        results = validate_rows(
            [(row.row_number, row.raw_data) for row in rows],
            mapping,
            unresolved,
            corrections,
        )
        shipment_repository = ShipmentRepository(self.session, self.company_id)
        for result in results:
            if result.disposition == "invalid":
                continue
            for field in (
                "shipment_reference",
                "booking_reference",
                "bill_of_lading_number",
                "container_number",
            ):
                value = result.normalized_data.get(field)
                if value and shipment_repository.exists_by_identity(field, str(value)):
                    result.issues.append(
                        ValidationIssue(
                            result.row_number,
                            field,
                            "ERROR",
                            "DUPLICATE_EXISTING",
                            "A canonical record with this identifier already exists for the company.",
                        )
                    )
                    result.disposition = "invalid"
                    break

        row_ids = [row.id for row in rows]
        if row_ids:
            self.session.execute(
                delete(ImportIssue).where(
                    ImportIssue.import_job_id == job.id,
                    ImportIssue.import_row_id.in_(row_ids),
                )
            )
        rows_by_number = {row.row_number: row for row in rows}
        validated_at = datetime.now(UTC)
        for result in results:
            row = rows_by_number[result.row_number]
            row.system_normalized_data = result.system_normalized_data
            row.normalized_data = result.normalized_data
            row.disposition = result.disposition
            row.last_validated_at = validated_at
            if result.disposition != "ready":
                row.approved_at = None
                row.approved_by = None
            for issue in result.issues:
                self.session.add(
                    ImportIssue(
                        import_job_id=job.id,
                        import_row_id=row.id,
                        row_number=issue.row,
                        field=issue.field,
                        severity=issue.severity,
                        code=issue.code,
                        message=issue.message,
                    )
                )
        self._refresh_counts_and_status(job)
        self.session.commit()
        return results

    def correct_row(
        self,
        import_id: uuid.UUID,
        row_id: uuid.UUID,
        canonical_field: str,
        corrected_value: Any,
        *,
        source_column: str | None = None,
        unit: str | None = None,
        reason: str | None = None,
        reviewer_reference: str = "demo-reviewer",
    ) -> ImportRow:
        job = self._job(import_id)
        row = self._row(import_id, row_id)
        if row.disposition == "committed":
            raise ImportStateError("Committed rows cannot be corrected.")
        if canonical_field not in self.mapper.canonical_fields:
            raise ValueError(f"Unknown canonical field: {canonical_field}")

        normalized_value = normalize_value(corrected_value, canonical_field)
        normalized_unit = unit.strip().lower() if unit else None
        if canonical_field == "gross_weight" and normalized_unit:
            if normalized_unit not in {"kg", "t", "tonne", "tonnes"}:
                raise ValueError("Gross weight unit must be kg or tonnes.")
            if normalized_unit in {"t", "tonne", "tonnes"}:
                normalized_value = format(Decimal(str(normalized_value)) * 1000, "f")
                normalized_unit = "kg"

        previous = (row.normalized_data or {}).get(canonical_field)
        self.session.add(
            ImportCorrection(
                company_id=self.company_id,
                import_job_id=job.id,
                import_row_id=row.id,
                correction_type="value",
                source_column=source_column,
                canonical_field=canonical_field,
                previous_value=previous,
                corrected_value=normalized_value,
                unit=normalized_unit,
                reason=reason,
                reviewer_reference=reviewer_reference,
            )
        )
        self.session.commit()
        self.validate(job.id)
        self.session.refresh(row)
        return row

    def approve_rows(
        self,
        import_id: uuid.UUID,
        row_ids: list[uuid.UUID],
        reviewer_reference: str = "demo-reviewer",
    ) -> dict:
        job = self._job(import_id)
        rows = self._selected_rows(job, row_ids)
        approved = 0
        skipped: list[dict] = []
        now = datetime.now(UTC)
        for row in rows:
            if row.disposition != "ready":
                skipped.append(self._skip(row, f"row_is_{row.disposition}"))
                continue
            row.approved_at = now
            row.approved_by = reviewer_reference
            approved += 1
        self.session.commit()
        return {"requested": len(row_ids), "approved": approved, "skipped": skipped}

    def commit_rows(
        self,
        import_id: uuid.UUID,
        row_ids: list[uuid.UUID] | None = None,
        reviewer_reference: str = "demo-reviewer",
    ) -> dict:
        job = self._job(import_id)
        if job.status not in {"validated", "needs_review", "partially_committed", "committed"}:
            raise ImportStateError("Import must be validated before commit.")
        if row_ids is None:
            rows = [row for row in job.rows if row.disposition == "ready"]
            requested = len(rows)
        else:
            rows = self._selected_rows(job, row_ids)
            requested = len(row_ids)

        repository = ShipmentRepository(self.session, self.company_id)
        committed = 0
        skipped: list[dict] = []
        now = datetime.now(UTC)
        for row in rows:
            if row.disposition == "committed":
                skipped.append(self._skip(row, "already_committed"))
                continue
            if row.disposition != "ready":
                skipped.append(self._skip(row, f"row_is_{row.disposition}"))
                continue
            duplicate_field = self._existing_identity(repository, row.normalized_data or {})
            if duplicate_field:
                row.disposition = "invalid"
                self.session.add(
                    ImportIssue(
                        import_job_id=job.id,
                        import_row_id=row.id,
                        row_number=row.row_number,
                        field=duplicate_field,
                        severity="ERROR",
                        code="DUPLICATE_EXISTING",
                        message="The record became a canonical duplicate before commit.",
                    )
                )
                skipped.append(self._skip(row, f"duplicate_{duplicate_field}"))
                continue
            shipment = self._persist_shipment(job, row)
            row.disposition = "committed"
            row.committed_at = now
            row.canonical_record_id = shipment.id
            row.approved_at = row.approved_at or now
            row.approved_by = row.approved_by or reviewer_reference
            committed += 1

        job.committed_at = now if committed else job.committed_at
        self._refresh_counts_and_status(job)
        self.session.commit()
        return {
            "import_id": job.id,
            "status": job.status,
            "requested": requested,
            "committed": committed,
            "skipped": skipped,
            "ready": job.ready_count,
            "needs_review": job.review_count,
            "invalid": job.rejected_count,
            "total_committed": job.imported_count,
        }

    def commit(self, import_id: uuid.UUID) -> ImportJob:
        self.commit_rows(import_id)
        return self._job(import_id)

    def issues(self, import_id: uuid.UUID) -> list[ImportIssue]:
        job = self._job(import_id)
        return list(
            self.session.scalars(
                select(ImportIssue)
                .where(ImportIssue.import_job_id == job.id)
                .order_by(ImportIssue.row_number, ImportIssue.severity)
            ).all()
        )

    def _value_corrections(self, rows: list[ImportRow]) -> dict[int, dict[str, Any]]:
        if not rows:
            return {}
        by_id = {row.id: row.row_number for row in rows}
        latest: dict[int, dict[str, Any]] = {row.row_number: {} for row in rows}
        corrections = self.session.scalars(
            select(ImportCorrection)
            .where(
                ImportCorrection.company_id == self.company_id,
                ImportCorrection.import_row_id.in_(list(by_id)),
                ImportCorrection.correction_type == "value",
            )
            .order_by(ImportCorrection.created_at, ImportCorrection.id)
        ).all()
        for correction in corrections:
            if correction.import_row_id and correction.canonical_field:
                latest[by_id[correction.import_row_id]][correction.canonical_field] = (
                    correction.corrected_value
                )
        return latest

    @staticmethod
    def _selected_rows(job: ImportJob, row_ids: list[uuid.UUID]) -> list[ImportRow]:
        by_id = {row.id: row for row in job.rows}
        unknown = [str(row_id) for row_id in row_ids if row_id not in by_id]
        if unknown:
            raise LookupError(f"Import rows not found: {', '.join(unknown)}")
        return [by_id[row_id] for row_id in row_ids]

    @staticmethod
    def _skip(row: ImportRow, reason: str) -> dict:
        return {"row_id": row.id, "row_number": row.row_number, "reason": reason}

    @staticmethod
    def _existing_identity(repository: ShipmentRepository, data: dict[str, Any]) -> str | None:
        for field in (
            "shipment_reference",
            "booking_reference",
            "bill_of_lading_number",
            "container_number",
        ):
            value = data.get(field)
            if value and repository.exists_by_identity(field, str(value)):
                return field
        return None

    def _refresh_counts_and_status(self, job: ImportJob) -> None:
        job.ready_count = sum(row.disposition == "ready" for row in job.rows)
        job.review_count = sum(row.disposition == "review" for row in job.rows)
        job.rejected_count = sum(row.disposition == "invalid" for row in job.rows)
        job.imported_count = sum(row.disposition == "committed" for row in job.rows)
        pending = job.detected_row_count - job.imported_count
        if pending == 0:
            target = "committed"
        elif job.imported_count:
            target = "partially_committed"
        elif job.review_count or job.rejected_count:
            target = "needs_review"
        else:
            target = "validated"
        self._transition(job, target)

    def _persist_shipment(self, job: ImportJob, row: ImportRow) -> Shipment:
        data = row.normalized_data or {}
        customer = self._customer(data.get("customer_name"))
        vessel = self._vessel(data.get("vessel_name"))
        voyage = self._voyage(data.get("voyage_number"), vessel)
        origin = self._port(data.get("port_of_loading"))
        destination = self._port(data.get("port_of_discharge"))
        reference = data.get("shipment_reference")
        if not reference and data.get("booking_reference"):
            reference = f"BOOK:{data['booking_reference']}"
        if not reference and data.get("bill_of_lading_number"):
            reference = f"BL:{data['bill_of_lading_number']}"
        if not reference and data.get("container_number"):
            reference = f"CNTR:{data['container_number']}"
        shipment = Shipment(
            company_id=self.company_id,
            customer_id=customer.id if customer else None,
            voyage_id=voyage.id if voyage else None,
            origin_port_id=origin.id if origin else None,
            destination_port_id=destination.id if destination else None,
            import_job_id=job.id,
            source_row_number=row.row_number,
            external_reference=reference,
            booking_reference=data.get("booking_reference"),
            etd=self._date(data.get("etd")),
            eta=self._date(data.get("eta")),
            status=data.get("status") or "IMPORTED",
            gross_weight=self._decimal(data.get("gross_weight")),
            revenue=self._decimal(data.get("revenue")),
            currency=data.get("currency"),
        )
        self.session.add(shipment)
        self.session.flush()
        if data.get("container_number"):
            self.session.add(
                Container(
                    company_id=self.company_id,
                    shipment_id=shipment.id,
                    container_number=data["container_number"].replace(" ", ""),
                    size_type=data.get("container_type"),
                    teu=self._decimal(data.get("teu")),
                    gross_weight=self._decimal(data.get("gross_weight")),
                )
            )
        if data.get("bill_of_lading_number"):
            self.session.add(
                BillOfLading(
                    company_id=self.company_id,
                    shipment_id=shipment.id,
                    number=data["bill_of_lading_number"],
                )
            )
        return shipment

    def _customer(self, name: str | None) -> Customer | None:
        if not name:
            return None
        customer = self.session.scalar(
            select(Customer).where(
                Customer.company_id == self.company_id,
                func.lower(Customer.name) == name.lower(),
            )
        )
        if customer:
            return customer
        customer = Customer(company_id=self.company_id, name=name)
        self.session.add(customer)
        self.session.flush()
        return customer

    def _vessel(self, name: str | None) -> Vessel | None:
        if not name:
            return None
        vessel = self.session.scalar(
            select(Vessel).where(
                Vessel.company_id == self.company_id,
                func.lower(Vessel.name) == name.lower(),
            )
        )
        if vessel:
            return vessel
        vessel = Vessel(company_id=self.company_id, name=name)
        self.session.add(vessel)
        self.session.flush()
        return vessel

    def _voyage(self, number: str | None, vessel: Vessel | None) -> Voyage | None:
        if not number:
            return None
        voyage = self.session.scalar(
            select(Voyage).where(
                Voyage.company_id == self.company_id,
                Voyage.voyage_number == number,
                Voyage.vessel_id == (vessel.id if vessel else None),
            )
        )
        if voyage:
            return voyage
        voyage = Voyage(
            company_id=self.company_id,
            vessel_id=vessel.id if vessel else None,
            voyage_number=number,
        )
        self.session.add(voyage)
        self.session.flush()
        return voyage

    def _port(self, value: str | None) -> Port | None:
        if not value:
            return None
        compact = value.replace(" ", "").upper()
        unlocode = compact if len(compact) == 5 and compact.isalnum() else None
        port = self.session.scalar(
            select(Port).where(
                Port.company_id == self.company_id,
                (Port.unlocode == unlocode)
                if unlocode
                else (func.lower(Port.name) == value.lower()),
            )
        )
        if port:
            return port
        port = Port(
            company_id=self.company_id,
            unlocode=unlocode,
            name=value,
            country_code=unlocode[:2] if unlocode else None,
        )
        self.session.add(port)
        self.session.flush()
        return port

    @staticmethod
    def _decimal(value: str | None) -> Decimal | None:
        return Decimal(value) if value is not None else None

    @staticmethod
    def _date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None
