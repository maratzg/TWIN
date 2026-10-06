from decimal import Decimal
from pathlib import Path

from app.document_engine.classification import DocumentClassifier
from app.document_engine.extractors import BillOfLadingExtractor, InvoiceExtractor
from app.document_engine.normalization import (
    derive_teu,
    normalize_bill_of_lading_value,
    normalize_container_size_type,
    normalize_weight_kg,
)
from app.document_engine.parsers import PDFParser
from app.document_engine.types import ExtractedPage
from app.document_engine.validation import iso6346_status, validate_bill_of_lading_candidates


BILL_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "bills-of-lading"
INVOICE_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "invoices"


def test_bill_of_lading_classification_does_not_reduce_invoice_separation() -> None:
    bill_pages = PDFParser().parse((BILL_DIR / "bill-of-lading-a-clean-single-container.pdf").read_bytes())
    invoice_pages = PDFParser().parse((INVOICE_DIR / "invoice-a-clean.pdf").read_bytes())
    random_logistics = [ExtractedPage(1, "Container MSKU1234565\nDelivery instructions")]

    assert DocumentClassifier().classify(bill_pages).document_type == "BILL_OF_LADING"
    assert DocumentClassifier().classify(invoice_pages).document_type == "INVOICE"
    assert DocumentClassifier().classify(random_logistics).document_type == "UNKNOWN"
    assert InvoiceExtractor().extract(invoice_pages)


def test_bill_of_lading_extracts_parties_transport_ports_and_multiple_containers() -> None:
    pages = PDFParser().parse((BILL_DIR / "bill-of-lading-b-multiple-containers.pdf").read_bytes())
    candidates = BillOfLadingExtractor().extract(pages)
    document = {item.field_name: item.normalized_value for item in candidates if item.group_type == "document"}
    containers: dict[int, dict[str, object]] = {}
    for item in candidates:
        if item.group_type == "container":
            containers.setdefault(item.group_index, {})[item.field_name] = item.normalized_value

    assert document["bill_of_lading_number"] == "BL-RIX-260924-B"
    assert document["shipper_name"] == "Baltic Timber Export SIA"
    assert document["consignee_name"] == "Atlantic Wholesale GmbH"
    assert document["vessel_name"] == "EVER AURORA"
    assert document["voyage_number"] == "EA0924W"
    assert document["port_of_loading"] == "RIGA"
    assert document["port_of_discharge"] == "HAMBURG"
    assert document["total_gross_weight"] == "30400.000"
    assert len(containers) == 3
    assert containers[1] == {
        "container_number": "TEMU7654328",
        "container_size_type": "20GP",
        "seal_number": "SEAL9002",
        "package_count": 80,
        "package_type": "BUNDLES",
        "gross_weight": "8400.000",
    }
    assert next(item for item in candidates if item.group_type == "container").page_number == 1


def test_logistics_normalization_iso_validation_and_teu() -> None:
    assert normalize_bill_of_lading_value("container_number", "msku 123456 5") == "MSKU1234565"
    assert normalize_container_size_type("40 HQ") == "40HC"
    assert normalize_container_size_type("20' GP") == "20GP"
    assert normalize_container_size_type("40") == "40"
    assert normalize_weight_kg("18.400 KGS") == "18400.000"
    assert normalize_weight_kg("18 400 KG") == "18400.000"
    assert normalize_weight_kg("18,400 kg") == "18400.000"
    assert iso6346_status("MSKU1234565") == "check_digit_valid"
    assert iso6346_status("MSKU1234567") == "check_digit_invalid"
    assert iso6346_status("BAD-123") == "structurally_invalid"
    assert derive_teu("20GP") == "1.00"
    assert derive_teu("40HC") == "2.00"
    assert derive_teu("40") is None


def test_bill_validation_detects_check_digit_and_weight_mismatch() -> None:
    findings = validate_bill_of_lading_candidates(
        {
            "bill_of_lading_number": "BL-1",
            "vessel_name": "VESSEL",
            "voyage_number": "V1",
            "port_of_loading": "RIGA",
            "port_of_discharge": "HAMBURG",
            "total_gross_weight": "20000.000",
        },
        [
            {"container_number": "MSKU1234567", "gross_weight": "10000.000"},
            {"container_number": "TEMU7654328", "gross_weight": "8400.000"},
        ],
        candidate_statuses=[],
        duplicate=False,
        shipment_resolution="unresolved",
        canonical_conflicts=[],
        weight_tolerance=Decimal("1.000"),
    )

    assert {finding.code for finding in findings} >= {
        "INVALID_CONTAINER_CHECK_DIGIT",
        "TOTAL_WEIGHT_MISMATCH",
        "NEW_SHIPMENT_CANDIDATE",
    }
