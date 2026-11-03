# tests/test_meal_prep_api.py

"""Testes do endpoint do Meal Prep."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient


def _meals(client: TestClient, plan_id: str) -> list[str]:
    return client.get(f"/api/v1/plans/{plan_id}/meals").json()["meals"]


def test_meal_prep_for_missing_plan_returns_404(client: TestClient):
    assert client.get(f"/api/v1/meal-prep/{uuid4()}").status_code == 404


def test_meal_prep_returns_plan_for_requested_days(client: TestClient, uploaded_plan_id: str):
    response = client.get(f"/api/v1/meal-prep/{uploaded_plan_id}", params={"days": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] == uploaded_plan_id
    assert body["days"] == 5
    assert body["cook_items"] or body["assembly"]
    assert body["notes"]
    for item in body["cook_items"]:
        assert item["instruction"].startswith("Prepare ")


def test_meal_prep_days_are_validated(client: TestClient, uploaded_plan_id: str):
    for days in (0, 32):
        response = client.get(f"/api/v1/meal-prep/{uploaded_plan_id}", params={"days": days})
        assert response.status_code == 422


def test_meal_prep_can_filter_selected_meals(client: TestClient, uploaded_plan_id: str):
    first_meal = _meals(client, uploaded_plan_id)[0]

    body = client.get(
        f"/api/v1/meal-prep/{uploaded_plan_id}", params={"meal_names": first_meal}
    ).json()

    assert body["meals"] == [first_meal]
    assert {part["meal_name"] for item in body["cook_items"] for part in item["breakdown"]} <= {
        first_meal
    }


def test_meal_prep_applies_leftovers_and_rejects_invalid_ones(
    client: TestClient, uploaded_plan_id: str
):
    url = f"/api/v1/meal-prep/{uploaded_plan_id}"
    base = client.get(url, params={"days": 7}).json()
    weighed = next(i for i in base["cook_items"] if i["unit_type"] == "weight_g")

    reduced = client.get(
        url,
        params={"days": 7, "leftovers_grams": json.dumps({weighed["name"]: 10})},
    ).json()
    same_item = next(i for i in reduced["cook_items"] if i["name"] == weighed["name"])
    assert same_item["total_quantity"] < weighed["total_quantity"]

    invalid = client.get(url, params={"leftovers_grams": "isto não é json"})
    assert invalid.status_code == 422
