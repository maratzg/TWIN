from pathlib import Path

from fastapi.testclient import TestClient

from app.api.deps import get_current_company
from app.database import get_db
from app.main import app
from app.services import document_service


BILL_DIR = Path(__file__).resolve().parents[2] / "demo-data" / "bills-of-lading"


def test_bill_of_lading_api_smoke(session, companies, tmp_path, monkeypatch) -> None:
    company, second = companies
    monkeypatch.setattr(document_service.settings, "document_storage_root", str(tmp_path))

    def database_override():
        yield session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_company] = lambda: company
    try:
        client = TestClient(app)
        with (BILL_DIR / "bill-of-lading-b-multiple-containers.pdf").open("rb") as stream:
            upload = client.post(
                "/api/v1/documents",
                files={"file": ("bill-of-lading-b.pdf", stream, "application/pdf")},
            )
        assert upload.status_code == 201, upload.text
        detail = upload.json()
        document_id = detail["document"]["id"]
        assert detail["document"]["document_type"] == "BILL_OF_LADING"
        containers = [item for item in detail["candidates"] if item["group_type"] == "container"]
        assert len({item["group_index"] for item in containers}) == 3

        seal = next(item for item in containers if item["group_index"] == 1 and item["field_name"] == "seal_number")
        corrected = client.patch(
            f"/api/v1/documents/{document_id}/candidates/{seal['id']}",
            json={"corrected_value": "SEAL9002-A", "reason": "Seal visually confirmed"},
        )
        assert corrected.status_code == 200, corrected.text
        assert any(item["field_name"] == "containers[1].seal_number" for item in corrected.json()["corrections"])
        assert client.post(f"/api/v1/documents/{document_id}/revalidate").status_code == 200
        assert client.post(f"/api/v1/documents/{document_id}/approve", json={"reviewer_reference": "api-smoke"}).status_code == 200
        committed = client.post(f"/api/v1/documents/{document_id}/commit")
        assert committed.status_code == 200, committed.text
        bill_id = committed.json()["bill_of_lading"]["id"]

        bill = client.get(f"/api/v1/bills-of-lading/{bill_id}")
        assert bill.status_code == 200, bill.text
        body = bill.json()
        assert body["source_document_id"] == document_id
        assert body["vessel"] == "EVER AURORA"
        assert body["voyage"] == "EA0924W"
        assert body["port_of_loading"] == "RIGA"
        assert body["port_of_discharge"] == "HAMBURG"
        assert len(body["containers"]) == 3
        assert next(item for item in body["containers"] if item["container_number"] == "TEMU7654328")["seal_number"] == "SEAL9002-A"

        shipment = client.get(f"/api/v1/shipments/{body['shipment_id']}")
        assert shipment.status_code == 200, shipment.text
        assert len(shipment.json()["containers"]) == 3
        assert shipment.json()["documents"][0]["source_document_id"] == document_id
        assert client.get("/api/v1/bills-of-lading").json()["total"] == 1
        history = client.get("/api/v1/documents?document_type=BILL_OF_LADING").json()["items"][0]
        assert history["canonical_bill_of_lading_id"] == bill_id

        app.dependency_overrides[get_current_company] = lambda: second
        assert client.get(f"/api/v1/bills-of-lading/{bill_id}").status_code == 404
        assert client.get(f"/api/v1/shipments/{body['shipment_id']}").status_code == 404
    finally:
        app.dependency_overrides.clear()
