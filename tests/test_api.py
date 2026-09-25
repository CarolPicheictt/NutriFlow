# tests/test_api.py

"""Testes das rotas principais da API (upload, lista, checklist, export)."""

from __future__ import annotations

from fastapi.testclient import TestClient

MISSING_PLAN_ID = "00000000-0000-0000-0000-000000000000"


def test_upload_returns_plan_id_and_meta(client: TestClient, diet_plan_json: str):
    response = client.post(
        "/api/v1/upload",
        files={"file": ("plan.json", diet_plan_json.encode("utf-8"), "application/json")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_name"] == "Carolina Picheictt"
    assert body["meals_found"] == 7
    assert "plan_id" in body
    assert body["message"]


def test_upload_rejects_invalid_json(client: TestClient):
    response = client.post(
        "/api/v1/upload",
        files={"file": ("plan.json", b"{not valid json", "application/json")},
    )
    assert response.status_code == 422


def test_upload_pdf_is_not_yet_implemented(client: TestClient):
    response = client.post(
        "/api/v1/upload",
        files={"file": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 501


def test_shopping_list_for_missing_plan_returns_404(client: TestClient):
    response = client.get(f"/api/v1/shopping/{MISSING_PLAN_ID}")
    assert response.status_code == 404


def test_shopping_list_invalid_days_returns_422(client: TestClient, uploaded_plan_id: str):
    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 0})
    assert response.status_code == 422

    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 31})
    assert response.status_code == 422


def test_shopping_list_groups_items_by_category(client: TestClient, uploaded_plan_id: str):
    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 7})
    assert response.status_code == 200
    body = response.json()

    assert body["days"] == 7
    assert body["total_items"] > 0
    assert isinstance(body["categories"], dict)
    assert "outros" not in body["categories"] or isinstance(body["categories"]["outros"], list)

    all_items = [item for items in body["categories"].values() for item in items]
    assert len(all_items) == body["total_items"]


def test_checklist_can_be_marked_and_unmarked(client: TestClient, uploaded_plan_id: str):
    shopping = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 7}).json()
    first_item_name = next(iter(shopping["categories"].values()))[0]["name"]

    response = client.patch(
        f"/api/v1/checklist/{uploaded_plan_id}",
        json={"item_name": first_item_name, "checked": True},
    )
    assert response.status_code == 200
    assert response.json() == {"item_name": first_item_name, "checked": True}

    updated = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 7}).json()
    matched = [
        item["checked"]
        for items in updated["categories"].values()
        for item in items
        if item["name"] == first_item_name
    ]
    assert matched == [True]

    response = client.patch(
        f"/api/v1/checklist/{uploaded_plan_id}",
        json={"item_name": first_item_name, "checked": False},
    )
    assert response.status_code == 200
    assert response.json()["checked"] is False


def test_checklist_for_missing_plan_returns_404(client: TestClient):
    response = client.patch(
        f"/api/v1/checklist/{MISSING_PLAN_ID}",
        json={"item_name": "Arroz", "checked": True},
    )
    assert response.status_code == 404


def test_export_text_returns_shareable_list(client: TestClient, uploaded_plan_id: str):
    response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"days": 7, "fmt": "text"},
    )
    assert response.status_code == 200
    text = response.text
    assert "Lista de compras" in text
    assert "Total de itens" in text


def test_export_json_returns_structured_list(client: TestClient, uploaded_plan_id: str):
    response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"days": 7, "fmt": "json"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] == uploaded_plan_id
    assert body["days"] == 7
    assert "categories" in body


def test_export_for_missing_plan_returns_404(client: TestClient):
    response = client.get(f"/api/v1/shopping/{MISSING_PLAN_ID}/export")
    assert response.status_code == 404
