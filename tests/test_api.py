# tests/test_api.py

"""Testes das rotas principais da API (upload, lista, checklist, export)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.plan_service import FilePlanRepository

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


def test_upload_pdf_parses_and_stores_plan(client: TestClient):
    from pathlib import Path

    pdf_path = Path(__file__).parent / "Plano alimentar - Carolina Picheictt.pdf"
    response = client.post(
        "/api/v1/upload",
        files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["patient_name"] == "Carolina Picheictt"
    assert body["meals_found"] > 0

    meals_response = client.get(f"/api/v1/plans/{body['plan_id']}/meals")
    assert meals_response.status_code == 200
    assert meals_response.json()["meals"]


def test_file_plan_repository_survives_recreation(real_diet_plan, tmp_path):
    plan_id = FilePlanRepository(tmp_path).save(real_diet_plan)

    restored_plan = FilePlanRepository(tmp_path).get(plan_id)

    assert restored_plan == real_diet_plan
    assert (tmp_path / f"{plan_id}.json").is_file()


def test_shopping_list_for_missing_plan_returns_404(client: TestClient):
    response = client.get(f"/api/v1/shopping/{MISSING_PLAN_ID}")
    assert response.status_code == 404


def test_plan_meals_lists_meals_and_returns_404_for_missing_plan(
    client: TestClient, uploaded_plan_id: str
):
    response = client.get(f"/api/v1/plans/{uploaded_plan_id}/meals")
    assert response.status_code == 200
    assert len(response.json()["meals"]) == 7

    response = client.get(f"/api/v1/plans/{MISSING_PLAN_ID}/meals")
    assert response.status_code == 404


def test_shopping_list_can_filter_selected_meals(
    client: TestClient, uploaded_plan_id: str
):
    meals_response = client.get(f"/api/v1/plans/{uploaded_plan_id}/meals")
    first_meal = meals_response.json()["meals"][0]

    full_list = client.get(f"/api/v1/shopping/{uploaded_plan_id}").json()
    filtered_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"meal_names": first_meal},
    )

    assert filtered_response.status_code == 200
    filtered_list = filtered_response.json()
    assert filtered_list["total_items"] > 0
    assert filtered_list["total_items"] < full_list["total_items"]

    export_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"fmt": "json", "meal_names": first_meal},
    )
    assert export_response.status_code == 200
    assert export_response.json()["total_items"] == filtered_list["total_items"]


def test_shopping_list_days_support_31_and_reject_values_outside_range(
    client: TestClient, uploaded_plan_id: str
):
    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 0})
    assert response.status_code == 422

    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 31})
    assert response.status_code == 200
    assert response.json()["days"] == 31

    response = client.get(f"/api/v1/shopping/{uploaded_plan_id}", params={"days": 32})
    assert response.status_code == 422

    export_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"days": 31, "fmt": "json"},
    )
    assert export_response.status_code == 200
    assert export_response.json()["days"] == 31

    export_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"days": 32, "fmt": "json"},
    )
    assert export_response.status_code == 422


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
    assert response.headers["content-type"].startswith("text/plain")
    assert text.startswith("*🛒 Lista de compras para 7 dias*")
    assert "- ☐ *" in text
    assert text.rstrip().splitlines()[-1].startswith("*Total: ")


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
