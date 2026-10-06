import pytest

from app.core.models.diet_plan import DietPlan, FoodItem, Meal
from app.core.shopping.cooking import calculate_food_quantity, find_cooking_factor
from app.core.shopping.calculator import ShoppingCalculator


def test_prepared_chicken_is_converted_to_raw_using_workbook_factor():
    result = calculate_food_quantity(
        prescribed_quantity=80,
        prescribed_state="prepared",
        target_state="raw",
        food="Peito de frango sem pele",
        cooking_method="grilling",
        consider_cooking_factor=True,
    )

    assert result.prescribed_quantity == 80
    assert result.calculated_quantity == pytest.approx(80 / 0.72)
    assert result.cooking_factor is not None
    assert result.cooking_factor.data_status == "USDA"
    assert result.cooking_factor.confidence == "high"
    assert result.cooking_factor.source_reference == "USDA Cooking Yield Data for Meat and Poultry"


def test_explicit_prep_in_food_name_supplies_state_and_method():
    result = calculate_food_quantity(
        prescribed_quantity=80,
        prescribed_state=None,
        target_state="raw",
        food="Peito de frango sem pele grelhado",
        consider_cooking_factor=True,
    )

    assert result.calculated_quantity == pytest.approx(80 / 0.72)
    assert result.weight_state == "prepared"
    assert result.cooking_factor is not None
    assert result.cooking_factor.cooking_method == "grilling"


def test_boiling_descriptor_matches_workbook_composite_method():
    result = calculate_food_quantity(
        prescribed_quantity=77,
        prescribed_state=None,
        target_state="raw",
        food="Peito de frango sem pele cozido",
        consider_cooking_factor=True,
    )

    assert result.calculated_quantity == pytest.approx(77 / 0.77)
    assert result.cooking_factor is not None
    assert result.cooking_factor.cooking_method == "boiling_braising"


def test_missing_weight_state_uses_only_unique_factor_for_prepared_food():
    result = calculate_food_quantity(
        prescribed_quantity=100,
        prescribed_state=None,
        target_state="raw",
        food="Feijão Preto",
        consider_cooking_factor=True,
    )

    assert result.calculated_quantity == pytest.approx(100 / 2.3)
    assert result.weight_state == "prepared"
    assert result.cooking_factor is not None
    assert result.cooking_factor.cooking_method == "water_absorption"


def test_short_diet_name_matches_unique_workbook_food_name():
    result = calculate_food_quantity(
        prescribed_quantity=25,
        prescribed_state=None,
        target_state="raw",
        food="Aveia",
        consider_cooking_factor=True,
    )

    assert result.cooking_factor is not None
    assert result.cooking_factor.food_name == "Aveia em flocos"
    assert result.calculated_quantity == pytest.approx(25 / result.cooking_factor.yield_factor)


def test_missing_method_does_not_choose_between_multiple_factors():
    result = calculate_food_quantity(
        prescribed_quantity=100,
        prescribed_state=None,
        target_state="raw",
        food="Cenoura",
        consider_cooking_factor=True,
    )

    assert result.calculated_quantity == 100
    assert result.cooking_factor is None


def test_toggle_off_preserves_prescribed_quantity():
    result = calculate_food_quantity(
        80, "prepared", "raw", "Peito de frango sem pele", "grilling", False
    )

    assert result.calculated_quantity == 80
    assert result.cooking_factor is None


def test_raw_weight_is_converted_to_prepared_weight_by_multiplying():
    result = calculate_food_quantity(
        prescribed_quantity=100,
        prescribed_state="raw",
        target_state="prepared",
        food="Peito de frango sem pele",
        cooking_method="grilling",
        consider_cooking_factor=True,
    )

    assert result.calculated_quantity == pytest.approx(72)


def test_ambiguous_or_not_applicable_factor_is_not_applied():
    ambiguous = calculate_food_quantity(
        100, "prepared", "raw", "Batata inglesa", consider_cooking_factor=True
    )
    not_applicable = find_cooking_factor("Tomate", "raw", "raw")

    assert ambiguous.calculated_quantity == 100
    assert ambiguous.cooking_factor is None
    assert not_applicable is None


def test_calculator_toggle_reuses_prescribed_quantity_without_accumulating():
    plan = DietPlan(meals=[Meal(name="Almoço", items=[FoodItem(
        name="Peito de frango sem pele",
        quantity=80,
        unit="g",
        prescribed_state="prepared",
        cooking_method="grilling",
    )])])
    calculator = ShoppingCalculator()

    off_first = calculator.calculate(plan, days=1)[0]
    on = calculator.calculate(plan, days=1, consider_cooking_factor=True)[0]
    off_again = calculator.calculate(plan, days=1)[0]
    on_again = calculator.calculate(plan, days=1, consider_cooking_factor=True)[0]

    assert off_first.total_quantity == 80
    assert on.total_quantity == 111.1
    assert off_again.total_quantity == 80
    assert on_again.total_quantity == 111.1
    assert on.prescribed_quantity == 80
    assert on.calculated_quantity == pytest.approx(80 / 0.72)
    assert on.cooking_factor is not None
    assert on.cooking_factor.data_status == "USDA"