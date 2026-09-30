"""Testes do fluxo principal do parser WebDiet em PDF."""

from pathlib import Path

from scrap_do_pdf import MealParser, WebDietParser


PDF_FIXTURE = Path(__file__).parent / "Plano alimentar - Carolina Picheictt.pdf"


def test_parser_ignores_non_meal_sections_but_keeps_meals():
    diet_plan = WebDietParser(PDF_FIXTURE).parse()

    assert len(diet_plan.meals) == 7
    assert diet_plan.nutritional_summary.macros.proteins_g is None
    assert diet_plan.nutritional_summary.macros.lipids_g is None
    assert diet_plan.nutritional_summary.macros.carbs_g is None
    assert diet_plan.shopping_list == []
    assert diet_plan.recipes == []


def test_substitutions_split_alternatives_and_stop_before_recipes():
    text = """12:00 - Almoço
Arroz branco cozido 150g
Opções de substituição para Arroz Branco:
Batata inglesa - 280g - ou - Macarrão cozido - 160g - ou - Abóbora assada - 300g
Opções de substituição para Peito de frango sem pele grelhado:
Acém - 60g - ou - Lagarto - 60g - ou - Patinho grelhado - 60g - ou - Tilápia - 120g - ou - Coxão mole - 60g - ou- Músculo bovino - 100g - ou - Maminha - 90g - ou - Sobrecoxa de frango sem pele assada - 60g - ou - Lombo
suíno - 60g
Observações:
Chocolates até 120kcal
Relatório de nutrientes
Receita culinária
Ingredientes:
Farinha de trigo - 100g
"""

    meal = MealParser().parse(text)[0]

    assert [item.name for item in meal.substitutions] == [
        "Batata inglesa",
        "Macarrão cozido",
        "Abóbora assada",
        "Acém",
        "Lagarto",
        "Patinho grelhado",
        "Tilápia",
        "Coxão mole",
        "Músculo bovino",
        "Maminha",
        "Sobrecoxa de frango sem pele assada",
        "Lombo suíno",
    ]
    assert meal.substitutions[0].raw_quantity == "280g"
    assert meal.substitutions[-1].raw_quantity == "60g"
    assert [item.name for item in meal.items] == ["Arroz branco cozido"]