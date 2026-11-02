# tests/test_meal_prep_catalog.py

"""Testes da base de preparo do Meal Prep (catálogo)."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import pytest

from app.core.mealprep.catalog import PreparationCatalog, normalize_text
from app.core.shopping.cooking import _load_factors

# Métodos da planilha que não geram instrução de preparo.
_METHODS_WITHOUT_STEPS = {"raw", "ready_to_eat", "brewing", "microwave_baking"}


@pytest.fixture(scope="module")
def catalog() -> PreparationCatalog:
    return PreparationCatalog.default()


@pytest.mark.parametrize(
    "name, food_id",
    [
        ("Peito de frango sem pele grelhado", "frango"),
        ("Frango Desfiado", "frango-desfiado"),
        ("Arroz Branco", "arroz"),
        ("Pão de Hambúrguer", "pao-tapioca"),
        ("Hambúrguer carne vaca", "carne-bovina"),
        ("Macarrão seco", "massas"),
        ("Melancia", "frutas"),
        ("Mel", "adocantes-pastas"),
        ("Maçã", "frutas"),
        ("Legumes e salada", "legumes"),
        ("Salada com sal e vinagre", "salada-crua"),
        ("Ovo de galinha", "ovo"),
        ("Iogurte natural caseiro", "iogurte-leite"),
        ("Feijão Preto", "feijao"),
        ("Couve-flor", "legumes"),
    ],
)
def test_find_food_matches_whole_words(catalog, name, food_id):
    assert catalog.find_food(name).id == food_id


def test_find_food_returns_none_for_unknown_food(catalog):
    assert catalog.find_food("Café sem açúcar") is None
    assert catalog.find_food("") is None


def test_every_cooking_method_in_the_workbook_has_steps(catalog):
    methods = {
        factor.cooking_method
        for factor in _load_factors()
        if factor.data_status != "not_applicable"
    } - _METHODS_WITHOUT_STEPS
    missing = {method for method in methods if catalog.get_method(method) is None}
    assert not missing


def test_steps_use_food_override_before_method_steps(catalog):
    rice = catalog.find_food("Arroz branco")
    assert catalog.steps_for(rice, "grilling") == list(rice.steps)


def test_steps_add_extra_steps_before_the_last_step(catalog):
    shredded = catalog.find_food("Frango desfiado")
    steps = catalog.steps_for(shredded, "boiling_braising")
    assert "desfie com dois garfos" in steps
    assert steps[-1].startswith("retire da água")


def test_steps_fall_back_to_the_default_method_of_the_food(catalog):
    legumes = catalog.find_food("Legumes")
    assert catalog.steps_for(legumes, None) == list(catalog.get_method("steaming").steps)


def test_links_are_https_pages_with_source_name(catalog):
    links = [
        link
        for name in ("Frango desfiado", "Arroz", "Legumes", "Ovo", "Iogurte", "Feijão", "Hambúrguer")
        for link in catalog.find_food(name).links
    ]
    assert links
    for link in links:
        assert urlparse(link.url).scheme == "https"
        assert link.source and not link.source.startswith("www.")


def test_assembly_template_falls_back_to_generic_one(catalog):
    assert "{itens}" in catalog.assembly_template("misture")
    assert catalog.assembly_template("verbo-inexistente") == catalog.assembly_template("junte")


def test_normalize_text_removes_accents_and_punctuation():
    assert normalize_text("Couve-flor (cozida)") == "couve flor cozida"


def test_invalid_file_raises_value_error(tmp_path):
    broken = tmp_path / "base.json"
    broken.write_text("{ não é json", encoding="utf-8")
    with pytest.raises(ValueError):
        PreparationCatalog.from_file(broken)


def test_unknown_default_method_is_rejected(tmp_path):
    base = {
        "methods": {"boiling": {"label": "x", "steps": ["a"]}},
        "assembly": {"junte": "{itens}", "marmita": "{itens}"},
        "foods": [{"id": "x", "keywords": ["x"], "mode": "cook", "default_method": "inexistente"}],
    }
    path = tmp_path / "base.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ValueError):
        PreparationCatalog.from_file(path)
