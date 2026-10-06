from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.document_engine.storage import LocalDocumentStorage
from app.models import BillOfLading, Container, Customer, Port, Shipment, Supplier, Vessel, Voyage
from app.services.document_service import DocumentService, DocumentStateError


BILL_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "bills-of-lading"


def _service(session, company, tmp_path: Path) -> DocumentService:
    return DocumentService(session, company.id, storage=LocalDocumentStorage(tmp_path))


def _upload(service: DocumentService, filename: str):
    path = BILL_DIR / filename
    return service.upload(path.name, "application/pdf", path.read_bytes())


def test_multi_container_commit_creates_connected_graph_and_provenance(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    document = _upload(service, "bill-of-lading-b-multiple-containers.pdf")

    assert document.document_type == "BILL_OF_LADING"
    assert document.status == "needs_review"
    assert document.error_count == 0
    assert len({item.group_index for item in document.candidates if item.group_type == "container"}) == 3
    service.approve(document.id, "operations-reviewer")
    committed, bill = service.commit(document.id)
    repeated_document, repeated_bill = service.commit(document.id)

    assert committed.status == repeated_document.status == "committed"
    assert bill.id == repeated_bill.id
    assert bill.source_document_id == document.id
    assert bill.shipment.voyage.vessel.name == "EVER AURORA"
    assert bill.shipment.voyage.voyage_number == "EA0924W"
    assert bill.shipment.origin_port.name == "RIGA"
    assert bill.shipment.destination_port.name == "HAMBURG"
    assert len(bill.shipment.containers) == 3
    assert sum(container.teu for container in bill.shipment.containers) == 5
    assert all(container.source_document_id == document.id for container in bill.shipment.containers)
    assert {container.source_candidate_group for container in bill.shipment.containers} == {
        "container:0", "container:1", "container:2"
    }


def test_invalid_container_can_be_corrected_revalidated_and_approved(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    document = _upload(service, "bill-of-lading-d-invalid-check-digit.pdf")
    assert "INVALID_CONTAINER_CHECK_DIGIT" in {issue.code for issue in document.issues}
    with pytest.raises(DocumentStateError):
        service.approve(document.id)

    candidate = next(item for item in document.candidates if item.group_type == "container" and item.field_name == "container_number")
    service.correct_candidate(document.id, candidate.id, "MSKU1234565", reason="Verified against carrier portal")
    document = service.get(document.id)
    candidate = next(item for item in document.candidates if item.id == candidate.id)
    assert candidate.system_normalized_value == "MSKU1234567"
    assert candidate.normalized_value == "MSKU1234565"
    assert "INVALID_CONTAINER_CHECK_DIGIT" not in {issue.code for issue in document.issues}
    service.approve(document.id)
    assert service.get(document.id).status == "approved"


def test_exact_party_port_vessel_voyage_and_shipment_matching(session, companies, tmp_path) -> None:
    company, _other = companies
    supplier = Supplier(company_id=company.id, name="Baltic Timber Export SIA", external_reference=None, registration_number=None, vat_number=None, country_code="LV", currency="EUR")
    customer = Customer(company_id=company.id, name="North Sea Trading BV", external_reference=None, registration_number=None, vat_number=None, country_code="NL", currency="EUR")
    loading = Port(company_id=company.id, unlocode="LVRIX", name="RIGA", country_code="LV")
    discharge = Port(company_id=company.id, unlocode="NLRTM", name="ROTTERDAM", country_code="NL")
    vessel = Vessel(company_id=company.id, name="Ever Aurora", imo_number="9811001")
    session.add_all([supplier, customer, loading, discharge, vessel])
    session.flush()
    voyage = Voyage(company_id=company.id, vessel_id=vessel.id, voyage_number="EA0924W", departure_date=None, arrival_date=None)
    session.add(voyage)
    session.flush()
    shipment = Shipment(company_id=company.id, customer_id=customer.id, voyage_id=voyage.id, origin_port_id=loading.id, destination_port_id=discharge.id, import_job_id=None, source_row_number=None, external_reference="SHP-BL-A-2026", booking_reference="BOOK-A-77821", source_system_reference=None, etd=None, eta=None, status="open", gross_weight=None, revenue=None, currency=None)
    session.add(shipment)
    session.commit()

    service = _service(session, company, tmp_path)
    document = _upload(service, "bill-of-lading-a-clean-single-container.pdf")
    candidates = {(item.group_type, item.group_index, item.field_name): item for item in document.candidates}

    assert candidates[("document", 0, "shipper_name")].matched_entity_id == supplier.id
    assert candidates[("document", 0, "consignee_name")].matched_entity_id == customer.id
    assert candidates[("document", 0, "port_of_loading")].matched_entity_id == loading.id
    assert candidates[("document", 0, "port_of_discharge")].matched_entity_id == discharge.id
    assert candidates[("document", 0, "vessel_name")].matched_entity_id == vessel.id
    assert candidates[("document", 0, "shipment_reference")].matched_entity_id == shipment.id
    assert "CANONICAL_CONFLICT" not in {issue.code for issue in document.issues}
    service.approve(document.id)
    _document, bill = service.commit(document.id)
    assert bill.shipment_id == shipment.id
    assert bill.shipper_supplier_id == supplier.id
    assert bill.consignee_customer_id == customer.id


def test_canonical_conflict_blocks_approval_without_overwrite(session, companies, tmp_path) -> None:
    company, _other = companies
    riga = Port(company_id=company.id, unlocode="LVRIX", name="RIGA", country_code="LV")
    rotterdam = Port(company_id=company.id, unlocode="NLRTM", name="ROTTERDAM", country_code="NL")
    hamburg = Port(company_id=company.id, unlocode="DEHAM", name="HAMBURG", country_code="DE")
    vessel = Vessel(company_id=company.id, name="EVER AURORA", imo_number="9811001")
    session.add_all([riga, rotterdam, hamburg, vessel])
    session.flush()
    voyage = Voyage(company_id=company.id, vessel_id=vessel.id, voyage_number="EA0924W", departure_date=None, arrival_date=None)
    session.add(voyage)
    session.flush()
    shipment = Shipment(company_id=company.id, customer_id=None, voyage_id=voyage.id, origin_port_id=riga.id, destination_port_id=hamburg.id, import_job_id=None, source_row_number=None, external_reference="SHP-BL-A-2026", booking_reference=None, source_system_reference=None, etd=None, eta=None, status="trusted", gross_weight=None, revenue=None, currency=None)
    session.add(shipment)
    session.commit()

    service = _service(session, company, tmp_path)
    document = _upload(service, "bill-of-lading-a-clean-single-container.pdf")

    assert "CANONICAL_CONFLICT" in {issue.code for issue in document.issues}
    with pytest.raises(DocumentStateError):
        service.approve(document.id)
    session.refresh(shipment)
    assert shipment.destination_port_id == hamburg.id


def test_duplicate_bill_and_repeated_container_number_semantics(session, companies, tmp_path) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    first = _upload(service, "bill-of-lading-a-clean-single-container.pdf")
    service.approve(first.id)
    _document, first_bill = service.commit(first.id)

    second = _upload(service, "bill-of-lading-b-multiple-containers.pdf")
    service.approve(second.id)
    _document, second_bill = service.commit(second.id)
    occurrences = list(
        session.scalars(
            select(Container).where(
                Container.company_id == company.id,
                Container.container_number == "MSKU1234565",
            )
        ).all()
    )
    assert len(occurrences) == 2
    assert {item.shipment_id for item in occurrences} == {first_bill.shipment_id, second_bill.shipment_id}

    duplicate = _upload(service, "bill-of-lading-g-duplicate.pdf")
    assert "DUPLICATE_BILL_OF_LADING" in {issue.code for issue in duplicate.issues}
    with pytest.raises(DocumentStateError):
        service.approve(duplicate.id)


def test_weight_mismatch_and_transactional_failure_are_fail_closed(session, companies, tmp_path, monkeypatch) -> None:
    company, _other = companies
    service = _service(session, company, tmp_path)
    mismatch = _upload(service, "bill-of-lading-e-conflicting-weight.pdf")
    assert "TOTAL_WEIGHT_MISMATCH" in {issue.code for issue in mismatch.issues}

    valid = _upload(service, "bill-of-lading-b-multiple-containers.pdf")
    service.approve(valid.id)
    monkeypatch.setattr(service, "_resolve_or_create_voyage", lambda *_args: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(DocumentStateError):
        service.commit(valid.id)
    assert session.scalar(select(func.count(BillOfLading.id))) == 0
    assert session.scalar(select(func.count(Shipment.id))) == 0


def test_bill_of_lading_tenant_isolation(session, companies, tmp_path) -> None:
    first, second = companies
    first_service = _service(session, first, tmp_path / "first")
    second_service = _service(session, second, tmp_path / "second")
    document = _upload(first_service, "bill-of-lading-a-clean-single-container.pdf")
    with pytest.raises(LookupError):
        second_service.get(document.id)
