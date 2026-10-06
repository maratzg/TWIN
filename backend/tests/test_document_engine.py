from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from app.document_engine.classification import DocumentClassifier
from app.document_engine.extractors import InvoiceExtractor
from app.document_engine.normalization import normalize_invoice_value
from app.document_engine.parsers import PDFDocumentError, PDFParser
from app.document_engine.storage import LocalDocumentStorage
from app.document_engine.types import ExtractedPage
from app.document_engine.validation import validate_invoice_candidates


DEMO_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "invoices"


def test_pdf_parser_classifier_and_invoice_extractor() -> None:
    pages = PDFParser().parse((DEMO_DIR / "invoice-a-clean.pdf").read_bytes())

    classification = DocumentClassifier().classify(pages)
    candidates = {item.field_name: item for item in InvoiceExtractor().extract(pages)}

    assert classification.document_type == "INVOICE"
    assert classification.confidence >= 0.75
    assert pages[0].blocks
    assert candidates["invoice_number"].normalized_value == "BFS-2026-0917"
    assert candidates["supplier_vat_number"].normalized_value == "LV40203555111"
    assert candidates["subtotal"].normalized_value == "1000.00"
    assert candidates["vat_amount"].normalized_value == "210.00"
    assert candidates["total_amount"].normalized_value == "1210.00"
    assert candidates["booking_reference"].page_number == 1
    assert "Booking Reference" in candidates["booking_reference"].evidence


def test_european_money_and_date_normalization() -> None:
    pages = PDFParser().parse((DEMO_DIR / "invoice-b-european-format.pdf").read_bytes())
    values = {item.field_name: item.normalized_value for item in InvoiceExtractor().extract(pages)}

    assert values["invoice_date"] == "2026-09-18"
    assert values["subtotal"] == "1250.00"
    assert values["vat_amount"] == "262.50"
    assert values["total_amount"] == "1512.50"
    assert normalize_invoice_value("supplier_vat_number", "LV 4020-3555-111") == "LV40203555111"


def test_corrupt_pdf_and_unknown_classification_fail_safely() -> None:
    with pytest.raises(PDFDocumentError) as caught:
        PDFParser().parse(b"%PDF-corrupt")
    assert caught.value.code == "CORRUPT_PDF"

    result = DocumentClassifier().classify(
        [ExtractedPage(page_number=1, text="Packing list\nContainer MSKU1234567")]
    )
    assert result.document_type == "UNKNOWN"


def test_encrypted_pdf_is_rejected_with_structured_error() -> None:
    reader = PdfReader(DEMO_DIR / "invoice-a-clean.pdf")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    stream = BytesIO()
    writer.write(stream)

    with pytest.raises(PDFDocumentError) as caught:
        PDFParser().parse(stream.getvalue())
    assert caught.value.code == "ENCRYPTED_PDF"


def test_invoice_arithmetic_validation_is_tolerance_aware() -> None:
    values = {
        "invoice_number": "INV-1",
        "invoice_date": "2026-09-24",
        "direction": "payable",
        "currency": "EUR",
        "subtotal": "100.00",
        "vat_amount": "21.00",
        "total_amount": "121.03",
    }
    findings = validate_invoice_candidates(
        values,
        candidate_statuses={},
        party_resolution="matched",
        duplicate=False,
        reference_conflict=False,
        tolerance=Decimal("0.02"),
    )

    assert {finding.code for finding in findings} == {"ARITHMETIC_MISMATCH"}


def test_local_storage_blocks_path_traversal(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.read("../../outside.pdf")
    with pytest.raises(ValueError):
        storage.read("/tmp/outside.pdf")
