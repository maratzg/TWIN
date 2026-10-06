from pathlib import Path
from io import BytesIO

import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from app.document_engine.storage import LocalDocumentStorage
from app.models import BillOfLading, DocumentCorrection, Invoice, Shipment, Supplier
from app.services.document_service import DocumentService, DocumentStateError, DocumentUploadError


DEMO_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "invoices"


def _service(session, company, tmp_path: Path) -> DocumentService:
    company.name = "Demo Logistics SIA"
    company.registration_number = "40000000000"
    company.vat_number = "LV40000000000"
    session.commit()
    return DocumentService(session, company.id, storage=LocalDocumentStorage(tmp_path))


def test_upload_review_correction_approval_and_idempotent_commit(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    content = (DEMO_DIR / "invoice-d-arithmetic-mismatch.pdf").read_bytes()

    document = service.upload("invoice.pdf", "application/pdf", content)
    assert document.status == "needs_review"
    assert "ARITHMETIC_MISMATCH" in {issue.code for issue in document.issues}
    with pytest.raises(DocumentStateError):
        service.approve(document.id)

    total = next(item for item in document.candidates if item.field_name == "total_amount")
    assert total.system_normalized_value == "1199.00"
    service.correct_field(document.id, "total_amount", "1089.00", reason="Verified against statement")
    document = service.get(document.id)
    total = next(item for item in document.candidates if item.field_name == "total_amount")
    assert total.system_normalized_value == "1199.00"
    assert total.normalized_value == "1089.00"
    assert "ARITHMETIC_MISMATCH" not in {issue.code for issue in document.issues}
    correction = session.scalar(select(DocumentCorrection).where(DocumentCorrection.document_id == document.id))
    assert correction.previous_value == "1199.00"

    service.approve(document.id, "finance-reviewer")
    committed, invoice = service.commit(document.id)
    repeated_document, repeated_invoice = service.commit(document.id)

    assert committed.status == repeated_document.status == "committed"
    assert invoice.id == repeated_invoice.id
    assert invoice.source_document_id == document.id
    assert invoice.direction == "payable"
    assert invoice.total == 1089
    assert session.scalar(select(Supplier).where(Supplier.id == invoice.supplier_id)) is not None
    assert session.scalar(select(Invoice).where(Invoice.source_document_id == document.id)).id == invoice.id


def test_duplicate_invoice_is_blocked_after_first_commit(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    first = service.upload(
        "invoice-a-clean.pdf",
        "application/pdf",
        (DEMO_DIR / "invoice-a-clean.pdf").read_bytes(),
    )
    service.approve(first.id)
    service.commit(first.id)

    duplicate = service.upload(
        "invoice-e-duplicate.pdf",
        "application/pdf",
        (DEMO_DIR / "invoice-e-duplicate.pdf").read_bytes(),
    )
    assert duplicate.status == "needs_review"
    assert "DUPLICATE_INVOICE" in {issue.code for issue in duplicate.issues}
    with pytest.raises(DocumentStateError):
        service.approve(duplicate.id)


def test_tenant_boundary_and_upload_guards(session, companies, tmp_path) -> None:
    first, second = companies
    first_service = _service(session, first, tmp_path / "first")
    second_service = DocumentService(session, second.id, storage=LocalDocumentStorage(tmp_path / "second"))
    document = first_service.upload(
        "invoice-a-clean.pdf",
        "application/pdf",
        (DEMO_DIR / "invoice-a-clean.pdf").read_bytes(),
    )

    with pytest.raises(LookupError):
        second_service.get(document.id)
    with pytest.raises(DocumentUploadError) as wrong_type:
        first_service.upload("invoice.txt", "text/plain", b"not a pdf")
    assert wrong_type.value.code == "UNSUPPORTED_FILE_TYPE"


def test_corrupt_pdf_is_persisted_as_failed_with_structured_issue(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)

    document = service.upload("broken.pdf", "application/pdf", b"%PDF-corrupt")

    assert document.status == "failed"
    assert document.error_count == 1
    assert [(issue.code, issue.severity) for issue in document.issues] == [("CORRUPT_PDF", "ERROR")]


def test_blank_pdf_routes_to_explicit_ocr_required_state(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)

    document = service.upload("scan.pdf", "application/pdf", stream.getvalue())

    assert document.status == "failed"
    assert {issue.code for issue in document.issues} == {"OCR_REQUIRED"}


def test_exact_party_and_operational_references_are_reused(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    supplier = Supplier(
        company_id=company.id,
        external_reference="VENDOR-44",
        name="Baltic Freight Svcs",
        registration_number="40203555111",
        vat_number="LV40203555111",
        country_code="LV",
        currency="EUR",
    )
    shipment = Shipment(
        company_id=company.id,
        customer_id=None,
        voyage_id=None,
        origin_port_id=None,
        destination_port_id=None,
        import_job_id=None,
        source_row_number=None,
        external_reference="SHP-2026-0091",
        booking_reference="BOOK-77821",
        source_system_reference=None,
        etd=None,
        eta=None,
        status="open",
        gross_weight=None,
        revenue=None,
        currency="EUR",
    )
    session.add_all([supplier, shipment])
    session.flush()
    session.add(
        BillOfLading(
            company_id=company.id,
            shipment_id=shipment.id,
            number="BL-RIX-260917",
            issue_date=None,
            carrier=None,
            shipper=None,
            consignee=None,
            notify_party=None,
            references=None,
        )
    )
    session.commit()

    document = service.upload(
        "invoice-a-clean.pdf",
        "application/pdf",
        (DEMO_DIR / "invoice-a-clean.pdf").read_bytes(),
    )
    candidates = {candidate.field_name: candidate for candidate in document.candidates}

    assert candidates["supplier_name"].matched_entity_id == supplier.id
    assert candidates["supplier_name"].match_method == "exact_vat"
    assert candidates["shipment_reference"].matched_entity_id == shipment.id
    assert candidates["booking_reference"].matched_entity_id == shipment.id
    assert candidates["bill_of_lading_reference"].matched_entity_id == shipment.id
    assert "UNMATCHED_REFERENCE" not in {issue.code for issue in document.issues}
    service.approve(document.id)
    _document, invoice = service.commit(document.id)
    assert invoice.supplier_id == supplier.id
    assert invoice.shipment_id == shipment.id
    assert len(session.scalars(select(Supplier).where(Supplier.company_id == company.id)).all()) == 1


def test_unresolved_party_stays_fail_closed(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    document = service.upload(
        "invoice-c-ambiguous.pdf",
        "application/pdf",
        (DEMO_DIR / "invoice-c-ambiguous.pdf").read_bytes(),
    )
    assert document.status == "needs_review"
    assert "PARTY_UNRESOLVED" in {issue.code for issue in document.issues}
    with pytest.raises(DocumentStateError):
        service.approve(document.id)
