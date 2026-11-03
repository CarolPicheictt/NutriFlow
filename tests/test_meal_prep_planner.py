# tests/test_meal_prep_planner.py

"""Testes do cálculo do plano de preparo (Meal Prep)."""

from __future__ import annotations

import pytest

from app.core.mealprep.planner import MealPrepPlanner
from app.core.models.diet_plan import DietPlan, FoodItem, Meal
from app.core.models.shopping_list import UnitType


def _food(name: str, quantity: float | None, unit: str = "g", **extra) -> FoodItem:
    return FoodItem(name=name, quantity=quantity, unit=unit, **extra)


@pytest.fixture
def lunch_and_snack() -> DietPlan:
    """Exemplo do escopo: marmita de almoço e um lanche sem cozimento."""
    return DietPlan(meals=[
        Meal(name="Almoço", items=[
            _food("Peito de frango sem pele grelhado", 120),
            _food("Arroz branco cozido", 150),
            _food("Legumes", 100),
            _food("Salada", None, "À vontade"),
        ]),
        Meal(name="Lanche", items=[
            _food("Iogurte natural", 170),
            _food("Banana", 1, "Unidade(s) média(s)"),
            _food("Aveia em flocos", 30),
        ]),
    ])


def _cook(plan, name):
    return next(item for item in plan.cook_items if item.name == name)


def test_lunch_for_five_days_converts_cooked_weight_to_raw(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Almoço"])

    chicken = _cook(plan, "Peito de frango sem pele grelhado")
    assert chicken.total_quantity == 834  # 600 ÷ 0,72 = 833,3, arredondado para cima
    assert chicken.cooked_quantity == 600
    assert chicken.per_portion_quantity == 120
    assert chicken.cooking_factor.yield_factor == 0.72

    rice = _cook(plan, "Arroz branco cozido")
    assert rice.total_quantity == 250  # sem ruído de ponto flutuante (não vira 251)
    assert rice.cooked_quantity == 750
    assert rice.per_portion_quantity == 150


def test_instruction_names_raw_weight_and_simple_preparation(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Almoço"])

    instruction = _cook(plan, "Peito de frango sem pele grelhado").instruction
    assert instruction.startswith("Prepare 834g de peito de frango sem pele cru: ")
    assert "grelhe" in instruction
    assert instruction.endswith(".")
    assert _cook(plan, "Arroz branco cozido").steps[0] == "Lave o arroz."


def test_item_without_factor_keeps_diet_quantity_and_warns(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Almoço"])

    vegetables = _cook(plan, "Legumes")
    assert vegetables.total_quantity == 500
    assert vegetables.cooked_quantity is None
    assert vegetables.cooking_factor is None
    assert vegetables.warnings
    assert vegetables.instruction.startswith("Prepare 500g de legumes: ")


def test_raw_prescription_gets_cooked_weight_from_factor():
    diet = DietPlan(meals=[Meal(name="Almoço", items=[
        _food("Peito de frango sem pele", 100, prescribed_state="raw", cooking_method="grilling"),
    ])])
    chicken = MealPrepPlanner().plan(diet, days=5).cook_items[0]

    assert chicken.total_quantity == 500
    assert chicken.cooked_quantity == 360
    assert chicken.per_portion_quantity == 72


def test_lunch_non_cooking_items_are_added_when_assembling_each_container(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Almoço"])

    assert [a.meal_name for a in plan.assembly] == ["Almoço"]
    lunch = plan.assembly[0]
    assert lunch.has_cooked_items is True
    assert lunch.instruction == "Ao montar cada marmita, acrescente salada."
    assert lunch.items[0].total_text == "à vontade"


def test_snack_has_assembly_instruction_without_cooking_steps(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Lanche"])

    assert plan.cook_items == []
    snack = plan.assembly[0]
    assert snack.has_cooked_items is False
    assert snack.instruction == (
        "Misture iogurte natural, banana e aveia em flocos em um recipiente e consuma."
    )
    totals = {item.name: item.total_text for item in snack.items}
    # A aveia não passa pelo fator de cocção: 30 g × 5 dias = 150 g.
    assert totals == {"Iogurte natural": "850g", "Banana": "5 unidades", "Aveia em flocos": "150g"}
    assert 1 <= len(snack.links) <= 3


def test_single_non_cooking_item_is_just_separated():
    diet = DietPlan(meals=[Meal(name="Lanche", items=[_food("Maçã", 1, "Unidade(s)")])])
    snack = MealPrepPlanner().plan(diet, days=3).assembly[0]

    assert snack.instruction == "Separe maçã e consuma."


def test_leftovers_reduce_raw_weight_and_covered_items_disappear(lunch_and_snack):
    planner = MealPrepPlanner()
    plan = planner.plan(
        lunch_and_snack,
        days=5,
        meal_names=["Almoço"],
        leftovers_grams={"Arroz branco cozido": 50, "Legumes": 500},
    )

    rice = _cook(plan, "Arroz branco cozido")
    assert rice.total_quantity == 200
    assert rice.cooked_quantity == 600
    assert all(item.name != "Legumes" for item in plan.cook_items)


def test_unit_items_are_rounded_up():
    diet = DietPlan(meals=[Meal(name="Café", items=[_food("Ovo de galinha", 2.5, "Unidade(s)")])])
    eggs = MealPrepPlanner().plan(diet, days=5).cook_items[0]

    assert eggs.unit_type == UnitType.UNIT
    assert eggs.total_quantity == 13
    assert eggs.total_text == "13 unidades"
    assert eggs.links


def test_item_with_cooked_state_in_name_is_cooked_even_without_catalog_entry():
    diet = DietPlan(meals=[Meal(name="Jantar", items=[_food("Salmão grelhado", 100)])])
    salmon = MealPrepPlanner().plan(diet, days=5).cook_items[0]

    assert salmon.instruction.startswith("Prepare 500g de salmão")
    assert salmon.warnings


def test_only_selected_meals_are_planned_and_unknown_names_are_ignored(lunch_and_snack):
    planner = MealPrepPlanner()
    plan = planner.plan(lunch_and_snack, days=2, meal_names=["Lanche", "Inexistente"])

    assert plan.meals == ["Lanche"]
    assert planner.plan(lunch_and_snack, days=2, meal_names=["Inexistente"]).meals == []
    assert len(planner.plan(lunch_and_snack, days=2).meals) == 2


def test_breakdown_lists_each_person_when_item_appears_in_more_than_one_meal():
    diet = DietPlan(meals=[
        Meal(name="Ana · Almoço", items=[_food("Arroz branco cozido", 150)]),
        Meal(name="Bia · Almoço", items=[_food("Arroz branco cozido", 90)]),
    ])
    rice = MealPrepPlanner().plan(diet, days=5).cook_items[0]

    assert rice.total_quantity == 400  # (150 + 90) × 5 ÷ 3
    assert rice.cooked_quantity == 1200
    breakdown = {part.meal_name: part for part in rice.breakdown}
    assert breakdown["Ana · Almoço"].total_quantity == 250
    assert breakdown["Bia · Almoço"].total_quantity == 150
    assert breakdown["Bia · Almoço"].per_portion_quantity == 90


def test_cook_items_are_ordered_protein_then_carb_then_vegetables(lunch_and_snack):
    plan = MealPrepPlanner().plan(lunch_and_snack, days=5, meal_names=["Almoço"])

    assert [item.category for item in plan.cook_items] == [
        "proteínas", "carboidratos", "verduras e legumes",
    ]
