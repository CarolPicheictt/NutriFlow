# backend/app/api/routes/meal_prep.py

"""
meal_prep.py

Rota do Meal Prep: indica o que cozinhar e montar para as marmitas e lanches
de N dias, a partir de um plano alimentar já importado.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.decoders import decode_leftovers_grams, decode_substitution_choices
from app.api.dependencies import get_meal_prep_service
from app.core.models.meal_prep import MealPrepPlan
from app.services.meal_prep_service import MealPrepService

router = APIRouter(prefix="/api/v1", tags=["meal-prep"])


class MealPrepResponse(MealPrepPlan):
    """Plano de preparo com o ID do plano alimentar de origem."""

    plan_id: UUID


@router.get("/meal-prep/{plan_id}", response_model=MealPrepResponse)
def get_meal_prep(
    plan_id: UUID,
    days: int = Query(5, ge=1, le=31),
    meal_names: list[str] | None = Query(None),
    additional_plan_ids: list[UUID] | None = Query(None),
    substitution_choices: str | None = Query(None),
    leftovers_grams: str | None = Query(None),
    service: MealPrepService = Depends(get_meal_prep_service),
) -> MealPrepResponse:
    """
    Retorna o plano de preparo (Meal Prep) para N dias.

    Args:
        plan_id: ID do plano alimentar importado.
        days: Dias/porções a preparar (entre 1 e 31).
        meal_names: Refeições a preparar; sem valor, considera todas.
        additional_plan_ids: Outros planos somados (várias dietas).
        substitution_choices: JSON com as substituições escolhidas.
        leftovers_grams: JSON com sobras em gramas por item cozinhado.
    """
    plan = service.get_meal_prep(
        plan_id,
        days,
        meal_names,
        additional_plan_ids,
        decode_substitution_choices(substitution_choices),
        decode_leftovers_grams(leftovers_grams),
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    return MealPrepResponse(plan_id=plan_id, **plan.model_dump())
