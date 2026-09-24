import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_company
from app.api.routes import data_quality, imports, shipments
from app.database import get_db
from app.models import ImportCorrection, LearnedMapping, Shipment
from app.services.import_service import ImportService, ImportStateError
from app.services.review_service import ImportReviewService


REVIEW_CSV = (
    "CUST;BL_NO;GWT;REF\n"
    "IKEA;BL-R-100;18,4t;\n"
    "ABB;BL-R-101;1200;RTM-8821\n"
    "No Identifier;;;\n"
).encode()


def confirm_known_columns(service: ImportService, job) -> None:
    service.update_mapping(
        job.id,
        [
            {
                "source_column": column.source_column,
                "canonical_field": column.canonical_field,
                "user_confirmed": True,
            }
            for column in job.columns
            if column.source_column != "REF"
        ],
    )


def test_history_row_filters_and_data_quality(session, companies) -> None:
    company, _ = companies
    service = ImportService(session, company.id)
    job = service.analyze("review.csv", REVIEW_CSV)
    confirm_known_columns(service, job)
    service.validate(job.id)

    review = ImportReviewService(session, company.id)
    history = review.history(search="review", status="needs_review", page=1, page_size=10)
    assert history["total"] == 1
    assert history["items"][0].id == job.id

    invalid = review.rows(job.id, disposition="invalid", search=None, page=1, page_size=1)
    assert invalid["total"] == 2
    assert len(invalid["items"]) == 1
    quality = review.data_quality()
    assert quality["imports_requiring_review"] == 1
    assert quality["review_rows"] == 1
    assert quality["invalid_rows"] == 2


def test_value_correction_preserves_raw_and_revalidates(session, companies) -> None:
    company, _ = companies
    service = ImportService(session, company.id)
    job = service.analyze("review.csv", REVIEW_CSV)
    confirm_known_columns(service, job)
    service.validate(job.id)
    row = job.rows[0]
    assert row.raw_data["GWT"] == "18,4t"
    assert row.disposition == "invalid"

    service.correct_row(
        job.id,
        row.id,
        "gross_weight",
        18400,
        source_column="GWT",
        unit="kg",
        reason="Source value was expressed in tonnes.",
    )
    assert row.raw_data["GWT"] == "18,4t"
    assert row.normalized_data["gross_weight"] == "18400"
    assert row.disposition == "ready"
    correction = session.scalar(
        select(ImportCorrection).where(ImportCorrection.import_row_id == row.id)
    )
    assert correction is not None
    assert correction.previous_value is None
    assert correction.corrected_value == "18400"
    assert correction.reviewer_reference == "demo-reviewer"


def test_mapping_correction_reprocesses_and_is_learned(session, companies) -> None:
    company, _ = companies
    service = ImportService(session, company.id)
    job = service.analyze("review.csv", REVIEW_CSV)
    confirm_known_columns(service, job)
    service.validate(job.id)
    mapping_row = job.rows[1]
    assert mapping_row.disposition == "review"

    service.update_mapping(
        job.id,
        [{"source_column": "REF", "canonical_field": "booking_reference", "user_confirmed": True}],
        reprocess=True,
    )
    assert mapping_row.disposition == "ready"
    assert mapping_row.normalized_data["booking_reference"] == "RTM-8821"
    learned = session.scalar(
        select(LearnedMapping).where(
            LearnedMapping.company_id == company.id,
            LearnedMapping.normalized_header == "REF",
        )
    )
    assert learned is not None
    assert learned.canonical_field == "booking_reference"

    future = service.analyze("future.csv", b"REF,GWT\nRTM-9900,900\n")
    ref = next(column for column in future.columns if column.source_column == "REF")
    assert ref.mapping_method == "company_confirmed"
    assert ref.canonical_field == "booking_reference"


def test_selective_commit_rejects_invalid_and_is_idempotent(session, companies) -> None:
    company, _ = companies
    service = ImportService(session, company.id)
    job = service.analyze("review.csv", REVIEW_CSV)
    confirm_known_columns(service, job)
    service.validate(job.id)
    service.correct_row(job.id, job.rows[0].id, "gross_weight", 18400, unit="kg")
    ready = job.rows[0]
    invalid = job.rows[2]

    first = service.commit_rows(job.id, [ready.id, invalid.id])
    assert first["committed"] == 1
    assert first["status"] == "partially_committed"
    assert first["skipped"][0]["reason"] == "row_is_invalid"
    assert ready.disposition == "committed"
    assert ready.canonical_record_id is not None

    repeated = service.commit_rows(job.id, [ready.id, invalid.id])
    assert repeated["committed"] == 0
    assert {item["reason"] for item in repeated["skipped"]} == {
        "already_committed",
        "row_is_invalid",
    }
    assert session.scalar(select(Shipment).where(Shipment.company_id == company.id)) is not None
    with pytest.raises(ImportStateError):
        service.update_mapping(
            job.id,
            [{"source_column": "REF", "canonical_field": "booking_reference"}],
            reprocess=True,
        )


