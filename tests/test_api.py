# tests/test_api.py

"""Testes das rotas principais da API (upload, lista, checklist, export)."""

from __future__ import annotations

import json

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


def test_natalya_lunch_returns_separate_substitution_groups(client: TestClient):
    from pathlib import Path

    pdf_path = Path(__file__).parent / "Plano alimentar - Natalya Picheictt.pdf"
    upload = client.post(
        "/api/v1/upload",
        files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    response = client.get(f"/api/v1/shopping/{upload.json()['plan_id']}")
    assert response.status_code == 200
    lunch_groups = [
        group for group in response.json()["substitution_groups"]
        if group["meal_name"] == "Almoço"
    ]

    assert len(lunch_groups) == 2
    groups_by_original = {group["original_name"]: group for group in lunch_groups}
    assert [
        option["name"] for option in groups_by_original["Arroz Branco"]["options"]
    ] == ["Arroz Branco", "Batata inglesa", "Macarrão cozido", "Abóbora assada"]
    assert [
        option["name"]
        for option in groups_by_original["Peito de frango sem pele grelhado"]["options"]
    ] == [
        "Peito de frango sem pele grelhado",
        "Acém",
        "Lagarto",
        "Patinho grelhado",
        "Tilápia",
        "Coxão mole",
        "Músculo bovino",
        "Maminha",
        "Sobrecoxa de frango sem pele assada",
        "Lombo suíno",
    ]


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


def test_substitutions_default_to_original_and_can_be_selected(
    client: TestClient, uploaded_plan_id: str
):
    default_response = client.get(f"/api/v1/shopping/{uploaded_plan_id}")
    assert default_response.status_code == 200
    default = default_response.json()
    groups = default["substitution_groups"]
    assert len(groups) >= 2

    cheese_group = next(group for group in groups if group["original_name"] == "Ovo de galinha")
    cheese_option = next(option for option in cheese_group["options"] if option["name"] == "Queijo branco")
    selected_choices = {cheese_group["key"]: cheese_option["key"]}
    default_items = [item for items in default["categories"].values() for item in items]
    assert not any(item["name"] == "Queijo branco" for item in default_items)

    default_text = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"fmt": "text"},
    ).text
    assert "*Queijo branco*" not in default_text

    selected_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"substitution_choices": json.dumps(selected_choices)},
    )
    assert selected_response.status_code == 200
    selected_items = [
        item for items in selected_response.json()["categories"].values() for item in items
    ]
    selected_by_name = {item["name"]: item for item in selected_items}
    assert selected_by_name["Queijo branco"]["total_quantity"] == 14
    remaining_eggs = next(item for item in selected_items if "ovo" in item["name"].lower())
    assert remaining_eggs["total_quantity"] == 28

    export_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"fmt": "json", "substitution_choices": json.dumps(selected_choices)},
    )
    assert export_response.status_code == 200
    export_items = [
        item for items in export_response.json()["categories"].values() for item in items
    ]
    assert next(item for item in export_items if item["name"] == "Queijo branco")["total_quantity"] == 14

    selected_text_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"fmt": "text", "substitution_choices": json.dumps(selected_choices)},
    )
    assert selected_text_response.status_code == 200
    assert "*Queijo branco*" in selected_text_response.text
    assert "*Queijo branco -*" not in selected_text_response.text


def test_leftovers_are_applied_to_shopping_list_and_copied_text(
    client: TestClient, uploaded_plan_id: str
):
    leftovers = {"Aveia": 100}
    response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"days": 7, "leftovers_grams": json.dumps(leftovers)},
    )
    assert response.status_code == 200
    items = [item for values in response.json()["categories"].values() for item in values]
    oats = next(item for item in items if item["name"] == "Aveia")
    assert oats["total_quantity"] == 75

    text_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"days": 7, "fmt": "text", "leftovers_grams": json.dumps(leftovers)},
    )
    assert text_response.status_code == 200
    assert "*Aveia* — 75g" in text_response.text
    assert "*Aveia* — 175g" not in text_response.text

    fully_covered = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"days": 7, "leftovers_grams": json.dumps({"Aveia": 1000})},
    )
    remaining_items = [
        item for values in fully_covered.json()["categories"].values() for item in values
    ]
    fully_covered_oats = next(item for item in remaining_items if item["name"] == "Aveia")
    assert fully_covered_oats["total_quantity"] == 0

    fully_covered_text = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={
            "days": 7,
            "fmt": "text",
            "leftovers_grams": json.dumps({"Aveia": 1000}),
        },
    ).text
    assert "*Aveia*" not in fully_covered_text

    invalid_leftover = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"leftovers_grams": json.dumps({"Aveia": -1})},
    )
    assert invalid_leftover.status_code == 422

    invalid_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"substitution_choices": "not-json"},
    )
    assert invalid_response.status_code == 422


def test_shopping_list_combines_multiple_plans(
    client: TestClient, uploaded_plan_id: str, diet_plan_json: str
):
    second_plan = json.loads(diet_plan_json)
    second_plan["patient"]["patient_name"] = "Outra pessoa"
    second_upload = client.post(
        "/api/v1/upload",
        files={
            "file": (
                "second-plan.json",
                json.dumps(second_plan).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert second_upload.status_code == 200
    second_plan_id = second_upload.json()["plan_id"]

    single = client.get(f"/api/v1/shopping/{uploaded_plan_id}").json()
    combined_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={"additional_plan_ids": second_plan_id},
    )

    assert combined_response.status_code == 200
    combined = combined_response.json()
    single_items = {
        item["name"]: item["total_quantity"]
        for items in single["categories"].values()
        for item in items
    }
    combined_items = {
        item["name"]: item["total_quantity"]
        for items in combined["categories"].values()
        for item in items
    }
    assert combined["total_items"] == single["total_items"]
    assert combined_items.keys() == single_items.keys()
    assert all(combined_items[name] == quantity * 2 for name, quantity in single_items.items())

    meals_response = client.get(
        f"/api/v1/plans/{uploaded_plan_id}/meals",
        params={"additional_plan_ids": second_plan_id},
    )
    available_meals = meals_response.json()["meals"]
    assert len(available_meals) == 14
    assert "Carolina Picheictt · Café da manhã" in available_meals
    assert "Outra pessoa · Café da manhã" in available_meals

    selected_meal = "Outra pessoa · Café da manhã"
    filtered_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}",
        params={
            "additional_plan_ids": second_plan_id,
            "meal_names": selected_meal,
        },
    )
    assert filtered_response.status_code == 200
    filtered_items = [
        item
        for items in filtered_response.json()["categories"].values()
        for item in items
    ]
    assert filtered_items
    assert all(item["source_meals"] == [selected_meal] for item in filtered_items)
    assert any(
        group["meal_name"] == "Outra pessoa · Café da manhã"
        for group in combined["substitution_groups"]
    )

    export_response = client.get(
        f"/api/v1/shopping/{uploaded_plan_id}/export",
        params={"fmt": "json", "additional_plan_ids": second_plan_id},
    )
    assert export_response.status_code == 200
    assert export_response.json()["total_items"] == combined["total_items"]


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
