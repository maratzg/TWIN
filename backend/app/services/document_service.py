import hashlib
import logging
import math
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.document_engine.classification import DocumentClassifier
from app.document_engine.extractors import BillOfLadingExtractor, InvoiceExtractor
from app.document_engine.normalization import derive_teu, normalize_bill_of_lading_value, normalize_invoice_value
from app.document_engine.ocr import OCRProvider, OCRUnavailableError, UnavailableOCRProvider
from app.document_engine.parsers import PDFDocumentError, PDFParser
from app.document_engine.storage import DocumentStorage, LocalDocumentStorage
from app.document_engine.types import ExtractedCandidate, ExtractedPage, ValidationFinding
from app.document_engine.validation import validate_bill_of_lading_candidates, validate_invoice_candidates
from app.models import (
    BillOfLading,
    Company,
    Customer,
    DocumentCorrection,
    DocumentFieldCandidate,
    DocumentIssue,
    DocumentPage,
    Invoice,
    Container,
    Port,
    Shipment,
    SourceDocument,
    Supplier,
    Vessel,
    Voyage,
)
from app.repositories.documents import DocumentRepository


logger = logging.getLogger("app.document_processing")
settings = get_settings()
PartyModel = TypeVar("PartyModel", Customer, Supplier)

INVOICE_FIELDS = [
    "invoice_number", "invoice_date", "due_date", "direction",
    "supplier_name", "supplier_registration_number", "supplier_vat_number",
    "customer_name", "customer_registration_number", "customer_vat_number",
    "currency", "subtotal", "vat_amount", "total_amount", "vat_rate",
    "payment_reference", "purchase_order_reference", "shipment_reference",
    "booking_reference", "bill_of_lading_reference", "bank_details",
]

BILL_OF_LADING_FIELDS = [
    "bill_of_lading_number", "issue_date", "shipper_name", "shipper_registration_number",
    "shipper_vat_number", "consignee_name", "consignee_registration_number",
    "consignee_vat_number", "notify_party_name", "carrier_name", "vessel_name",
    "vessel_imo_number", "voyage_number", "port_of_loading", "port_of_discharge",
    "place_of_receipt", "place_of_delivery", "shipment_reference", "booking_reference",
    "description_of_goods", "total_packages", "total_gross_weight", "measurement",
    "measurement_unit",
]

CONTAINER_FIELDS = [
    "container_number", "container_size_type", "seal_number", "package_count",
    "package_type", "gross_weight",
]

ALLOWED_DOCUMENT_TRANSITIONS = {
    "uploaded": {"extracting", "failed"},
    "extracting": {"classified", "failed"},
    "classified": {"extracted", "needs_review", "failed"},
    "extracted": {"ready", "needs_review", "failed"},
    "needs_review": {"classified", "ready", "needs_review", "approved", "failed"},
    "ready": {"ready", "needs_review", "approved", "failed"},
    "approved": {"ready", "needs_review", "committed", "failed"},
    "committed": set(),
    "failed": set(),
}


class DocumentStateError(ValueError):
    pass


