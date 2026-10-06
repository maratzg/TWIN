from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_current_company
from app.database import get_db
from app.main import app
from app.services import document_service


DEMO_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "invoices"


def test_document_api_end_to_end(session, companies, tmp_path, monkeypatch) -> None:
    company, second = companies
    company.name = "Demo Logistics SIA"
    company.registration_number = "40000000000"
    company.vat_number = "LV40000000000"
    session.commit()
    monkeypatch.setattr(document_service.settings, "document_storage_root", str(tmp_path))

    def database_override():
        yield session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_company] = lambda: company
    try:
        client = TestClient(app)
        with (DEMO_DIR / "invoice-a-clean.pdf").open("rb") as stream:
            upload = client.post(
                "/api/v1/documents",
                files={"file": ("invoice-a-clean.pdf", stream, "application/pdf")},
            )
        assert upload.status_code == 201, upload.text
        detail = upload.json()
        document_id = detail["document"]["id"]
        assert detail["document"]["document_type"] == "INVOICE"
        assert any(item["field_name"] == "invoice_number" for item in detail["candidates"])

        source = client.get(f"/api/v1/documents/{document_id}/source")
        assert source.status_code == 200
        assert source.headers["content-type"] == "application/pdf"
        assert source.content.startswith(b"%PDF-")

        corrected = client.patch(
            f"/api/v1/documents/{document_id}/fields/shipment_reference",
            json={"corrected_value": "SHP-2026-0091", "reason": "Confirmed against source"},
        )
        assert corrected.status_code == 200, corrected.text
        assert any(item["field_name"] == "shipment_reference" for item in corrected.json()["corrections"])
        revalidated = client.post(f"/api/v1/documents/{document_id}/revalidate")
        assert revalidated.status_code == 200, revalidated.text

        approved = client.post(
            f"/api/v1/documents/{document_id}/approve",
            json={"reviewer_reference": "api-smoke"},
        )
        assert approved.status_code == 200, approved.text
        committed = client.post(f"/api/v1/documents/{document_id}/commit")
        assert committed.status_code == 200, committed.text
        invoice_id = committed.json()["invoice"]["id"]

        invoice = client.get(f"/api/v1/invoices/{invoice_id}")
        assert invoice.status_code == 200
        assert invoice.json()["source_document_id"] == document_id
        assert client.get("/api/v1/invoices").json()["total"] == 1
        history_item = client.get("/api/v1/documents").json()["items"][0]
        assert history_item["canonical_invoice_id"] == invoice_id
        quality = client.get("/api/v1/data-quality").json()
        assert quality["recent_processed_documents"] == 1

        app.dependency_overrides[get_current_company] = lambda: second
        assert client.get(f"/api/v1/documents/{document_id}").status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/source").status_code == 404
    finally:
        app.dependency_overrides.clear()
