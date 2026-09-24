from sqlalchemy import select

from app.models import LearnedMapping, Shipment
from app.services.import_service import ImportService, ImportStateError
from app.services.shipment_service import ShipmentService


CSV = b"CUST,BL_NO,CNTR_NO,VSL,POL,POD,GWT,REV,CURRENCY\nIKEA,BL-100,MSCU1234567,Ever Given,NLRTM,LVLPX,12000,5000,EUR\n"


def test_import_transitions_and_learned_mapping(session, companies) -> None:
    company, _ = companies
    service = ImportService(session, company.id)
    job = service.analyze("shipments.csv", CSV)
    assert job.status == "analyzed"

    service.update_mapping(
        job.id,
        [{"source_column": column.source_column, "canonical_field": column.canonical_field, "user_confirmed": True} for column in job.columns],
    )
    results = service.validate(job.id)
    assert results[0].disposition == "ready"
    committed = service.commit(job.id)
    assert committed.status == "committed"
    assert committed.imported_count == 1
    assert session.scalar(select(Shipment).where(Shipment.company_id == company.id)) is not None

    learned = session.scalar(
        select(LearnedMapping).where(
            LearnedMapping.company_id == company.id,
            LearnedMapping.normalized_header == "CUST",
        )
    )
    assert learned is not None
    second = service.analyze("next.csv", b"CUST,BL_NO\nABB,BL-100\n")
    cust = next(column for column in second.columns if column.source_column == "CUST")
    assert cust.mapping_method == "company_confirmed"
    assert cust.confidence == 1.0
    service.update_mapping(
        second.id,
        [{"source_column": column.source_column, "canonical_field": column.canonical_field, "user_confirmed": True} for column in second.columns],
    )
    duplicate = service.validate(second.id)[0]
    assert duplicate.disposition == "invalid"
    assert duplicate.issues[0].code == "DUPLICATE_EXISTING"


def test_import_state_requires_validation(session, companies) -> None:
    company, _ = companies
    job = ImportService(session, company.id).analyze("shipments.csv", CSV)
    try:
        ImportService(session, company.id).commit(job.id)
    except ImportStateError:
        pass
    else:
        raise AssertionError("Commit should require validation")


def test_tenant_isolation(session, companies) -> None:
    first, second = companies
    first_service = ImportService(session, first.id)
    job = first_service.analyze("shipments.csv", CSV)
    try:
        ImportService(session, second.id).get(job.id)
    except LookupError:
        pass
    else:
        raise AssertionError("A company must not access another company's import")
    first_service.update_mapping(
        job.id,
        [{"source_column": column.source_column, "canonical_field": column.canonical_field, "user_confirmed": True} for column in job.columns],
    )
    first_service.validate(job.id)
    first_service.commit(job.id)
    assert ShipmentService(session, first.id).list(None, 1, 25).total == 1
    assert ShipmentService(session, second.id).list(None, 1, 25).total == 0
