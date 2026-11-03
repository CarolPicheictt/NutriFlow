# backend/app/core/mealprep/planner.py

"""
planner.py

Engine do Meal Prep: transforma um ``DietPlan`` em um plano de preparo para
N dias, separando o que precisa ser cozinhado do que só é montado.

Reaproveita o ``ShoppingConsolidator`` (soma por refeição e fator de cocção)
e o ``FoodCategorizer``. As quantidades em peso seguem estas regras:

    - com fator de cocção único: peso cru = peso da dieta ÷ fator (quando a
      dieta traz o peso cozido) e peso cozido = peso cru × fator;
    - sem fator confiável: a quantidade da dieta é mantida, sem conversão,
      e o item recebe um aviso;
    - o peso cru é sempre arredondado para cima, em gramas inteiras.

As sobras informadas pelo usuário abatem apenas o peso cru dos itens que
vão ao fogo.
"""

from __future__ import annotations

import re
from math import ceil, floor
from typing import Optional

from app.core.mealprep.catalog import FoodPreparation, PreparationCatalog
from app.core.models.diet_plan import DietPlan
from app.core.models.meal_prep import (
    MealPrepAssembly,
    MealPrepAssemblyItem,
    MealPrepBreakdown,
    MealPrepItem,
    MealPrepPlan,
    RecipeLink,
)
from app.core.models.shopping_list import CookingFactorInfo, ShoppingItem, UnitType
from app.core.shopping.categorizer import FoodCategorizer
from app.core.shopping.consolidator import ShoppingConsolidator
from app.core.shopping.units import UnitNormalizer

_MAX_LINKS = 3
_CATEGORY_ORDER = {"proteínas": 0, "carboidratos": 1, "verduras e legumes": 2}
_PREPARATION_SUFFIX = re.compile(
    r"\s+(cozid[oa]s?|grelhad[oa]s?|assad[oa]s?|refogad[oa]s?|crus?|crua?s?)\s*$",
    re.IGNORECASE,
)
_NOTES = [
    "Os pesos cru e cozido são estimativas baseadas em fatores de rendimento; "
    "o resultado real varia com o tempo de cozimento e a quantidade de água.",
    "Itens sem fator de cocção confiável mantêm a quantidade da dieta, sem conversão.",
]


