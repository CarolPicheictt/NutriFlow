# tests/test_consolidator.py

"""Testes de normalização de nomes/unidades e consolidação de duplicatas."""

from app.core.models.diet_plan import DietPlan, FoodItem, Meal
from app.core.models.shopping_list import UnitType
from app.core.shopping.calculator import ShoppingCalculator
from app.core.shopping.categorizer import FoodCategorizer
from app.core.shopping.consolidator import FoodNameNormalizer, ShoppingConsolidator
from app.core.shopping.units import UnitNormalizer


def make_plan(*meals: Meal) -> DietPlan:
    return DietPlan(meals=list(meals))


def test_name_normalizer_removes_qualifiers_and_extra_spaces():
    normalizer = FoodNameNormalizer()
    assert normalizer.normalize("Arroz   branco   cozido") == "arroz branco"
    assert normalizer.normalize("Feijão Preto") == "feijão preto"


def test_kg_is_converted_to_grams():
    normalizer = UnitNormalizer()
    assert normalizer.classify("kg") == UnitType.WEIGHT_G
    assert normalizer.to_base_unit(1.5, "kg") == 1500


def test_liters_are_converted_to_milliliters():
    normalizer = UnitNormalizer()
    assert normalizer.classify("l") == UnitType.VOLUME_ML
    assert normalizer.to_base_unit(2, "litro") == 2000


def test_colher_is_not_misclassified_as_volume():
    """'Colher' contém a letra 'l', mas não é uma unidade de volume."""
    normalizer = UnitNormalizer()
    assert normalizer.classify("Colher(es)") == UnitType.UNIT


def test_a_vontade_is_classified_as_free():
    normalizer = UnitNormalizer()
    assert normalizer.classify("À vontade") == UnitType.FREE


def test_ignores_items_without_name():
    plan = make_plan(
        Meal(
            name="Almoço",
            items=[
                FoodItem(name="", quantity=100, unit="g"),
                FoodItem(name="Arroz branco", quantity=100, unit="g"),
            ],
        )
    )
    consolidator = ShoppingConsolidator()
    items = consolidator.consolidate(plan)
    assert len(items) == 1
    assert "arroz" in next(iter(items))


def test_duplicate_food_across_meals_is_consolidated():
    plan = make_plan(
        Meal(
            name="Café da manhã",
            items=[FoodItem(name="Aveia", quantity=30, unit="g")],
        ),
        Meal(
            name="Lanche",
            items=[FoodItem(name="Aveia", quantity=20, unit="g")],
        ),
    )
    consolidator = ShoppingConsolidator()
    items = consolidator.consolidate(plan)
    assert len(items) == 1
    aveia = next(iter(items.values()))
    assert aveia.total_quantity == 50
    assert set(aveia.source_meals) == {"Café da manhã", "Lanche"}


def test_incompatible_units_are_not_summed():
    """
    100g e 2 unidades do "mesmo" alimento não devem virar 102.
    Mantém a primeira ocorrência e apenas registra a refeição adicional.
    """
    plan = make_plan(
        Meal(
            name="Almoço",
            items=[FoodItem(name="Queijo branco", quantity=100, unit="g")],
        ),
        Meal(
            name="Jantar",
            items=[FoodItem(name="Queijo branco", quantity=2, unit="Fatia(s)")],
        ),
    )
    consolidator = ShoppingConsolidator()
    items = consolidator.consolidate(plan)
    assert len(items) == 1
    queijo = next(iter(items.values()))
    assert queijo.total_quantity == 100
    assert queijo.unit_type == UnitType.WEIGHT_G
    assert "Jantar" in queijo.source_meals


def test_free_items_are_preserved_without_numeric_quantity():
    plan = make_plan(
        Meal(
            name="Ceia",
            items=[FoodItem(name="Chá de camomila", quantity=None, unit="À vontade")],
        )
    )
    calculator = ShoppingCalculator()
    items = calculator.calculate(plan, days=7)
    assert len(items) == 1
    cha = items[0]
    assert cha.unit_type == UnitType.FREE
    assert cha.total_quantity == 0
    assert cha.purchase_suggestion == "Compre a quantidade que preferir"


def test_items_are_grouped_by_category():
    plan = make_plan(
        Meal(
            name="Almoço",
            items=[
                FoodItem(name="Frango", quantity=100, unit="g"),
                FoodItem(name="Arroz", quantity=100, unit="g"),
                FoodItem(name="Alface", quantity=50, unit="g"),
                FoodItem(name="Produto inventado xyz", quantity=1, unit="unidade"),
            ],
        )
    )
    calculator = ShoppingCalculator(categorizer=FoodCategorizer())
    items = calculator.calculate(plan, days=1)
    by_name = {item.name: item.category for item in items}
    assert by_name["Frango"] == "proteínas"
    assert by_name["Arroz"] == "carboidratos"
    assert by_name["Alface"] == "verduras e legumes"
    assert by_name["Produto inventado xyz"] == "outros"
