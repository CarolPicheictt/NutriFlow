# backend/app/services/meal_prep_service.py

"""
meal_prep_service.py

Serviço do Meal Prep: busca o plano alimentar (com substituições e várias
dietas, como na lista de compras) e monta o plano de preparo.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.core.mealprep.planner import MealPrepPlanner
from app.core.models.meal_prep import MealPrepPlan
from app.services.shopping_service import ShoppingService


class MealPrepService:
    """Orquestra a leitura do plano e o cálculo do Meal Prep."""

    def __init__(
        self,
        shopping_service: ShoppingService,
        planner: Optional[MealPrepPlanner] = None,
    ) -> None:
        self._shopping_service = shopping_service
        self._planner = planner or MealPrepPlanner()

    def get_meal_prep(
        self,
        plan_id: UUID,
        days: int,
        meal_names: Optional[list[str]] = None,
        additional_plan_ids: Optional[list[UUID]] = None,
        substitution_choices: Optional[dict[str, str]] = None,
        leftovers_grams: Optional[dict[str, float]] = None,
    ) -> Optional[MealPrepPlan]:
        """Plano de preparo para N dias, ou ``None`` se o plano não existir."""
        diet_plan = self._shopping_service.get_selected_plan(
            plan_id, additional_plan_ids, substitution_choices
        )
        if diet_plan is None:
            return None
        return self._planner.plan(
            diet_plan,
            days=days,
            meal_names=meal_names,
            leftovers_grams=leftovers_grams,
        )
