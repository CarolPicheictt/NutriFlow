# backend/app/services/shopping_service.py

"""
shopping_service.py

Orquestra o cálculo da lista de compras, o estado do checklist ("já tenho
em casa") e a exportação da lista em formatos compartilháveis.

Assim como o ``PlanService``, o estado do checklist é mantido em memória
para o MVP, atrás de uma interface simples que pode ser trocada por
persistência real (PostgreSQL) no futuro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

from app.core.models.diet_plan import DietPlan, FoodItem
from app.core.models.shopping_list import (
    ShoppingItem,
    ShoppingSubstitutionGroup,
    ShoppingSubstitutionOption,
    UnitType,
)
from app.core.shopping.calculator import ShoppingCalculator
from app.core.shopping.consolidator import FoodNameNormalizer
from app.core.shopping.units import UnitNormalizer
from app.services.plan_service import PlanService


@dataclass
class ShoppingListResult:
    """Resultado do cálculo da lista de compras para um plano."""

    plan_id: UUID
    days: int
    total_items: int
    categories: dict[str, list[ShoppingItem]] = field(default_factory=dict)
    substitution_groups: list[ShoppingSubstitutionGroup] = field(default_factory=list)


class ChecklistRepository(Protocol):
    """
    Interface de armazenamento do estado de checklist por plano.

    O estado é independente do número de dias (`days`): marcar "já tenho
    farinha de aveia em casa" vale tanto para uma lista de 3 quanto de 30
    dias, então a chave de armazenamento é apenas ``(plan_id, nome
    normalizado do item)``.
    """

    def get_checked(self, plan_id: UUID, normalized_name: str) -> bool:
        ...

    def set_checked(
        self, plan_id: UUID, normalized_name: str, checked: bool
    ) -> None:
        ...


class InMemoryChecklistRepository:
    """Implementação em memória de ``ChecklistRepository``."""

    def __init__(self) -> None:
        self._state: dict[UUID, dict[str, bool]] = {}

    def get_checked(self, plan_id: UUID, normalized_name: str) -> bool:
        return self._state.get(plan_id, {}).get(normalized_name, False)

    def set_checked(
        self, plan_id: UUID, normalized_name: str, checked: bool
    ) -> None:
        self._state.setdefault(plan_id, {})[normalized_name] = checked


class ShoppingService:
    """
    Serviço de aplicação responsável pela lista de compras.

    Uso:
        service = ShoppingService(plan_service, ShoppingCalculator(), InMemoryChecklistRepository())
        result = await service.get_shopping_list(plan_id, days=7)
    """

    def __init__(
        self,
        plan_service: PlanService,
        calculator: Optional[ShoppingCalculator] = None,
        checklist_repository: Optional[ChecklistRepository] = None,
    ) -> None:
        self._plan_service = plan_service
        self._calculator = calculator or ShoppingCalculator()
        self._checklist_repository = checklist_repository or InMemoryChecklistRepository()
        self._name_normalizer = FoodNameNormalizer()

    async def get_shopping_list(
        self,
        plan_id: UUID,
        days: int,
        meal_names: Optional[list[str]] = None,
        additional_plan_ids: Optional[list[UUID]] = None,
        substitution_choices: Optional[dict[str, str]] = None,
        leftovers_grams: Optional[dict[str, float]] = None,
    ) -> Optional[ShoppingListResult]:
        """
        Calcula a lista de compras de um plano, agrupada por categoria.

        Aplica o estado de checklist já salvo (itens marcados como
        disponíveis em casa) antes de retornar.

        Args:
            plan_id: ID do plano alimentar importado.
            days: Número de dias para calcular.
            meal_names: Quando informado, restringe o cálculo apenas às
                refeições selecionadas pelo usuário (ex.: mostrar só os
                ingredientes do café da manhã e do pré-treino). ``None``
                considera todas as refeições do plano.

        Returns:
            ``ShoppingListResult`` com os itens agrupados por categoria, ou
            ``None`` se o plano não existir.
        """
        diet_plan = self._get_combined_plan(plan_id, additional_plan_ids)
        if diet_plan is None:
            return None

        groups, replacement_items = self._build_substitution_groups(diet_plan)
        selected_plan = self._apply_substitution_choices(
            diet_plan, replacement_items, substitution_choices or {}
        )
        items = self._calculator.calculate(
            selected_plan,
            days=days,
            meal_names=meal_names,
            leftovers_grams=leftovers_grams,
        )
        self._apply_checklist(plan_id, items)

        categories: dict[str, list[ShoppingItem]] = {}
        for item in items:
            categories.setdefault(item.category, []).append(item)

        return ShoppingListResult(
            plan_id=plan_id,
            days=days,
            total_items=len(items),
            categories=categories,
            substitution_groups=groups,
        )

    def get_available_meals(
        self,
        plan_id: UUID,
        additional_plan_ids: Optional[list[UUID]] = None,
    ) -> Optional[list[str]]:
        """
        Retorna os nomes das refeições do plano, na ordem em que aparecem.

        Usado pela interface para montar a seleção de refeições (Feature 2)
        sem duplicar essa informação em outro lugar.

        Args:
            plan_id: ID do plano alimentar.

        Returns:
            Lista de nomes de refeições, ou ``None`` se o plano não existir.
        """
        diet_plan = self._get_combined_plan(plan_id, additional_plan_ids)
        if diet_plan is None:
            return None
        return list(dict.fromkeys(meal.name for meal in diet_plan.meals))

    def _get_combined_plan(
        self,
        plan_id: UUID,
        additional_plan_ids: Optional[list[UUID]] = None,
    ) -> Optional[DietPlan]:
        """Combina as refeições dos planos, ignorando IDs repetidos."""
        plan_ids = dict.fromkeys([plan_id, *(additional_plan_ids or [])])
        plans = [self._plan_service.get_plan(current_id) for current_id in plan_ids]
        if any(plan is None for plan in plans):
            return None

        valid_plans = [plan for plan in plans if plan is not None]
        if len(valid_plans) == 1:
            return DietPlan(meals=valid_plans[0].meals)

        person_names = [
            (plan.patient.patient_name or "").strip() or f"Pessoa {index + 1}"
            for index, plan in enumerate(valid_plans)
        ]
        name_counts = {
            name: person_names.count(name)
            for name in set(person_names)
        }
        name_occurrences: dict[str, int] = {}
        meals: list[Meal] = []

        for person_name, plan in zip(person_names, valid_plans):
            name_occurrences[person_name] = name_occurrences.get(person_name, 0) + 1
            display_name = person_name
            if name_counts[person_name] > 1:
                display_name = f"{person_name} ({name_occurrences[person_name]})"

            for meal in plan.meals:
                identified_meal = meal.model_copy(deep=True)
                identified_meal.name = f"{display_name} · {meal.name}"
                meals.append(identified_meal)

        return DietPlan(meals=meals)

    def _build_substitution_groups(
        self, diet_plan: DietPlan
    ) -> tuple[
        list[ShoppingSubstitutionGroup],
        dict[tuple[int, int], dict[str, FoodItem]],
    ]:
        groups: list[ShoppingSubstitutionGroup] = []
        replacements: dict[tuple[int, int], dict[str, FoodItem]] = {}

        for meal_index, meal in enumerate(diet_plan.meals):
            for substitution in meal.substitutions:
                if not substitution.substitution_for:
                    continue

                target_name = self._normalize_substitution_name(
                    substitution.substitution_for
                )
                source_index = next((
                    index for index, item in enumerate(meal.items)
                    if self._normalize_substitution_name(item.name) == target_name
                    and not self._is_substitution_item(item, meal.substitutions)
                ), None)
                if source_index is None:
                    continue

                alternative = self._parse_substitution_food(substitution)
                if alternative is None:
                    continue

                group_key = f"{meal_index}:{source_index}"
                group = next((item for item in groups if item.key == group_key), None)
                if group is None:
                    original = meal.items[source_index]
                    group = ShoppingSubstitutionGroup(
                        key=group_key,
                        meal_name=meal.name,
                        original_name=original.name,
                        options=[ShoppingSubstitutionOption(
                            key="default",
                            name=original.name,
                            quantity=original.quantity or 0,
                            unit=original.unit or "",
                        )],
                    )
                    groups.append(group)
                    replacements[(meal_index, source_index)] = {}

                option_key = f"alternative:{len(group.options)}"
                group.options.append(ShoppingSubstitutionOption(
                    key=option_key,
                    name=alternative.name,
                    quantity=alternative.quantity or 0,
                    unit=alternative.unit or "",
                ))
                replacements[(meal_index, source_index)][option_key] = alternative

        return groups, replacements

    def _apply_substitution_choices(
        self,
        diet_plan: DietPlan,
        replacements: dict[tuple[int, int], dict[str, FoodItem]],
        choices: dict[str, str],
    ) -> DietPlan:
        selected_plan = diet_plan.model_copy(deep=True)
        for meal_index, meal in enumerate(selected_plan.meals):
            selected_items: list[FoodItem] = []
            for item_index, item in enumerate(meal.items):
                if self._is_substitution_item(item, meal.substitutions):
                    continue

                group_key = f"{meal_index}:{item_index}"
                choice_key = choices.get(group_key, "default")
                replacement = replacements.get((meal_index, item_index), {}).get(choice_key)
                selected_items.append(replacement.model_copy(deep=True) if replacement else item)
            meal.items = selected_items

        return selected_plan

    @staticmethod
    def _normalize_substitution_name(name: str) -> str:
        return FoodNameNormalizer().normalize(name.strip().rstrip(" -").strip())

    def _is_substitution_item(self, item: FoodItem, substitutions: list[FoodItem]) -> bool:
        item_name = self._normalize_substitution_name(item.name)
        return any(
            self._normalize_substitution_name(substitution.name) == item_name
            for substitution in substitutions
        )

    @staticmethod
    def _parse_substitution_food(substitution: FoodItem) -> Optional[FoodItem]:
        if substitution.quantity is not None and substitution.unit:
            return substitution.model_copy(deep=True)

        raw_quantity = (substitution.raw_quantity or "").strip()
        raw_quantity = re.sub(r"\s*\([^)]*\)\s*$", "", raw_quantity).strip()
        match = re.match(r"^(\d+(?:[.,]\d+)?)\s*(.*?)\s*$", raw_quantity)
        if not match:
            return None

        unit = match.group(2).strip()
        if not unit:
            return None
        return FoodItem(
            name=substitution.name,
            quantity=float(match.group(1).replace(",", ".")),
            unit=unit,
            raw_quantity=substitution.raw_quantity,
            substitution_for=substitution.substitution_for,
        )

    async def update_item_check(
        self, plan_id: UUID, item_name: str, checked: bool
    ) -> Optional[bool]:
        """
        Marca ou desmarca um item como já disponível em casa.

        Args:
            plan_id: ID do plano alimentar.
            item_name: Nome do item (como exibido na lista de compras).
            checked: Novo estado desejado.

        Returns:
            O valor de ``checked`` aplicado, ou ``None`` se o plano não
            existir.
        """
        if self._plan_service.get_plan(plan_id) is None:
            return None

        normalized_name = self._name_normalizer.normalize(item_name)
        self._checklist_repository.set_checked(plan_id, normalized_name, checked)
        return checked

    async def export_list(
        self,
        plan_id: UUID,
        days: int,
        fmt: str,
        meal_names: Optional[list[str]] = None,
        additional_plan_ids: Optional[list[UUID]] = None,
        substitution_choices: Optional[dict[str, str]] = None,
        leftovers_grams: Optional[dict[str, float]] = None,
    ) -> Optional[dict | str]:
        """
        Exporta a lista de compras em formato texto ou JSON.

        Args:
            plan_id: ID do plano alimentar.
            days: Número de dias.
            fmt: ``"text"`` (padrão) ou ``"json"``.
            meal_names: Mesma seleção de refeições usada em
                ``get_shopping_list`` — a exportação reflete o que o
                usuário está vendo na tela.

        Returns:
            Uma string formatada para copiar/compartilhar (``fmt="text"``),
            um dicionário serializável (``fmt="json"``), ou ``None`` se o
            plano não existir.

        Raises:
            ValueError: ``fmt`` diferente de ``"text"``/``"json"``.
        """
        result = await self.get_shopping_list(
            plan_id,
            days,
            meal_names,
            additional_plan_ids,
            substitution_choices,
            leftovers_grams,
        )
        if result is None:
            return None

        if fmt == "json":
            return {
                "plan_id": str(result.plan_id),
                "days": result.days,
                "total_items": result.total_items,
                "substitution_groups": [group.model_dump() for group in result.substitution_groups],
                "categories": {
                    category: [item.model_dump() for item in items]
                    for category, items in result.categories.items()
                },
            }

        if fmt == "text":
            return self._render_text(result)

        raise ValueError(f"Formato de exportação não suportado: {fmt!r}")

    def _apply_checklist(self, plan_id: UUID, items: list[ShoppingItem]) -> None:
        """Preenche ``item.checked`` com o estado salvo no checklist."""
        for item in items:
            item.checked = self._checklist_repository.get_checked(
                plan_id, item.normalized_name
            )

    @staticmethod
    def _render_text(result: ShoppingListResult) -> str:
        """
        Renderiza a lista com Markdown compatível com WhatsApp.
        """
        day_label = "dia" if result.days == 1 else "dias"
        lines = [f"*🛒 Lista de compras para {result.days} {day_label}*", ""]

        purchasable_categories = {
            category: [
                item for item in items
                if item.unit_type != UnitType.WEIGHT_G or item.total_quantity > 0
            ]
            for category, items in result.categories.items()
        }
        purchasable_categories = {
            category: items for category, items in purchasable_categories.items() if items
        }

        for category, items in sorted(purchasable_categories.items()):
            lines.append(f"*{category.upper()}*")
            for item in items:
                mark = "✅" if item.checked else "☐"
                quantity = ShoppingService._format_exact_quantity(item)
                details = f" — {quantity}" if quantity else ""
                if item.purchase_suggestion:
                    suggestion = item.purchase_suggestion
                    if quantity and not suggestion.lower().startswith("compre "):
                        suggestion = f"compre {suggestion}"
                    details += f" · {suggestion}" if quantity else f" — {suggestion}"
                lines.append(f"- {mark} *{item.name}*{details}")
            lines.append("")

        total_items = sum(len(items) for items in purchasable_categories.values())
        item_label = "item" if total_items == 1 else "itens"
        lines.append(f"*Total: {total_items} {item_label}*")
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _format_exact_quantity(item: ShoppingItem) -> str:
        if item.unit_type.value == "free":
            return ""

        quantity = item.total_quantity
        if item.unit_type.value == "weight_g":
            formatted = UnitNormalizer.format_weight_quantity(quantity)
            if item.category == "suplementos" and "whey" in item.name.lower():
                if quantity == 15:
                    return f"{formatted} (meio scoop)"
                scoops = f"{quantity / 30:.1f}".rstrip("0").rstrip(".").replace(".", ",")
                return f"{formatted} ({scoops} {'scoop' if quantity == 30 else 'scoops'})"
            return formatted

        if quantity.is_integer():
            quantity_text = f"{int(quantity):,}".replace(",", ".")
        else:
            quantity_text = f"{quantity:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")

        unit = item.unit.strip()
        if not unit:
            return quantity_text
        return f"{quantity_text}{unit}" if unit in {"g", "ml"} else f"{quantity_text} {unit}"