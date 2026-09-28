"""Testes do fluxo principal do parser WebDiet em PDF."""

from pathlib import Path

from scrap_do_pdf import WebDietParser


PDF_FIXTURE = Path(__file__).parent / "Plano alimentar - Carolina Picheictt.pdf"


def test_parser_ignores_non_meal_sections_but_keeps_meals():
    diet_plan = WebDietParser(PDF_FIXTURE).parse()

    assert len(diet_plan.meals) == 7
    assert diet_plan.nutritional_summary.macros.proteins_g is None
    assert diet_plan.nutritional_summary.macros.lipids_g is None
    assert diet_plan.nutritional_summary.macros.carbs_g is None
    assert diet_plan.shopping_list == []
    assert diet_plan.recipes == []