# backend/app/api/routes/shopping.py

"""
shopping.py

Rotas da API relacionadas à lista de compras inteligente.

Nenhuma regra de negócio vive aqui: as rotas apenas validam entrada/saída
HTTP e delegam para os serviços de aplicação (``PlanService`` e
``ShoppingService``).
"""

from __future__ import annotations

import json
import math
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from starlette.responses import PlainTextResponse

from app.api.dependencies import get_plan_service, get_shopping_service
from app.core.models.shopping_list import ShoppingItem, ShoppingSubstitutionGroup
from app.services.plan_service import (
    InvalidDietPlanError,
    PlanService,
)
from app.services.shopping_service import ShoppingService

router = APIRouter(prefix="/api/v1", tags=["shopping"])


class UploadResponse(BaseModel):
    """Retorno do upload de um plano alimentar."""

    plan_id: UUID
    patient_name: str | None
    meals_found: int
    message: str


class ShoppingListResponse(BaseModel):
    """Retorno da lista de compras calculada."""

    plan_id: UUID
    days: int
    total_items: int
    categories: dict[str, list[ShoppingItem]]
    substitution_groups: list[ShoppingSubstitutionGroup]


class MealsResponse(BaseModel):
    """Refeições disponíveis em um plano alimentar."""

    meals: list[str]


class ChecklistUpdate(BaseModel):
    """Payload para atualizar estado de checklist."""

    item_name: str
    checked: bool


class ChecklistResponse(BaseModel):
    """Retorno da atualização de checklist."""

    item_name: str
    checked: bool


def _decode_substitution_choices(raw_choices: str | None) -> dict[str, str] | None:
    if raw_choices is None:
        return None
    try:
        choices = json.loads(raw_choices)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Escolhas de substituição inválidas.") from exc
    if not isinstance(choices, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in choices.items()
    ):
        raise HTTPException(status_code=422, detail="Escolhas de substituição inválidas.")
    return choices


def _decode_leftovers_grams(raw_leftovers: str | None) -> dict[str, float] | None:
    if raw_leftovers is None:
        return None
    try:
        leftovers = json.loads(raw_leftovers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.") from exc
    if not isinstance(leftovers, dict):
        raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.")

    decoded: dict[str, float] = {}
    for name, quantity in leftovers.items():
        if (
            not isinstance(name, str)
            or isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
            or quantity < 0
        ):
            raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.")
        decoded[name] = float(quantity)
    return decoded


@router.post("/upload", response_model=UploadResponse)
async def upload_diet(
    file: UploadFile = File(...),
    service: PlanService = Depends(get_plan_service),
) -> UploadResponse:
    """
    Recebe um plano alimentar em JSON (formato ``DietPlan``) e o armazena.

    Aceita:
        - application/json (suportado nesta versão)
                - application/pdf (extraído pelo ``WebDietParser``)

    Returns:
        ``UploadResponse`` com o ID do plano criado.
    """
    allowed = {"application/pdf", "application/json"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Formato não suportado: {file.content_type}",
        )

    content = await file.read()

    try:
        plan_id, diet_plan = await service.process_upload(content, file.content_type)
    except InvalidDietPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return UploadResponse(
        plan_id=plan_id,
        patient_name=diet_plan.patient.patient_name,
        meals_found=len(diet_plan.meals),
        message="Plano importado com sucesso",
    )


@router.get("/plans/{plan_id}/meals", response_model=MealsResponse)
async def get_plan_meals(
    plan_id: UUID,
    additional_plan_ids: list[UUID] | None = Query(None),
    service: ShoppingService = Depends(get_shopping_service),
) -> MealsResponse:
    """Retorna os nomes das refeições disponíveis para seleção."""
    meals = service.get_available_meals(plan_id, additional_plan_ids)
    if meals is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    return MealsResponse(meals=meals)


@router.get("/shopping/{plan_id}", response_model=ShoppingListResponse)
async def get_shopping_list(
    plan_id: UUID,
    days: int = Query(7, ge=1, le=31),
    meal_names: list[str] | None = Query(None),
    additional_plan_ids: list[UUID] | None = Query(None),
    substitution_choices: str | None = Query(None),
    leftovers_grams: str | None = Query(None),
    service: ShoppingService = Depends(get_shopping_service),
) -> ShoppingListResponse:
    """
    Retorna a lista de compras calculada para N dias.

    Args:
        plan_id: ID do plano alimentar importado.
        days: Número de dias para calcular (entre 1 e 31).

    Returns:
        ``ShoppingListResponse`` com itens agrupados por categoria.
    """
    result = await service.get_shopping_list(
        plan_id,
        days,
        meal_names,
        additional_plan_ids,
        _decode_substitution_choices(substitution_choices),
        _decode_leftovers_grams(leftovers_grams),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return ShoppingListResponse(
        plan_id=result.plan_id,
        days=result.days,
        total_items=result.total_items,
        categories=result.categories,
        substitution_groups=result.substitution_groups,
    )


@router.patch("/checklist/{plan_id}", response_model=ChecklistResponse)
async def update_checklist(
    plan_id: UUID,
    update: ChecklistUpdate,
    service: ShoppingService = Depends(get_shopping_service),
) -> ChecklistResponse:
    """
    Atualiza o estado de checagem de um item da lista de compras.

    Permite que o usuário marque (ou desmarque) o que já tem em casa.

    Args:
        plan_id: ID do plano alimentar.
        update: Item e novo estado (``checked: true/false``).
    """
    checked = await service.update_item_check(
        plan_id, update.item_name, update.checked
    )
    if checked is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return ChecklistResponse(item_name=update.item_name, checked=checked)


@router.get("/shopping/{plan_id}/export")
async def export_shopping_list(
    plan_id: UUID,
    days: int = Query(7, ge=1, le=31),
    fmt: str = Query("text", pattern="^(text|json)$"),
    meal_names: list[str] | None = Query(None),
    additional_plan_ids: list[UUID] | None = Query(None),
    substitution_choices: str | None = Query(None),
    leftovers_grams: str | None = Query(None),
    service: ShoppingService = Depends(get_shopping_service),
):
    """
    Exporta a lista de compras em formato compartilhável.

    Args:
        plan_id: ID do plano.
        days: Número de dias.
        fmt: Formato de saída — ``"text"`` (padrão) ou ``"json"``.

    Returns:
        Texto pronto para copiar/compartilhar (``fmt="text"``) ou um objeto
        JSON equivalente (``fmt="json"``).
    """
    result = await service.export_list(
        plan_id,
        days,
        fmt,
        meal_names,
        additional_plan_ids,
        _decode_substitution_choices(substitution_choices),
        _decode_leftovers_grams(leftovers_grams),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    if fmt == "text":
        return PlainTextResponse(str(result))

    return result