class MealPrepPlanner:
    """
    Calcula o plano de preparo (Meal Prep) a partir do plano alimentar.

    Uso:
        planner = MealPrepPlanner()
        plan = planner.plan(diet_plan, days=5, meal_names=["Almoço"])
    """

    def __init__(
        self,
        consolidator: Optional[ShoppingConsolidator] = None,
        categorizer: Optional[FoodCategorizer] = None,
        catalog: Optional[PreparationCatalog] = None,
    ) -> None:
        self._consolidator = consolidator or ShoppingConsolidator(UnitNormalizer())
        self._categorizer = categorizer or FoodCategorizer()
        self._catalog = catalog or PreparationCatalog.default()

    def plan(
        self,
        diet_plan: DietPlan,
        days: int = 5,
        meal_names: Optional[list[str]] = None,
        leftovers_grams: Optional[dict[str, float]] = None,
    ) -> MealPrepPlan:
        """
        Gera o plano de preparo para N dias.

        Args:
            diet_plan: Plano alimentar (representa 1 dia).
            days: Número de dias/porções a preparar.
            meal_names: Refeições a preparar. ``None`` considera todas.
            leftovers_grams: Sobras em gramas por nome do item, abatidas do
                peso cru dos itens cozinhados.

        Returns:
            ``MealPrepPlan`` com os itens a cozinhar e a montagem por refeição.
        """
        existing = list(dict.fromkeys(meal.name for meal in diet_plan.meals))
        wanted = list(dict.fromkeys(meal_names)) if meal_names else existing
        selected = [name for name in wanted if name in existing]
        if not selected:
            return MealPrepPlan(days=days, meals=[], notes=list(_NOTES))

        with_factor = self._consolidate(diet_plan, selected, True)
        factors = self._resolve_factors(diet_plan, selected, with_factor)
        per_meal_factor = {n: self._consolidate(diet_plan, [n], True) for n in selected}
        per_meal_factors = {
            n: self._resolve_factors(diet_plan, [n], per_meal_factor[n]) for n in selected
        }
        per_meal_plain = {n: self._consolidate(diet_plan, [n], False) for n in selected}

        cook_items = self._build_cook_items(
            with_factor, factors, per_meal_factor, per_meal_factors, days, leftovers_grams or {}
        )
        assembly = self._build_assembly(
            selected, per_meal_factor, per_meal_factors, per_meal_plain, days
        )
        return MealPrepPlan(
            days=days,
            meals=selected,
            cook_items=cook_items,
            assembly=assembly,
            notes=list(_NOTES),
        )

    # ------------------------------------------------------------------
    # Itens que vão ao fogo
    # ------------------------------------------------------------------

    def _consolidate(
        self,
        diet_plan: DietPlan,
        meals: list[str],
        consider_factor: bool,
        target_state: str = "raw",
    ) -> dict[str, ShoppingItem]:
        return self._consolidator.consolidate(
            diet_plan,
            meals,
            consider_cooking_factor=consider_factor,
            target_state=target_state,
        )

    def _resolve_factors(
        self,
        diet_plan: DietPlan,
        meals: list[str],
        raw_items: dict[str, ShoppingItem],
    ) -> dict[str, Optional[CookingFactorInfo]]:
        """
        Fator de cocção único de cada item, ou ``None`` se não houver.

        O consolidador com alvo "cru" só devolve o fator de itens prescritos
        já cozidos (quando a prescrição já está no estado-alvo, ele não
        procura fator). Para os prescritos em estado cru, uma segunda
        consulta com alvo "cozido" localiza o fator.
        """
        prepared = self._consolidate(diet_plan, meals, True, target_state="prepared")
        return {
            key: item.cooking_factor
            or (prepared[key].cooking_factor if key in prepared else None)
            for key, item in raw_items.items()
        }

    def _is_cooking(self, item: ShoppingItem, factor: Optional[CookingFactorInfo]) -> bool:
        food = self._catalog.find_food(item.name)
        if food is not None:
            return food.mode == "cook"
        if factor or item.cooking_factors:
            return True
        return bool(_PREPARATION_SUFFIX.search(item.name))

    def _build_cook_items(
        self,
        consolidated: dict[str, ShoppingItem],
        factors: dict[str, Optional[CookingFactorInfo]],
        per_meal: dict[str, dict[str, ShoppingItem]],
        per_meal_factors: dict[str, dict[str, Optional[CookingFactorInfo]]],
        days: int,
        leftovers: dict[str, float],
    ) -> list[MealPrepItem]:
        items: list[MealPrepItem] = []
        for key, item in consolidated.items():
            if not self._is_cooking(item, factors[key]):
                continue
            built = self._build_cook_item(
                key, item, factors[key], per_meal, per_meal_factors, days, leftovers
            )
            if built is not None:
                items.append(built)
        items.sort(key=lambda i: (_CATEGORY_ORDER.get(i.category, 3), i.name))
        return items

    def _build_cook_item(
        self,
        key: str,
        item: ShoppingItem,
        factor: Optional[CookingFactorInfo],
        per_meal: dict[str, dict[str, ShoppingItem]],
        per_meal_factors: dict[str, dict[str, Optional[CookingFactorInfo]]],
        days: int,
        leftovers: dict[str, float],
    ) -> Optional[MealPrepItem]:
        food = self._catalog.find_food(item.name)
        per_day = item.total_quantity
        warnings: list[str] = []
        cooked: Optional[float] = None

        if item.unit_type == UnitType.WEIGHT_G:
            exact = max(0.0, per_day * days - leftovers.get(item.name, 0.0))
            if exact <= 0:
                return None
            total = float(_ceil(exact))
            if factor is not None:
                cooked = float(_round_half_up(exact * factor.yield_factor))
                per_portion = round(per_day * factor.yield_factor, 1)
            else:
                per_portion = round(per_day, 1)
                warnings.append(self._no_factor_warning(item))
        elif item.unit_type == UnitType.UNIT:
            total = float(_ceil(per_day * days))
            per_portion = per_day
        elif item.unit_type == UnitType.FREE:
            total, per_portion = 0.0, None
        else:
            total = round(per_day * days, 1)
            per_portion = per_day

        method_key = (
            factor.cooking_method
            if factor
            else self._catalog.method_from_name(item.name)
            or (food.default_method if food else None)
        )
        method = self._catalog.get_method(method_key)
        steps = self._catalog.steps_for(food, method_key)
        unit_type, unit = item.unit_type, item.unit

        return MealPrepItem(
            name=item.name,
            category=self._categorizer.categorize(item.name),
            unit=unit,
            unit_type=unit_type,
            total_quantity=total,
            total_text=_format_quantity(unit_type, unit, total),
            cooked_quantity=cooked,
            cooked_text=_format_quantity(unit_type, unit, cooked) if cooked is not None else "",
            per_portion_quantity=per_portion,
            per_portion_text=_format_quantity(unit_type, unit, per_portion),
            cooking_factor=factor,
            method=method_key,
            method_label=method.label if method else None,
            instruction=self._instruction(item, total, factor is not None, steps),
            steps=[_sentence(step) for step in steps],
            links=_links(food),
            warnings=warnings,
            source_meals=list(item.source_meals),
            breakdown=self._breakdown(key, per_meal, per_meal_factors, days),
        )

    @staticmethod
    def _no_factor_warning(item: ShoppingItem) -> str:
        if len(item.cooking_factors) > 1:
            return (
                "Há mais de um fator de cocção para este alimento nas refeições "
                "escolhidas; a quantidade da dieta foi mantida."
            )
        return "Sem fator de cocção confiável; a quantidade da dieta foi mantida."

    def _instruction(
        self, item: ShoppingItem, total: float, is_raw: bool, steps: list[str]
    ) -> str:
        name = _display_name(item.name)
        quantity = _format_quantity(item.unit_type, item.unit, total)
        raw_mark = " cru" if is_raw else ""
        head = f"Prepare {quantity} de {name}{raw_mark}" if quantity else f"Prepare {name}"
        return f"{head}: {', '.join(steps)}." if steps else f"{head}."

    def _breakdown(
        self,
        key: str,
        per_meal: dict[str, dict[str, ShoppingItem]],
        per_meal_factors: dict[str, dict[str, Optional[CookingFactorInfo]]],
        days: int,
    ) -> list[MealPrepBreakdown]:
        parts = [(meal, items[key]) for meal, items in per_meal.items() if key in items]
        if len(parts) < 2:
            return []
        breakdown = []
        for meal, part in parts:
            per_day = part.total_quantity
            total = per_day * days
            per_portion = per_day
            if part.unit_type == UnitType.WEIGHT_G:
                total = float(_ceil(total))
                part_factor = per_meal_factors[meal].get(key)
                if part_factor is not None:
                    per_portion = round(per_day * part_factor.yield_factor, 1)
            breakdown.append(MealPrepBreakdown(
                meal_name=meal,
                total_quantity=total,
                total_text=_format_quantity(part.unit_type, part.unit, total),
                per_portion_quantity=per_portion,
                per_portion_text=_format_quantity(part.unit_type, part.unit, per_portion),
            ))
        return breakdown

    # ------------------------------------------------------------------
    # Montagem (itens que não vão ao fogo)
    # ------------------------------------------------------------------

    def _build_assembly(
        self,
        selected: list[str],
        per_meal_factor: dict[str, dict[str, ShoppingItem]],
        per_meal_factors: dict[str, dict[str, Optional[CookingFactorInfo]]],
        per_meal_plain: dict[str, dict[str, ShoppingItem]],
        days: int,
    ) -> list[MealPrepAssembly]:
        assembly: list[MealPrepAssembly] = []
        for meal in selected:
            decided = per_meal_factor[meal]
            cooking_keys = {
                k for k, item in decided.items()
                if self._is_cooking(item, per_meal_factors[meal][k])
            }
            plain_items = [
                item for k, item in per_meal_plain[meal].items() if k not in cooking_keys
            ]
            if not plain_items:
                continue
            foods = [self._catalog.find_food(item.name) for item in plain_items]
            has_cooked = bool(cooking_keys)
            assembly.append(MealPrepAssembly(
                meal_name=meal,
                instruction=self._assembly_instruction(plain_items, foods, has_cooked),
                has_cooked_items=has_cooked,
                items=[self._assembly_item(item, days) for item in plain_items],
                links=_links(*foods),
            ))
        return assembly

    def _assembly_instruction(
        self,
        items: list[ShoppingItem],
        foods: list[Optional[FoodPreparation]],
        has_cooked_items: bool,
    ) -> str:
        names = _join_names([_lower_first(item.name) for item in items])
        if has_cooked_items:
            verb = "marmita"
        elif len(items) == 1:
            verb = "separe"
        else:
            verbs = {(food.assemble_verb if food else None) or "junte" for food in foods}
            verb = verbs.pop() if len(verbs) == 1 else "junte"
        return self._catalog.assembly_template(verb).format(itens=names)

    @staticmethod
    def _assembly_item(item: ShoppingItem, days: int) -> MealPrepAssemblyItem:
        per_day = item.total_quantity
        if item.unit_type == UnitType.WEIGHT_G:
            total, per_portion = float(_ceil(per_day * days)), round(per_day, 1)
        elif item.unit_type == UnitType.UNIT:
            total, per_portion = float(_ceil(per_day * days)), per_day
        elif item.unit_type == UnitType.FREE:
            total, per_portion = 0.0, None
        else:
            total, per_portion = round(per_day * days, 1), per_day
        return MealPrepAssemblyItem(
            name=item.name,
            unit=item.unit,
            unit_type=item.unit_type,
            total_quantity=total,
            total_text=_format_quantity(item.unit_type, item.unit, total),
            per_portion_quantity=per_portion,
            per_portion_text=_format_quantity(item.unit_type, item.unit, per_portion),
        )


# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------

def _ceil(value: float) -> int:
    """Arredonda para cima ignorando ruído de ponto flutuante (250.00000000000003)."""
    return int(ceil(round(value, 6)))


def _round_half_up(value: float) -> int:
    return int(floor(round(value, 6) + 0.5))


def _format_quantity(unit_type: UnitType, unit: str, value: Optional[float]) -> str:
    if unit_type == UnitType.FREE:
        return "à vontade"
    if value is None:
        return ""
    if unit_type == UnitType.WEIGHT_G:
        return UnitNormalizer.format_weight_quantity(value)
    if unit_type == UnitType.VOLUME_ML:
        return f"{value / 1000:.1f}L".replace(".", ",") if value >= 1000 else f"{value:.0f}ml"
    number = f"{int(value)}" if float(value).is_integer() else f"{value:.1f}".replace(".", ",")
    label = {"un": "unidade" if value == 1 else "unidades"}.get(unit, unit)
    return f"{number} {label}".strip()


def _display_name(name: str) -> str:
    """Nome para a frase de preparo: sem o estado final (grelhado, cozido...)."""
    stripped = _PREPARATION_SUFFIX.sub("", name).strip() or name
    return _lower_first(stripped)


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _sentence(step: str) -> str:
    step = step.strip()
    return (step[:1].upper() + step[1:] + ("" if step.endswith(".") else ".")) if step else step


def _join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " e " + names[-1]


def _links(*foods: Optional[FoodPreparation]) -> list[RecipeLink]:
    links: list[RecipeLink] = []
    seen: set[str] = set()
    for food in foods:
        for link in (food.links if food else ()):
            if link.url not in seen:
                seen.add(link.url)
                links.append(link)
    return links[:_MAX_LINKS]
