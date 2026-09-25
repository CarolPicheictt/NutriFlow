# tests/conftest.py

"""
conftest.py

Fixtures compartilhadas pela suíte de testes do NutriFlow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.models.diet_plan import DietPlan
from app.main import app


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "carolina_diet.json"


@pytest.fixture
def diet_plan_json() -> str:
    """Conteúdo JSON bruto do plano alimentar de exemplo (Carolina)."""
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def real_diet_plan(diet_plan_json: str) -> DietPlan:
    """``DietPlan`` real, gerado pelo parser do WebDiet a partir do PDF de exemplo."""
    return DietPlan.model_validate_json(diet_plan_json)


@pytest.fixture
def client() -> TestClient:
    """Cliente de testes da API FastAPI, isolado por override do estado."""
    return TestClient(app)


@pytest.fixture
def uploaded_plan_id(client: TestClient, diet_plan_json: str) -> str:
    """Faz upload do plano de exemplo e retorna o ``plan_id`` gerado."""
    response = client.post(
        "/api/v1/upload",
        files={"file": ("plan.json", diet_plan_json.encode("utf-8"), "application/json")},
    )
    assert response.status_code == 200, response.text
    return response.json()["plan_id"]
