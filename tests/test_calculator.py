# tests/test_calculator.py

"""Testes do ShoppingCalculator com dados reais do PDF."""

from app.core.shopping.calculator import ShoppingCalculator
from app.core.models.diet_plan import DietPlan, FoodItem, Meal
from app.services.shopping_service import ShoppingService


def test_calculator_returns_items(real_diet_plan):
    calc = ShoppingCalculator()
    items = calc.calculate(real_diet_plan, days=7)
    assert len(items) > 0


def test_eggs_consolidated_across_meals(real_diet_plan):
    """Ovos aparecem em 3 refeições — devem ser somados."""
    calc = ShoppingCalculator()
    items = calc.calculate(real_diet_plan, days=1)
    egg_items = [i for i in items if "ovo" in i.name.lower()]
    assert len(egg_items) == 1  # consolidado em 1 item
    assert egg_items[0].total_quantity == 6  # 2+2+2 ovos por dia


def test_scale_7_days(real_diet_plan):
    calc = ShoppingCalculator()
    items_1 = calc.calculate(real_diet_plan, days=1)
    items_7 = calc.calculate(real_diet_plan, days=7)

    eggs_1 = next(i for i in items_1 if "ovo" in i.name.lower())
    eggs_7 = next(i for i in items_7 if "ovo" in i.name.lower())

    assert eggs_7.total_quantity == eggs_1.total_quantity * 7


def test_purchase_suggestion_eggs(real_diet_plan):
    calc = ShoppingCalculator()
    items = calc.calculate(real_diet_plan, days=7)
    eggs = next(i for i in items if "ovo" in i.name.lower())
    # 6 ovos/dia × 7 dias = 42 → "3 dúzias + 6"
    assert "dúzia" in eggs.purchase_suggestion


def test_fractional_egg_quantity_rounds_up_to_whole_eggs():
    plan = DietPlan(meals=[Meal(name="Café da manhã", items=[
        FoodItem(name="Ovo de galinha", quantity=2.5, unit="unidade(s)"),
    ])])

    eggs = ShoppingCalculator().calculate(plan, days=1)[0]

    assert eggs.total_quantity == 3
    assert eggs.purchase_suggestion == "3 unidades"


def test_supplement_scoop_packages_and_whey_equivalence():
    plan = DietPlan(meals=[Meal(name="Lanche", items=[
        FoodItem(name="Whey protein", quantity=15, unit="g"),
        FoodItem(name="Whey isolado", quantity=0.5, unit="scoop"),
        FoodItem(name="Creatina", quantity=1200, unit="g"),
    ])])
    items = {item.name: item for item in ShoppingCalculator().calculate(plan, days=1)}

    whey = items["Whey protein"]
    assert whey.total_quantity == 15
    assert "sachê individual de 30g" in whey.purchase_suggestion
    assert ShoppingService._format_exact_quantity(whey) == "15g (meio scoop)"

    whey_scoop = items["Whey isolado"]
    assert whey_scoop.total_quantity == 15
    assert whey_scoop.unit == "g"

    creatine = items["Creatina"]
    assert creatine.purchase_suggestion == "1 pacote família de 2kg"


def test_weight_display_and_meat_package_suggestion():
    plan = DietPlan(meals=[Meal(name="Almoço", items=[
        FoodItem(name="Peito de frango", quantity=1000, unit="g"),
        FoodItem(name="Pão integral", quantity=2, unit="unidade"),
        FoodItem(name="Aveia", quantity=999, unit="g"),
    ])])
    items = {item.name: item for item in ShoppingCalculator().calculate(plan, days=1)}

    assert items["Peito de frango"].purchase_suggestion == "2 pacotes (~1kg)"
    assert ShoppingService._format_exact_quantity(items["Peito de frango"]) == "1kg"
    assert items["Pão integral"].unit == "fatias"
    assert items["Pão integral"].purchase_suggestion == "2 fatias"
    assert items["Aveia"].purchase_suggestion == "~1kg"


def test_leftovers_are_subtracted_after_scaling_and_zero_items_are_removed():
    plan = DietPlan(meals=[Meal(name="Café", items=[
        FoodItem(name="Aveia", quantity=200, unit="g"),
        FoodItem(name="Banana", quantity=2, unit="unidade"),
    ])])
    calculator = ShoppingCalculator()

    adjusted = calculator.calculate(plan, days=3, leftovers_grams={"Aveia": 250})
    adjusted_by_name = {item.name: item for item in adjusted}
    assert adjusted_by_name["Aveia"].total_quantity == 350
    assert adjusted_by_name["Aveia"].purchase_suggestion == "~500g"
    assert adjusted_by_name["Banana"].total_quantity == 6

    covered = calculator.calculate(plan, days=3, leftovers_grams={"Aveia": 700})
    covered_by_name = {item.name: item for item in covered}
    assert covered_by_name["Aveia"].total_quantity == 0
    assert covered_by_name["Aveia"].purchase_suggestion is None
    assert covered_by_name["Banana"].total_quantity == 6