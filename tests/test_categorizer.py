# tests/test_categorizer.py

"""Testes do FoodCategorizer isolado."""

from app.core.shopping.categorizer import FoodCategorizer


def test_known_categories_are_detected():
    categorizer = FoodCategorizer()
    assert categorizer.categorize("peito de frango") == "proteínas"
    assert categorizer.categorize("arroz branco") == "carboidratos"
    assert categorizer.categorize("banana prata") == "frutas"
    assert categorizer.categorize("brócolis") == "verduras e legumes"
    assert categorizer.categorize("leite integral") == "laticínios"
    assert categorizer.categorize("azeite de oliva") == "gorduras"
    assert categorizer.categorize("Whey protein") == "suplementos"
    assert categorizer.categorize("Creatina monohidratada") == "suplementos"


def test_unknown_food_falls_back_to_outros():
    categorizer = FoodCategorizer()
    assert categorizer.categorize("xyz-alimento-inexistente") == "outros"


def test_categorization_is_case_insensitive():
    categorizer = FoodCategorizer()
    assert categorizer.categorize("FRANGO") == "proteínas"
