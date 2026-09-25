# tests/test_calculator.py

"""Testes do ShoppingCalculator com dados reais do PDF."""

from app.core.shopping.calculator import ShoppingCalculator


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