def test_review_operations_are_tenant_isolated(session, companies) -> None:
    first, second = companies
    first_service = ImportService(session, first.id)
    job = first_service.analyze("review.csv", REVIEW_CSV)
    confirm_known_columns(first_service, job)
    first_service.validate(job.id)
    with pytest.raises(LookupError):
        ImportReviewService(session, second.id).row_detail(job.id, job.rows[0].id)
    with pytest.raises(LookupError):
        ImportService(session, second.id).correct_row(
            job.id,
            job.rows[0].id,
            "gross_weight",
            18400,
        )


def test_end_to_end_review_api_smoke(session, companies) -> None:
    company, _ = companies
    app = FastAPI()
    app.include_router(data_quality.router, prefix="/api/v1")
    app.include_router(imports.router, prefix="/api/v1")
    app.include_router(shipments.router, prefix="/api/v1")

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_company] = lambda: company

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/imports",
            files={"file": ("review.csv", REVIEW_CSV, "text/csv")},
        )
        created.raise_for_status()
        import_id = created.json()["id"]
        mapping = client.get(f"/api/v1/imports/{import_id}/mapping").json()
        known = [item for item in mapping["mappings"] if item["source_column"] != "REF"]
        saved = client.put(
            f"/api/v1/imports/{import_id}/mapping",
            json={
                "mappings": [
                    {
                        "source_column": item["source_column"],
                        "canonical_field": item["canonical_field"],
                        "user_confirmed": True,
                    }
                    for item in known
                ]
            },
        )
        saved.raise_for_status()
        validated = client.post(f"/api/v1/imports/{import_id}/validate")
        validated.raise_for_status()
        assert validated.json()["invalid"] == 2
        assert validated.json()["needs_review"] == 1

        invalid_rows = client.get(
            f"/api/v1/imports/{import_id}/rows",
            params={"disposition": "invalid"},
        ).json()
        value_row = next(
            item for item in invalid_rows["items"] if "INVALID_NUMBER" in item["issue_codes"]
        )
        detail = client.get(
            f"/api/v1/imports/{import_id}/rows/{value_row['id']}"
        ).json()
        assert next(cell for cell in detail["cells"] if cell["source_column"] == "GWT")["raw_value"] == "18,4t"

        corrected = client.patch(
            f"/api/v1/imports/{import_id}/rows/{value_row['id']}",
            json={
                "source_column": "GWT",
                "canonical_field": "gross_weight",
                "corrected_value": 18400,
                "unit": "kg",
                "reason": "Confirmed from source document",
            },
        )
        corrected.raise_for_status()
        assert corrected.json()["disposition"] == "ready"
        assert corrected.json()["raw_data"]["GWT"] == "18,4t"

        remapped = client.put(
            f"/api/v1/imports/{import_id}/mapping",
            json={
                "mappings": [
                    {
                        "source_column": "REF",
                        "canonical_field": "booking_reference",
                        "user_confirmed": True,
                    }
                ],
                "reprocess": True,
            },
        )
        remapped.raise_for_status()
        ready_rows = client.get(
            f"/api/v1/imports/{import_id}/rows",
            params={"disposition": "ready"},
        ).json()["items"]
        assert len(ready_rows) == 2

        committed = client.post(
            f"/api/v1/imports/{import_id}/commit",
            json={"row_ids": [item["id"] for item in ready_rows]},
        )
        committed.raise_for_status()
        assert committed.json()["committed"] == 2
        assert committed.json()["status"] == "partially_committed"
        shipment_page = client.get("/api/v1/shipments").json()
        assert shipment_page["total"] == 2
        assert {item["gross_weight"] for item in shipment_page["items"]} == {"18400.000", "1200.000"}

        audit = client.get(
            f"/api/v1/imports/{import_id}/rows/{value_row['id']}"
        ).json()["corrections"]
        assert audit[0]["corrected_value"] == "18400"
        quality = client.get("/api/v1/data-quality").json()
        assert quality["imports_requiring_review"] == 1
        assert quality["invalid_rows"] == 1
