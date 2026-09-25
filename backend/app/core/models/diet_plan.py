# backend/app/core/models/diet_plan.py

"""
diet_plan.py

Modelos canônicos do plano alimentar usados por todo o núcleo do NutriFlow.

O parser do WebDiet (``scrap_do_pdf.py``, na raiz do repositório) já define
esses modelos e é tratado como uma dependência externa ao MVP da lista de
compras. Em vez de duplicar as estruturas de dados aqui, este módulo apenas
reexporta os modelos canônicos, para que:

    - o núcleo de compras (``app.core.shopping``) dependa de um caminho de
      import estável (``app.core.models.diet_plan``), independente de onde o
      parser realmente vive;
    - o parser possa evoluir, ser movido para
      ``app/core/parser/webdiet_parser.py`` ou ser substituído por uma
      futura integração via API do WebDiet, sem quebrar o núcleo de compras.

Qualquer alimento recebido pela API (upload de JSON, entrada manual, PDF no
futuro) deve ser normalizado para os tipos abaixo antes de chegar ao
``ShoppingCalculator``.
"""

from __future__ import annotations
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrap_do_pdf import (
    DataSource,
    DietPlan,
    FoodItem,
    MacroNutrients,
    Meal,
    MealNutrients,
    NutritionalSummary,
    PatientInfo,
    Recipe,
    RecipeIngredient,
)

__all__ = [
    "DataSource",
    "DietPlan",
    "FoodItem",
    "MacroNutrients",
    "Meal",
    "MealNutrients",
    "NutritionalSummary",
    "PatientInfo",
    "Recipe",
    "RecipeIngredient",
]