class DocumentUploadError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class DocumentService:
    def __init__(
        self,
        session: Session,
        company_id: uuid.UUID,
        *,
        storage: DocumentStorage | None = None,
        ocr: OCRProvider | None = None,
    ) -> None:
        self.session = session
        self.company_id = company_id
        self.repository = DocumentRepository(session, company_id)
        self.storage = storage or LocalDocumentStorage(settings.document_storage_path)
        self.ocr = ocr or UnavailableOCRProvider()
        self.parser = PDFParser()
        self.classifier = DocumentClassifier(settings.document_classification_threshold)
        self.invoice_extractor = InvoiceExtractor()
        self.bill_of_lading_extractor = BillOfLadingExtractor()

    def upload(self, filename: str, content_type: str | None, content: bytes) -> SourceDocument:
        safe_filename = self._validate_upload(filename, content_type, content)
        document_id = uuid.uuid4()
        checksum = hashlib.sha256(content).hexdigest()
        storage_key = self.storage.put(self.company_id, document_id, checksum, content)
        document = SourceDocument(
            id=document_id,
            company_id=self.company_id,
            original_filename=safe_filename,
            content_type="application/pdf",
            size_bytes=len(content),
            checksum_sha256=checksum,
            storage_key=storage_key,
            status="uploaded",
            document_type="UNKNOWN",
            classification_confidence=0,
        )
        self.session.add(document)
        self.session.commit()
        logger.info("document_uploaded", extra=self._log_context(document))
        return self.process(document.id)

    def process(self, document_id: uuid.UUID) -> SourceDocument:
        document = self.get(document_id)
        if document.status != "uploaded":
            raise DocumentStateError("Only newly uploaded documents can enter extraction.")
        try:
            self._transition(document, "extracting")
            self.session.commit()
            logger.info("document_parsing_started", extra=self._log_context(document))
            content = self.storage.read(document.storage_key)
            pages = self.parser.parse(content)
            if sum(len(page.text.strip()) for page in pages) < 20:
                try:
                    pages = self.ocr.extract(self.storage.path(document.storage_key))
                except OCRUnavailableError as exc:
                    return self._fail(document, "OCR_REQUIRED", str(exc))
            self._store_pages(document, pages)
            document.extraction_method = pages[0].extraction_method if pages else None
            document.page_count = len(pages)
            logger.info("document_text_extracted", extra={**self._log_context(document), "page_count": len(pages)})

            result = self.classifier.classify(pages)
            document.document_type = result.document_type
            document.classification_confidence = result.confidence
            document.classification_method = result.method
            document.classification_signals = result.signals
            self._transition(document, "classified")
            logger.info("document_classified", extra={**self._log_context(document), "document_type": result.document_type, "confidence": result.confidence})
            if result.document_type not in {"INVOICE", "BILL_OF_LADING"}:
                self._replace_issues(
                    document,
                    [ValidationFinding(None, "ERROR", "DOCUMENT_TYPE_UNKNOWN", "The document could not be classified confidently as a supported document type.")],
                )
                self._transition(document, "needs_review")
                self._refresh_counts(document)
                self.session.commit()
                return document

            self._extract_document(document)
            self._transition(document, "extracted")
            self.session.commit()
            logger.info("document_extraction_completed", extra={**self._log_context(document), "field_count": document.field_count})
            return self.validate(document.id)
        except PDFDocumentError as exc:
            return self._fail(document, exc.code, str(exc))
        except Exception:
            logger.exception("document_processing_failed", extra=self._log_context(document))
            return self._fail(document, "PROCESSING_FAILED", "Document processing failed safely.")

    def get(self, document_id: uuid.UUID) -> SourceDocument:
        document = self.repository.get(document_id)
        if document is None:
            raise LookupError("Document not found.")
        return document

    def history(
        self,
        *,
        search: str | None,
        status: str | None,
        document_type: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        documents, total = self.repository.list(
            search=search,
            status=status,
            document_type=document_type,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        counts = self.repository.candidate_status_counts([document.id for document in documents])
        invoices = self.repository.invoice_references([document.id for document in documents])
        bills = self.repository.bill_of_lading_references([document.id for document in documents])
        return {
            "items": [
                self._summary(
                    document,
                    counts.get(document.id, {}),
                    invoices.get(document.id),
                    bills.get(document.id),
                )
                for document in documents
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def detail(self, document_id: uuid.UUID) -> dict:
        document = self.get(document_id)
        invoice = self.repository.invoice_for_document(document.id)
        bill_of_lading = self.repository.bill_of_lading_for_document(document.id)
        return {
            "document": document,
            "pages": list(document.pages),
            "candidates": list(document.candidates),
            "issues": sorted(document.issues, key=lambda issue: (issue.severity != "ERROR", issue.field or "")),
            "corrections": list(reversed(document.corrections)),
            "canonical_invoice": invoice,
            "canonical_bill_of_lading": bill_of_lading,
            "canonical_fields": self._document_fields(document.document_type),
        }

    def confirm_classification(
        self,
        document_id: uuid.UUID,
        document_type: str,
        reviewer_reference: str = "demo-reviewer",
    ) -> SourceDocument:
        document = self.get(document_id)
        if document.status != "needs_review" or document.document_type != "UNKNOWN":
            raise DocumentStateError("Only an unknown document awaiting review can be classified manually.")
        if document_type not in {"INVOICE", "BILL_OF_LADING"}:
            raise ValueError("Choose INVOICE or BILL_OF_LADING.")
        previous = document.document_type
        document.document_type = document_type
        document.classification_confidence = 1.0
        document.classification_method = "user_confirmed"
        document.classification_signals = ["human_confirmation"]
        self.session.add(
            DocumentCorrection(
                company_id=self.company_id,
                document_id=document.id,
                field_name="document_type",
                previous_value=previous,
                corrected_value=document_type,
                reviewer_reference=reviewer_reference,
            )
        )
        self._transition(document, "classified")
        self._extract_document(document)
        self._transition(document, "extracted")
        self.session.commit()
        return self.validate(document.id)

    def correct_field(
        self,
        document_id: uuid.UUID,
        field_name: str,
        corrected_value: Any,
        *,
        reason: str | None = None,
        reviewer_reference: str = "demo-reviewer",
    ) -> SourceDocument:
        document = self.get(document_id)
        if document.status in {"committed", "failed"}:
            raise DocumentStateError(f"Documents in {document.status} state cannot be corrected.")
        if field_name not in self._document_fields(document.document_type):
            raise ValueError(f"Unknown {document.document_type.lower()} field: {field_name}")
        candidate = next(
            (item for item in document.candidates if item.field_name == field_name and item.group_type == "document"),
            None,
        )
        previous = candidate.normalized_value if candidate else None
        normalized = self._normalize_value(document.document_type, field_name, corrected_value)
        if candidate is None:
            candidate = DocumentFieldCandidate(
                document_id=document.id,
                field_name=field_name,
                group_type="document",
                group_index=0,
                raw_value=None,
                system_normalized_value=None,
                normalized_value=normalized,
                confidence=1.0,
                extraction_method="user_corrected",
                status="ready" if normalized is not None else "error",
            )
            self.session.add(candidate)
            self.session.flush()
        else:
            candidate.normalized_value = normalized
            candidate.confidence = 1.0
            candidate.extraction_method = "user_corrected"
            candidate.status = "ready" if normalized is not None else "error"
            candidate.matched_entity_type = None
            candidate.matched_entity_id = None
            candidate.match_method = None
            candidate.match_confidence = None
        self.session.add(
            DocumentCorrection(
                company_id=self.company_id,
                document_id=document.id,
                field_candidate_id=candidate.id,
                field_name=field_name,
                previous_value=previous,
                corrected_value=normalized if normalized is not None else str(corrected_value),
                reason=reason,
                reviewer_reference=reviewer_reference,
            )
        )
        document.approved_at = None
        document.approved_by = None
        self.session.commit()
        logger.info("document_correction_applied", extra={**self._log_context(document), "field": field_name})
        return self.validate(document.id)

    def correct_candidate(
        self,
        document_id: uuid.UUID,
        candidate_id: uuid.UUID,
        corrected_value: Any,
        *,
        reason: str | None = None,
        reviewer_reference: str = "demo-reviewer",
    ) -> SourceDocument:
        document = self.get(document_id)
        if document.status in {"committed", "failed"}:
            raise DocumentStateError(f"Documents in {document.status} state cannot be corrected.")
        candidate = next((item for item in document.candidates if item.id == candidate_id), None)
        if candidate is None:
            raise LookupError("Field candidate not found.")
        if candidate.group_type != "container" or candidate.field_name not in CONTAINER_FIELDS:
            raise ValueError("Candidate-specific correction is reserved for repeating container fields.")
        previous = candidate.normalized_value
        normalized = self._normalize_value(document.document_type, candidate.field_name, corrected_value)
        candidate.normalized_value = normalized
        candidate.confidence = 1.0
        candidate.extraction_method = "user_corrected"
        candidate.status = "ready" if normalized is not None else "error"
        candidate.matched_entity_type = None
        candidate.matched_entity_id = None
        candidate.match_method = None
        candidate.match_confidence = None
        self.session.add(
            DocumentCorrection(
                company_id=self.company_id,
                document_id=document.id,
                field_candidate_id=candidate.id,
                field_name=f"containers[{candidate.group_index}].{candidate.field_name}",
                previous_value=previous,
                corrected_value=normalized if normalized is not None else str(corrected_value),
                reason=reason,
                reviewer_reference=reviewer_reference,
            )
        )
        document.approved_at = None
        document.approved_by = None
        self.session.commit()
        logger.info("document_correction_applied", extra={**self._log_context(document), "field": candidate.field_name})
        return self.validate(document.id)

    def validate(self, document_id: uuid.UUID) -> SourceDocument:
        document = self.get(document_id)
        if document.status in {"committed", "failed"}:
            raise DocumentStateError(f"Documents in {document.status} state cannot be revalidated.")
        if document.document_type == "INVOICE":
            self._derive_direction(document)
            self.session.flush()
            self.session.expire(document, ["candidates"])
            party_resolution = self._match_parties(document)
            reference_conflict = self._match_references(document)
            values = self._values(document)
            findings = self._invoice_findings(document, values, party_resolution, reference_conflict)
        elif document.document_type == "BILL_OF_LADING":
            findings = self._validate_bill_of_lading(document)
        else:
            raise DocumentStateError("Only confirmed supported documents can be validated.")
        self._replace_issues(document, findings)
        document.approved_at = None
        document.approved_by = None
        target = "needs_review" if findings else "ready"
        self._transition(document, target)
        self._refresh_counts(document)
        self.session.commit()
        logger.info("document_validation_completed", extra={**self._log_context(document), "errors": document.error_count, "review": document.review_count})
        if findings:
            logger.info("document_review_required", extra={**self._log_context(document), "issue_count": len(findings)})
        return document

    def approve(self, document_id: uuid.UUID, reviewer_reference: str = "demo-reviewer") -> SourceDocument:
        document = self.get(document_id)
        if document.status not in {"ready", "needs_review"}:
            raise DocumentStateError("Document must be validated before approval.")
        if any(issue.severity == "ERROR" for issue in document.issues):
            raise DocumentStateError("Documents with error-level issues cannot be approved.")
        document.approved_at = datetime.now(UTC)
        document.approved_by = reviewer_reference
        self._transition(document, "approved")
        self.session.commit()
        logger.info("document_approved", extra=self._log_context(document))
        return document

    def commit(self, document_id: uuid.UUID) -> tuple[SourceDocument, Invoice | BillOfLading]:
        document = self.get(document_id)
        existing_for_source = (
            self.repository.invoice_for_document(document.id)
            if document.document_type == "INVOICE"
            else self.repository.bill_of_lading_for_document(document.id)
        )
        if document.status == "committed" and existing_for_source:
            return document, existing_for_source
        if document.status != "approved":
            raise DocumentStateError("Only an approved document can be committed.")
        if any(issue.severity == "ERROR" for issue in document.issues):
            raise DocumentStateError("Documents with error-level issues cannot be committed.")
        if document.document_type == "BILL_OF_LADING":
            return self._commit_bill_of_lading(document)
        if document.document_type != "INVOICE":
            raise DocumentStateError("The document type has no canonical commit adapter.")
        return self._commit_invoice(document)

    def _commit_invoice(self, document: SourceDocument) -> tuple[SourceDocument, Invoice]:
        values = self._values(document)
        duplicate = self._existing_invoice(values)
        if duplicate:
            raise DocumentStateError("A canonical invoice with this identity already exists.")
        direction = str(values["direction"])
        customer_id, supplier_id = self._resolve_or_create_party(document, values, direction)
        invoice = Invoice(
            company_id=self.company_id,
            source_document_id=document.id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            shipment_id=self._matched_shipment_id(document),
            invoice_number=str(values["invoice_number"]),
            direction=direction,
            invoice_date=date.fromisoformat(str(values["invoice_date"])),
            due_date=date.fromisoformat(str(values["due_date"])) if values.get("due_date") else None,
            subtotal=Decimal(str(values["subtotal"])),
            vat=Decimal(str(values["vat_amount"])),
            total=Decimal(str(values["total_amount"])),
            currency=str(values["currency"]),
            status="open",
        )
        self.session.add(invoice)
        self.session.flush()
        document.committed_at = datetime.now(UTC)
        self._transition(document, "committed")
        self.session.commit()
        logger.info("document_commit_completed", extra={**self._log_context(document), "invoice_id": str(invoice.id)})
        return document, invoice

    def source_path(self, document_id: uuid.UUID) -> Path:
        return self.storage.path(self.get(document_id).storage_key)

    def issues(self, document_id: uuid.UUID) -> list[DocumentIssue]:
        return list(self.get(document_id).issues)

    def _extract_document(self, document: SourceDocument) -> None:
        self.session.execute(delete(DocumentIssue).where(DocumentIssue.document_id == document.id))
        self.session.execute(delete(DocumentFieldCandidate).where(DocumentFieldCandidate.document_id == document.id))
        self.session.flush()
        pages = [
            ExtractedPage(
                page_number=page.page_number,
                text=page.text,
                blocks=page.blocks,
                extraction_method=page.extraction_method,
            )
            for page in document.pages
        ]
        extractor = self.invoice_extractor if document.document_type == "INVOICE" else self.bill_of_lading_extractor
        candidates = extractor.extract(pages)
        for extracted in candidates:
            self.session.add(self._candidate_model(document.id, extracted))
        document.extraction_version = extractor.version
        document.field_count = len(candidates)
        self.session.flush()
        self.session.expire(document, ["candidates", "issues"])

    def _validate_bill_of_lading(self, document: SourceDocument) -> list[ValidationFinding]:
        candidates = self._candidate_map(document)
        document_candidates = {
            field: candidate
            for (group_type, group_index, field), candidate in candidates.items()
            if group_type == "document" and group_index == 0
        }
        self._match_party(document_candidates, "shipper", Supplier)
        self._match_party(document_candidates, "consignee", Customer)
        ports = {
            field: self._match_port(candidates.get(("document", 0, field)))
            for field in ("port_of_loading", "port_of_discharge")
        }
        vessel_id = self._match_vessel(candidates)
        voyage_id = self._match_voyage(candidates, vessel_id)
        shipment_id, shipment_conflicts = self._match_bill_shipment(document, ports, voyage_id)
        canonical_conflicts = shipment_conflicts + self._bill_canonical_conflicts(
            document, shipment_id, ports, voyage_id
        )
        values = self._values(document)
        containers = self._container_values(document)
        findings = validate_bill_of_lading_candidates(
            values,
            containers,
            candidate_statuses=[
                (candidate.field_name, candidate.group_type, candidate.group_index, candidate.status)
                for candidate in document.candidates
            ],
            duplicate=self._existing_bill_of_lading(values) is not None,
            shipment_resolution="matched" if shipment_id else "unresolved",
            canonical_conflicts=canonical_conflicts,
            weight_tolerance=Decimal(settings.document_weight_tolerance),
        )
        for field in ("port_of_loading", "port_of_discharge"):
            candidate = candidates.get(("document", 0, field))
            if candidate and candidate.normalized_value and not candidate.matched_entity_id:
                findings.append(ValidationFinding(field, "WARNING", "NEW_PORT_CANDIDATE", "No canonical port matched exactly; approval will allow creation from the reviewed port text."))
        vessel = candidates.get(("document", 0, "vessel_name"))
        if vessel and vessel.normalized_value and not vessel.matched_entity_id:
            findings.append(ValidationFinding("vessel_name", "WARNING", "NEW_VESSEL_CANDIDATE", "No canonical vessel matched exactly; approval will allow creation from the reviewed vessel identity."))
        voyage = candidates.get(("document", 0, "voyage_number"))
        if voyage and voyage.normalized_value and not voyage.matched_entity_id:
            findings.append(ValidationFinding("voyage_number", "WARNING", "NEW_VOYAGE_CANDIDATE", "No canonical voyage matched the vessel and voyage number; approval will allow creation."))
        for field in ("shipper_name", "consignee_name"):
            candidate = candidates.get(("document", 0, field))
            if candidate and candidate.normalized_value and not candidate.matched_entity_id:
                findings.append(ValidationFinding(field, "INFO", "PARTY_TEXT_UNRESOLVED", "Party text is retained, but no canonical party was matched exactly."))
        return findings

    def _match_port(self, candidate: DocumentFieldCandidate | None) -> uuid.UUID | None:
        if candidate is None or not candidate.normalized_value:
            return None
        candidate.matched_entity_type = None
        candidate.matched_entity_id = None
        candidate.match_method = None
        candidate.match_confidence = None
        value = str(candidate.normalized_value).strip()
        compact = re.sub(r"[^A-Z0-9]", "", value.upper())
        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}", compact):
            port = self.session.scalar(
                select(Port).where(Port.company_id == self.company_id, func.upper(Port.unlocode) == compact)
            )
            if port:
                self._set_entity_match(candidate, "port", port.id, "exact_unlocode", 1.0)
                return port.id
        ports = list(self.session.scalars(select(Port).where(Port.company_id == self.company_id).limit(500)).all())
        exact = [port for port in ports if self._name(port.name) == self._name(value)]
        if len(exact) == 1:
            self._set_entity_match(candidate, "port", exact[0].id, "exact_name", 0.98)
            return exact[0].id
        candidate.matched_entity_type = "new_port"
        candidate.match_method = "new_port_candidate"
        candidate.match_confidence = 0.90
        return None

    def _match_vessel(self, candidates: dict[tuple[str, int, str], DocumentFieldCandidate]) -> uuid.UUID | None:
        name_candidate = candidates.get(("document", 0, "vessel_name"))
        if name_candidate is None or not name_candidate.normalized_value:
            return None
        name_candidate.matched_entity_type = None
        name_candidate.matched_entity_id = None
        name_candidate.match_method = None
        name_candidate.match_confidence = None
        imo = self._candidate_value(candidates.get(("document", 0, "vessel_imo_number")))
        vessels = list(self.session.scalars(select(Vessel).where(Vessel.company_id == self.company_id).limit(500)).all())
        if imo:
            exact_imo = [vessel for vessel in vessels if vessel.imo_number and self._identifier(vessel.imo_number) == self._identifier(imo)]
            if len(exact_imo) == 1:
                self._set_entity_match(name_candidate, "vessel", exact_imo[0].id, "exact_imo", 1.0)
                return exact_imo[0].id
        exact_name = [vessel for vessel in vessels if self._name(vessel.name) == self._name(str(name_candidate.normalized_value))]
        if len(exact_name) == 1:
            self._set_entity_match(name_candidate, "vessel", exact_name[0].id, "exact_name", 0.98)
            return exact_name[0].id
        name_candidate.matched_entity_type = "new_vessel"
        name_candidate.match_method = "new_vessel_candidate"
        name_candidate.match_confidence = 0.90
        return None

    def _match_voyage(
        self,
        candidates: dict[tuple[str, int, str], DocumentFieldCandidate],
        vessel_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        candidate = candidates.get(("document", 0, "voyage_number"))
        if candidate is None or not candidate.normalized_value:
            return None
        candidate.matched_entity_type = None
        candidate.matched_entity_id = None
        candidate.match_method = None
        candidate.match_confidence = None
        if vessel_id:
            voyages = list(
                self.session.scalars(
                    select(Voyage).where(Voyage.company_id == self.company_id, Voyage.vessel_id == vessel_id)
                ).all()
            )
            exact = [voyage for voyage in voyages if self._identifier(voyage.voyage_number) == self._identifier(str(candidate.normalized_value))]
            if len(exact) == 1:
                self._set_entity_match(candidate, "voyage", exact[0].id, "exact_vessel_and_voyage", 1.0)
                return exact[0].id
        candidate.matched_entity_type = "new_voyage"
        candidate.match_method = "new_voyage_candidate"
        candidate.match_confidence = 0.88
        return None

    def _match_bill_shipment(
        self,
        document: SourceDocument,
        ports: dict[str, uuid.UUID | None],
        voyage_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID | None, list[str]]:
        candidates = self._candidate_map(document)
        matched: set[uuid.UUID] = set()
        for field, column in (("shipment_reference", Shipment.external_reference), ("booking_reference", Shipment.booking_reference)):
            candidate = candidates.get(("document", 0, field))
            if candidate and candidate.normalized_value:
                shipment = self.session.scalar(
                    select(Shipment).where(Shipment.company_id == self.company_id, column == str(candidate.normalized_value))
                )
                if shipment:
                    self._set_entity_match(candidate, "shipment", shipment.id, "exact_identifier", 1.0)
                    matched.add(shipment.id)
        bill_number = self._candidate_value(candidates.get(("document", 0, "bill_of_lading_number")))
        if bill_number:
            bill = self.session.scalar(
                select(BillOfLading).where(BillOfLading.company_id == self.company_id, func.upper(BillOfLading.number) == bill_number.upper())
            )
            if bill:
                self._set_entity_match(candidates[("document", 0, "bill_of_lading_number")], "shipment", bill.shipment_id, "exact_bill_of_lading", 1.0)
                matched.add(bill.shipment_id)
        for group in self._container_values(document):
            if not (voyage_id and ports.get("port_of_loading") and ports.get("port_of_discharge")):
                continue
            number = group.get("container_number")
            if not number:
                continue
            shipments = list(
                self.session.scalars(
                    select(Shipment)
                    .join(Container, Container.shipment_id == Shipment.id)
                    .where(Container.company_id == self.company_id, Container.container_number == str(number))
                    .distinct()
                    .limit(2)
                ).all()
            )
            compatible = [
                shipment for shipment in shipments
                if (not voyage_id or shipment.voyage_id == voyage_id)
                and (not ports.get("port_of_loading") or shipment.origin_port_id == ports["port_of_loading"])
                and (not ports.get("port_of_discharge") or shipment.destination_port_id == ports["port_of_discharge"])
            ]
            if len(compatible) == 1:
                candidate = candidates.get(("container", int(group["_group_index"]), "container_number"))
                if candidate:
                    self._set_entity_match(candidate, "shipment", compatible[0].id, "exact_container_and_transport", 0.96)
                matched.add(compatible[0].id)
        if not matched and voyage_id and ports.get("port_of_loading") and ports.get("port_of_discharge"):
            shipments = list(
                self.session.scalars(
                    select(Shipment).where(
                        Shipment.company_id == self.company_id,
                        Shipment.voyage_id == voyage_id,
                        Shipment.origin_port_id == ports["port_of_loading"],
                        Shipment.destination_port_id == ports["port_of_discharge"],
                    ).limit(2)
                ).all()
            )
            if len(shipments) == 1:
                matched.add(shipments[0].id)
        if len(matched) > 1:
            return None, ["Extracted exact references resolve to different canonical shipments."]
        return (next(iter(matched)) if matched else None), []

    def _bill_canonical_conflicts(
        self,
        document: SourceDocument,
        shipment_id: uuid.UUID | None,
        ports: dict[str, uuid.UUID | None],
        voyage_id: uuid.UUID | None,
    ) -> list[str]:
        if shipment_id is None:
            return []
        shipment = self.session.scalar(select(Shipment).where(Shipment.id == shipment_id, Shipment.company_id == self.company_id))
        if shipment is None:
            return []
        conflicts: list[str] = []
        if shipment.voyage_id and voyage_id and shipment.voyage_id != voyage_id:
            conflicts.append("The extracted vessel/voyage conflicts with the matched shipment's trusted voyage.")
        if shipment.origin_port_id and ports.get("port_of_loading") and shipment.origin_port_id != ports["port_of_loading"]:
            conflicts.append("The extracted port of loading conflicts with the matched shipment.")
        if shipment.destination_port_id and ports.get("port_of_discharge") and shipment.destination_port_id != ports["port_of_discharge"]:
            conflicts.append("The extracted port of discharge conflicts with the matched shipment.")
        values = self._values(document)
        if shipment.gross_weight is not None and values.get("total_gross_weight") is not None:
            if abs(Decimal(shipment.gross_weight) - Decimal(str(values["total_gross_weight"]))) > Decimal(settings.document_weight_tolerance):
                conflicts.append("The extracted total gross weight conflicts with the matched shipment's trusted weight.")
        for container in self._container_values(document):
            existing = self.session.scalar(
                select(Container).where(
                    Container.company_id == self.company_id,
                    Container.shipment_id == shipment.id,
                    Container.container_number == str(container.get("container_number")),
                )
            )
            if existing and existing.size_type and container.get("container_size_type") and existing.size_type != container["container_size_type"]:
                conflicts.append(f"Container {existing.container_number} size/type conflicts with the matched shipment occurrence.")
            if existing and existing.gross_weight is not None and container.get("gross_weight") is not None:
                if abs(Decimal(existing.gross_weight) - Decimal(str(container["gross_weight"]))) > Decimal(settings.document_weight_tolerance):
                    conflicts.append(f"Container {existing.container_number} weight conflicts with the matched shipment occurrence.")
        return conflicts

    def _commit_bill_of_lading(self, document: SourceDocument) -> tuple[SourceDocument, BillOfLading]:
        values = self._values(document)
        duplicate = self._existing_bill_of_lading(values)
        if duplicate:
            raise DocumentStateError("A canonical Bill of Lading with this identity already exists.")
        try:
            candidates = self._candidate_map(document)
            document_candidates = {
                field: candidate
                for (group_type, group_index, field), candidate in candidates.items()
                if group_type == "document" and group_index == 0
            }
            self._match_party(document_candidates, "shipper", Supplier)
            self._match_party(document_candidates, "consignee", Customer)
            port_ids = {
                field: self._match_port(candidates.get(("document", 0, field)))
                for field in ("port_of_loading", "port_of_discharge")
            }
            vessel_id = self._match_vessel(candidates)
            voyage_id = self._match_voyage(candidates, vessel_id)
            shipment_id, match_conflicts = self._match_bill_shipment(document, port_ids, voyage_id)
            conflicts = match_conflicts + self._bill_canonical_conflicts(document, shipment_id, port_ids, voyage_id)
            if conflicts:
                raise DocumentStateError("Canonical conflicts must be resolved before commit.")

            loading_port = self._resolve_or_create_port(candidates.get(("document", 0, "port_of_loading")), port_ids["port_of_loading"])
            discharge_port = self._resolve_or_create_port(candidates.get(("document", 0, "port_of_discharge")), port_ids["port_of_discharge"])
            vessel = self._resolve_or_create_vessel(candidates, vessel_id)
            voyage = self._resolve_or_create_voyage(candidates, vessel, voyage_id)
            if shipment_id:
                shipment = self.session.scalar(
                    select(Shipment).where(Shipment.id == shipment_id, Shipment.company_id == self.company_id)
                )
                if shipment is None:
                    raise DocumentStateError("Matched shipment is no longer available.")
            else:
                shipment_reference = values.get("shipment_reference") or f"BL-{values['bill_of_lading_number']}"
                existing_reference = self.session.scalar(
                    select(Shipment).where(
                        Shipment.company_id == self.company_id,
                        Shipment.external_reference == str(shipment_reference),
                    )
                )
                if existing_reference:
                    raise DocumentStateError("Shipment reference became ambiguous during commit.")
                consignee = candidates.get(("document", 0, "consignee_name"))
                shipment = Shipment(
                    company_id=self.company_id,
                    customer_id=consignee.matched_entity_id if consignee and consignee.matched_entity_type == "consignee" else None,
                    voyage_id=voyage.id,
                    origin_port_id=loading_port.id,
                    destination_port_id=discharge_port.id,
                    import_job_id=None,
                    source_row_number=None,
                    external_reference=str(shipment_reference),
                    booking_reference=str(values["booking_reference"]) if values.get("booking_reference") else None,
                    source_system_reference=None,
                    etd=None,
                    eta=None,
                    status="open",
                    gross_weight=Decimal(str(values["total_gross_weight"])) if values.get("total_gross_weight") is not None else None,
                    revenue=None,
                    currency=None,
                )
                self.session.add(shipment)
                self.session.flush()

            shipper = candidates.get(("document", 0, "shipper_name"))
            consignee = candidates.get(("document", 0, "consignee_name"))
            bill = BillOfLading(
                company_id=self.company_id,
                shipment_id=shipment.id,
                source_document_id=document.id,
                shipper_supplier_id=shipper.matched_entity_id if shipper and shipper.matched_entity_type == "shipper" else None,
                consignee_customer_id=consignee.matched_entity_id if consignee and consignee.matched_entity_type == "consignee" else None,
                number=str(values["bill_of_lading_number"]),
                issue_date=date.fromisoformat(str(values["issue_date"])) if values.get("issue_date") else None,
                carrier=str(values["carrier_name"]) if values.get("carrier_name") else None,
                shipper=str(values["shipper_name"]) if values.get("shipper_name") else None,
                consignee=str(values["consignee_name"]) if values.get("consignee_name") else None,
                notify_party=str(values["notify_party_name"]) if values.get("notify_party_name") else None,
                references=" | ".join(
                    str(values[field]) for field in ("shipment_reference", "booking_reference") if values.get(field)
                ) or None,
                description_of_goods=str(values["description_of_goods"]) if values.get("description_of_goods") else None,
                total_packages=int(str(values["total_packages"])) if values.get("total_packages") is not None else None,
                total_gross_weight=Decimal(str(values["total_gross_weight"])) if values.get("total_gross_weight") is not None else None,
                measurement=Decimal(str(values["measurement"])) if values.get("measurement") is not None else None,
                measurement_unit=str(values["measurement_unit"]) if values.get("measurement_unit") else None,
            )
            self.session.add(bill)
            self.session.flush()

            for container_values in self._container_values(document):
                number = str(container_values["container_number"])
                existing = self.session.scalar(
                    select(Container).where(
                        Container.company_id == self.company_id,
                        Container.shipment_id == shipment.id,
                        Container.container_number == number,
                    )
                )
                if existing:
                    continue
                size_type = str(container_values["container_size_type"]) if container_values.get("container_size_type") else None
                self.session.add(
                    Container(
                        company_id=self.company_id,
                        shipment_id=shipment.id,
                        source_document_id=document.id,
                        source_candidate_group=f"container:{container_values['_group_index']}",
                        container_number=number,
                        size_type=size_type,
                        seal_number=str(container_values["seal_number"]) if container_values.get("seal_number") else None,
                        package_count=int(str(container_values["package_count"])) if container_values.get("package_count") is not None else None,
                        package_type=str(container_values["package_type"]) if container_values.get("package_type") else None,
                        teu=Decimal(derive_teu(size_type)) if derive_teu(size_type) else None,
                        gross_weight=Decimal(str(container_values["gross_weight"])) if container_values.get("gross_weight") is not None else None,
                        status="active",
                    )
                )
            document.committed_at = datetime.now(UTC)
            self._transition(document, "committed")
            self.session.commit()
            logger.info("document_commit_completed", extra={**self._log_context(document), "bill_of_lading_id": str(bill.id)})
            return document, bill
        except DocumentStateError:
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            logger.exception("bill_of_lading_commit_failed", extra=self._log_context(document))
            raise DocumentStateError("Bill of Lading commit failed transactionally.") from exc

    def _resolve_or_create_port(
        self, candidate: DocumentFieldCandidate | None, matched_id: uuid.UUID | None
    ) -> Port:
        if matched_id:
            port = self.session.scalar(select(Port).where(Port.id == matched_id, Port.company_id == self.company_id))
            if port:
                return port
        if candidate is None or not candidate.normalized_value:
            raise DocumentStateError("Required port is unresolved.")
        value = str(candidate.normalized_value)
        compact = re.sub(r"[^A-Z0-9]", "", value.upper())
        port = Port(
            company_id=self.company_id,
            unlocode=compact if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}", compact) else None,
            name=value,
            country_code=compact[:2] if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}", compact) else None,
        )
        self.session.add(port)
        self.session.flush()
        return port

    def _resolve_or_create_vessel(
        self,
        candidates: dict[tuple[str, int, str], DocumentFieldCandidate],
        matched_id: uuid.UUID | None,
    ) -> Vessel:
        if matched_id:
            vessel = self.session.scalar(select(Vessel).where(Vessel.id == matched_id, Vessel.company_id == self.company_id))
            if vessel:
                return vessel
        candidate = candidates.get(("document", 0, "vessel_name"))
        if candidate is None or not candidate.normalized_value:
            raise DocumentStateError("Required vessel is unresolved.")
        imo = self._candidate_value(candidates.get(("document", 0, "vessel_imo_number")))
        vessel = Vessel(company_id=self.company_id, name=str(candidate.normalized_value), imo_number=imo)
        self.session.add(vessel)
        self.session.flush()
        return vessel

    def _resolve_or_create_voyage(
        self,
        candidates: dict[tuple[str, int, str], DocumentFieldCandidate],
        vessel: Vessel,
        matched_id: uuid.UUID | None,
    ) -> Voyage:
        if matched_id:
            voyage = self.session.scalar(select(Voyage).where(Voyage.id == matched_id, Voyage.company_id == self.company_id))
            if voyage:
                return voyage
        candidate = candidates.get(("document", 0, "voyage_number"))
        if candidate is None or not candidate.normalized_value:
            raise DocumentStateError("Required voyage is unresolved.")
        existing = self.session.scalar(
            select(Voyage).where(
                Voyage.company_id == self.company_id,
                Voyage.vessel_id == vessel.id,
                Voyage.voyage_number == str(candidate.normalized_value),
            )
        )
        if existing:
            return existing
        voyage = Voyage(
            company_id=self.company_id,
            vessel_id=vessel.id,
            voyage_number=str(candidate.normalized_value),
            departure_date=None,
            arrival_date=None,
        )
        self.session.add(voyage)
        self.session.flush()
        return voyage

    def _existing_bill_of_lading(self, values: dict[str, object]) -> BillOfLading | None:
        number = values.get("bill_of_lading_number")
        if not number:
            return None
        return self.session.scalar(
            select(BillOfLading).where(
                BillOfLading.company_id == self.company_id,
                func.upper(BillOfLading.number) == str(number).upper(),
            )
        )

    def _derive_direction(self, document: SourceDocument) -> None:
        candidates = {candidate.field_name: candidate for candidate in document.candidates}
        existing = candidates.get("direction")
        if existing and existing.extraction_method == "user_corrected":
            return
        company = self.session.scalar(select(Company).where(Company.id == self.company_id))
        supplier_is_company = self._party_is_company(candidates, "supplier", company)
        customer_is_company = self._party_is_company(candidates, "customer", company)
        direction = None
        evidence_candidate = None
        if customer_is_company and not supplier_is_company:
            direction = "payable"
            evidence_candidate = candidates.get("customer_name")
        elif supplier_is_company and not customer_is_company:
            direction = "receivable"
            evidence_candidate = candidates.get("supplier_name")
        if existing is None:
            existing = DocumentFieldCandidate(
                document_id=document.id,
                field_name="direction",
                raw_value=None,
                system_normalized_value=direction,
                normalized_value=direction,
                confidence=0.98 if direction else 0,
                extraction_method="company_identity_match",
                page_number=evidence_candidate.page_number if evidence_candidate else None,
                evidence=evidence_candidate.evidence if evidence_candidate else None,
                status="ready" if direction else "error",
            )
            self.session.add(existing)
            self.session.flush()
        else:
            existing.system_normalized_value = direction
            existing.normalized_value = direction
            existing.confidence = 0.98 if direction else 0
            existing.status = "ready" if direction else "error"

    def _match_parties(self, document: SourceDocument) -> str:
        candidates = {candidate.field_name: candidate for candidate in document.candidates}
        self._match_party(candidates, "supplier", Supplier)
        self._match_party(candidates, "customer", Customer)
        direction = candidates.get("direction").normalized_value if candidates.get("direction") else None
        prefix = "supplier" if direction == "payable" else "customer" if direction == "receivable" else None
        if prefix is None:
            return "unresolved"
        name_candidate = candidates.get(f"{prefix}_name")
        if not name_candidate or not name_candidate.normalized_value:
            return "unresolved"
        if name_candidate.matched_entity_id:
            return "matched"
        has_identifier = bool(
            (candidates.get(f"{prefix}_vat_number") and candidates[f"{prefix}_vat_number"].normalized_value)
            or (candidates.get(f"{prefix}_registration_number") and candidates[f"{prefix}_registration_number"].normalized_value)
        )
        if has_identifier:
            name_candidate.matched_entity_type = f"new_{prefix}"
            name_candidate.match_method = "new_party_candidate"
            name_candidate.match_confidence = 0.85
            return "new_candidate"
        return "unresolved"

    def _match_party(self, candidates: dict[str, DocumentFieldCandidate], prefix: str, model: type[PartyModel]) -> None:
        name_candidate = candidates.get(f"{prefix}_name")
        if not name_candidate or not name_candidate.normalized_value:
            return
        name_candidate.matched_entity_type = None
        name_candidate.matched_entity_id = None
        name_candidate.match_method = None
        name_candidate.match_confidence = None
        vat = self._candidate_value(candidates.get(f"{prefix}_vat_number"))
        registration = self._candidate_value(candidates.get(f"{prefix}_registration_number"))
        parties = list(self.session.scalars(select(model).where(model.company_id == self.company_id).limit(200)).all())
        for party in parties:
            if vat and party.vat_number and self._identifier(vat) == self._identifier(party.vat_number):
                return self._set_match(name_candidate, prefix, party.id, "exact_vat", 1.0)
        for party in parties:
            if registration and party.registration_number and self._identifier(registration) == self._identifier(party.registration_number):
                return self._set_match(name_candidate, prefix, party.id, "exact_registration", 1.0)
        for party in parties:
            if registration and party.external_reference and self._identifier(registration) == self._identifier(party.external_reference):
                return self._set_match(name_candidate, prefix, party.id, "exact_external_reference", 0.99)
        normalized_name = self._name(str(name_candidate.normalized_value))
        for party in parties:
            if self._name(party.name) == normalized_name:
                return self._set_match(name_candidate, prefix, party.id, "exact_name", 0.96)
        ranked = sorted(
            ((SequenceMatcher(None, normalized_name, self._name(party.name)).ratio(), party) for party in parties),
            key=lambda item: item[0],
            reverse=True,
        )
        if ranked and ranked[0][0] >= 0.94 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
            self._set_match(name_candidate, prefix, ranked[0][1].id, "conservative_fuzzy_name", round(ranked[0][0], 2))

    def _match_references(self, document: SourceDocument) -> bool:
        matched: set[uuid.UUID] = set()
        for candidate in document.candidates:
            candidate.matched_entity_type = candidate.matched_entity_type if candidate.field_name.endswith("_name") else None
            if candidate.field_name not in {"shipment_reference", "booking_reference", "bill_of_lading_reference"}:
                continue
            candidate.matched_entity_id = None
            candidate.match_method = None
            candidate.match_confidence = None
            value = str(candidate.normalized_value or "").strip()
            if not value:
                continue
            shipment = None
            if candidate.field_name == "shipment_reference":
                shipment = self.session.scalar(
                    select(Shipment).where(Shipment.company_id == self.company_id, Shipment.external_reference == value)
                )
            elif candidate.field_name == "booking_reference":
                shipment = self.session.scalar(
                    select(Shipment).where(Shipment.company_id == self.company_id, Shipment.booking_reference == value)
                )
            else:
                shipment = self.session.scalar(
                    select(Shipment)
                    .join(BillOfLading, BillOfLading.shipment_id == Shipment.id)
                    .where(BillOfLading.company_id == self.company_id, BillOfLading.number == value)
                )
            if shipment:
                candidate.matched_entity_type = "shipment"
                candidate.matched_entity_id = shipment.id
                candidate.match_method = "exact_identifier"
                candidate.match_confidence = 1.0
                matched.add(shipment.id)
        return len(matched) > 1

    def _invoice_findings(
        self,
        document: SourceDocument,
        values: dict[str, object],
        party_resolution: str,
        reference_conflict: bool,
    ) -> list[ValidationFinding]:
        findings = validate_invoice_candidates(
            values,
            candidate_statuses={candidate.field_name: candidate.status for candidate in document.candidates},
            party_resolution=party_resolution,
            duplicate=self._existing_invoice(values) is not None,
            reference_conflict=reference_conflict,
            tolerance=Decimal(settings.document_amount_tolerance),
        )
        for candidate in document.candidates:
            if candidate.field_name in {"shipment_reference", "booking_reference", "bill_of_lading_reference"} and candidate.normalized_value and not candidate.matched_entity_id:
                findings.append(ValidationFinding(candidate.field_name, "WARNING", "UNMATCHED_REFERENCE", "The extracted operational reference did not match a canonical shipment."))
        return findings

    def _existing_invoice(self, values: dict[str, object]) -> Invoice | None:
        number = values.get("invoice_number")
        direction = values.get("direction")
        if not number or not direction:
            return None
        return self.session.scalar(
            select(Invoice).where(
                Invoice.company_id == self.company_id,
                Invoice.invoice_number == str(number),
                Invoice.direction == str(direction),
            )
        )

    def _resolve_or_create_party(
        self, document: SourceDocument, values: dict[str, object], direction: str
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        prefix = "supplier" if direction == "payable" else "customer"
        model = Supplier if prefix == "supplier" else Customer
        candidates = {candidate.field_name: candidate for candidate in document.candidates}
        name_candidate = candidates.get(f"{prefix}_name")
        if not name_candidate or not name_candidate.normalized_value:
            raise DocumentStateError("The external invoice party is unresolved.")
        if name_candidate.matched_entity_id:
            return (None, name_candidate.matched_entity_id) if prefix == "supplier" else (name_candidate.matched_entity_id, None)
        vat = self._candidate_value(candidates.get(f"{prefix}_vat_number"))
        registration = self._candidate_value(candidates.get(f"{prefix}_registration_number"))
        if not vat and not registration:
            raise DocumentStateError("A new party requires a VAT or registration identifier.")
        query = select(model).where(model.company_id == self.company_id)
        if vat and registration:
            query = query.where(or_(model.vat_number == vat, model.registration_number == registration))
        elif vat:
            query = query.where(model.vat_number == vat)
        else:
            query = query.where(model.registration_number == registration)
        existing = self.session.scalar(query.limit(1))
        if existing:
            return (None, existing.id) if prefix == "supplier" else (existing.id, None)
        party = model(
            company_id=self.company_id,
            name=str(name_candidate.normalized_value),
            vat_number=vat,
            registration_number=registration,
            currency=str(values.get("currency")) if values.get("currency") else None,
        )
        self.session.add(party)
        self.session.flush()
        return (None, party.id) if prefix == "supplier" else (party.id, None)

    def _matched_shipment_id(self, document: SourceDocument) -> uuid.UUID | None:
        ids = {
            candidate.matched_entity_id
            for candidate in document.candidates
            if candidate.matched_entity_type == "shipment" and candidate.matched_entity_id
        }
        return next(iter(ids)) if len(ids) == 1 else None

    def _party_is_company(
        self, candidates: dict[str, DocumentFieldCandidate], prefix: str, company: Company | None
    ) -> bool:
        if company is None:
            return False
        vat = self._candidate_value(candidates.get(f"{prefix}_vat_number"))
        registration = self._candidate_value(candidates.get(f"{prefix}_registration_number"))
        name = self._candidate_value(candidates.get(f"{prefix}_name"))
        return bool(
            (vat and company.vat_number and self._identifier(vat) == self._identifier(company.vat_number))
            or (registration and company.registration_number and self._identifier(registration) == self._identifier(company.registration_number))
            or (name and self._name(name) == self._name(company.name))
        )

    def _replace_issues(self, document: SourceDocument, findings: list[ValidationFinding]) -> None:
        self.session.execute(delete(DocumentIssue).where(DocumentIssue.document_id == document.id))
        candidates = self._candidate_map(document)
        for finding in findings:
            candidate = candidates.get((finding.group_type, finding.group_index, finding.field or ""))
            issue_field = finding.field
            if finding.group_type != "document" and finding.field:
                issue_field = f"{finding.group_type}s[{finding.group_index}].{finding.field}"
            self.session.add(
                DocumentIssue(
                    document_id=document.id,
                    field_candidate_id=candidate.id if candidate else None,
                    field=issue_field,
                    severity=finding.severity,
                    code=finding.code,
                    message=finding.message,
                )
            )
        self.session.flush()
        self.session.expire(document, ["issues"])

    def _store_pages(self, document: SourceDocument, pages) -> None:
        self.session.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        for page in pages:
            self.session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                    blocks=page.blocks,
                    extraction_method=page.extraction_method,
                    char_count=len(page.text),
                )
            )
        self.session.flush()
        self.session.expire(document, ["pages"])

    def _fail(self, document: SourceDocument, code: str, message: str) -> SourceDocument:
        self._replace_issues(document, [ValidationFinding(None, "ERROR", code, message)])
        if document.status != "failed":
            self._transition(document, "failed")
        self._refresh_counts(document)
        self.session.commit()
        logger.warning("document_processing_failed", extra={**self._log_context(document), "code": code})
        return document

    def _refresh_counts(self, document: SourceDocument) -> None:
        document.field_count = len(document.candidates)
        document.review_count = sum(issue.severity == "WARNING" for issue in document.issues)
        document.error_count = sum(issue.severity == "ERROR" for issue in document.issues)

    @staticmethod
    def _candidate_model(document_id: uuid.UUID, extracted: ExtractedCandidate) -> DocumentFieldCandidate:
        status = "error" if extracted.normalized_value is None else (
            "ready" if extracted.confidence >= settings.document_high_confidence_threshold else "review"
        )
        return DocumentFieldCandidate(
            document_id=document_id,
            field_name=extracted.field_name,
            group_type=extracted.group_type,
            group_index=extracted.group_index,
            raw_value=extracted.raw_value,
            system_normalized_value=extracted.normalized_value,
            normalized_value=extracted.normalized_value,
            confidence=extracted.confidence,
            extraction_method=extracted.extraction_method,
            page_number=extracted.page_number,
            evidence=extracted.evidence,
            bounding_box=extracted.bounding_box,
            status=status,
        )

    @staticmethod
    def _values(document: SourceDocument) -> dict[str, object]:
        return {
            candidate.field_name: candidate.normalized_value
            for candidate in document.candidates
            if candidate.group_type == "document"
        }

    @staticmethod
    def _container_values(document: SourceDocument) -> list[dict[str, object]]:
        groups: dict[int, dict[str, object]] = {}
        for candidate in document.candidates:
            if candidate.group_type != "container":
                continue
            groups.setdefault(candidate.group_index, {"_group_index": candidate.group_index})[
                candidate.field_name
            ] = candidate.normalized_value
        return [groups[index] for index in sorted(groups)]

    @staticmethod
    def _candidate_map(
        document: SourceDocument,
    ) -> dict[tuple[str, int, str], DocumentFieldCandidate]:
        return {
            (candidate.group_type, candidate.group_index, candidate.field_name): candidate
            for candidate in document.candidates
        }

    @staticmethod
    def _set_match(candidate, prefix: str, entity_id: uuid.UUID, method: str, confidence: float) -> None:
        candidate.matched_entity_type = prefix
        candidate.matched_entity_id = entity_id
        candidate.match_method = method
        candidate.match_confidence = confidence

    @staticmethod
    def _candidate_value(candidate: DocumentFieldCandidate | None) -> str | None:
        return str(candidate.normalized_value) if candidate and candidate.normalized_value else None

    @staticmethod
    def _identifier(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    @staticmethod
    def _name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    @staticmethod
    def _set_entity_match(
        candidate: DocumentFieldCandidate,
        entity_type: str,
        entity_id: uuid.UUID,
        method: str,
        confidence: float,
    ) -> None:
        candidate.matched_entity_type = entity_type
        candidate.matched_entity_id = entity_id
        candidate.match_method = method
        candidate.match_confidence = confidence

    @staticmethod
    def _document_fields(document_type: str) -> list[str]:
        return INVOICE_FIELDS if document_type == "INVOICE" else BILL_OF_LADING_FIELDS

    @staticmethod
    def _normalize_value(document_type: str, field_name: str, value: Any):
        if document_type == "BILL_OF_LADING":
            return normalize_bill_of_lading_value(field_name, str(value))
        return normalize_invoice_value(field_name, str(value))

    @staticmethod
    def _validate_upload(filename: str, content_type: str | None, content: bytes) -> str:
        safe = Path((filename or "").replace("\\", "/")).name.replace("\x00", "").strip()
        if not safe or Path(safe).suffix.lower() != ".pdf":
            raise DocumentUploadError("UNSUPPORTED_FILE_TYPE", "Choose a .pdf document.")
        if content_type and content_type.lower() not in {"application/pdf", "application/octet-stream"}:
            raise DocumentUploadError("INVALID_CONTENT_TYPE", "The upload content type is not PDF.")
        if not content:
            raise DocumentUploadError("EMPTY_FILE", "The uploaded PDF is empty.")
        if len(content) > settings.document_max_upload_bytes:
            raise DocumentUploadError("FILE_TOO_LARGE", "The PDF exceeds the 20 MB upload limit.", 413)
        if not content.lstrip().startswith(b"%PDF-"):
            raise DocumentUploadError("INVALID_PDF_SIGNATURE", "The upload does not have a valid PDF signature.")
        return safe

    @staticmethod
    def _transition(document: SourceDocument, target: str) -> None:
        if document.status == target:
            return
        if target not in ALLOWED_DOCUMENT_TRANSITIONS.get(document.status, set()):
            raise DocumentStateError(f"Cannot transition document from {document.status} to {target}.")
        document.status = target

    @staticmethod
    def _summary(
        document: SourceDocument,
        counts: dict[str, int],
        invoice: Invoice | None,
        bill_of_lading: BillOfLading | None = None,
    ) -> dict:
        return {
            "document": document,
            "ready_fields": counts.get("ready", 0),
            "review_fields": counts.get("review", 0),
            "error_fields": counts.get("error", 0),
            "canonical_invoice_id": invoice.id if invoice else None,
            "canonical_invoice_number": invoice.invoice_number if invoice else None,
            "canonical_bill_of_lading_id": bill_of_lading.id if bill_of_lading else None,
            "canonical_bill_of_lading_number": bill_of_lading.number if bill_of_lading else None,
        }

    @staticmethod
    def _log_context(document: SourceDocument) -> dict[str, str]:
        return {"document_id": str(document.id), "company_id": str(document.company_id), "status": document.status}
