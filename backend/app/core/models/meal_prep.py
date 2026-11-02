# backend/app/core/models/meal_prep.py

"""
meal_prep.py

Modelos de saída do Meal Prep: o plano de preparo das refeições (o que
cozinhar e o que apenas montar) produzido por ``app.core.mealprep`` e
consumido pelos serviços e rotas da API.

Mantidos separados da lista de compras (``shopping_list.py``) porque
representam outro conceito: não é o que o usuário precisa comprar, e sim
o que precisa preparar para as marmitas e lanches de N dias.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.core.models.shopping_list import CookingFactorInfo, UnitType


class RecipeLink(BaseModel):
    """Link para uma receita da internet, sugerida como alternativa."""

    title: str
    url: str
    source: str = ""


class MealPrepBreakdown(BaseModel):
    """Contribuição de uma refeição (ou pessoa) para o total de um item."""

    meal_name: str
    total_quantity: float
    total_text: str
    per_portion_quantity: Optional[float] = None
    per_portion_text: str = ""


class MealPrepItem(BaseModel):
    """
    Alimento que precisa ser cozinhado.

    Attributes:
        total_quantity: Quantidade a cozinhar, para N dias. Em peso, é o
            peso cru quando há fator de cocção (arredondado para cima, em
            gramas inteiras); caso contrário, a quantidade da dieta.
        cooked_quantity: Peso cozido esperado, quando há fator de cocção.
        per_portion_quantity: Quantidade por porção (um dia), no estado em
            que será consumida (cozida quando há fator).
        cooking_factor: Fator de cocção usado, com fonte e confiança.
        instruction: Preparo mais simples em uma linha.
        steps: O mesmo preparo, passo a passo.
        links: Outras sugestões de receitas (páginas da internet).
        warnings: Avisos sobre limites do cálculo (ex.: sem fator).
        breakdown: Contribuição por refeição, quando o item aparece em
            mais de uma refeição selecionada.
    """

    name: str
    category: str = "outros"
    unit: str
    unit_type: UnitType
    total_quantity: float
    total_text: str
    cooked_quantity: Optional[float] = None
    cooked_text: str = ""
    per_portion_quantity: Optional[float] = None
    per_portion_text: str = ""
    cooking_factor: Optional[CookingFactorInfo] = None
    method: Optional[str] = None
    method_label: Optional[str] = None
    instruction: str = ""
    steps: list[str] = Field(default_factory=list)
    links: list[RecipeLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_meals: list[str] = Field(default_factory=list)
    breakdown: list[MealPrepBreakdown] = Field(default_factory=list)


class MealPrepAssemblyItem(BaseModel):
    """Alimento que não precisa ser cozinhado, só porcionado e montado."""

    name: str
    unit: str
    unit_type: UnitType
    total_quantity: float
    total_text: str
    per_portion_quantity: Optional[float] = None
    per_portion_text: str = ""


class MealPrepAssembly(BaseModel):
    """Montagem de uma refeição com os itens que não vão ao fogo."""

    meal_name: str
    instruction: str
    has_cooked_items: bool = False
    items: list[MealPrepAssemblyItem] = Field(default_factory=list)
    links: list[RecipeLink] = Field(default_factory=list)


class MealPrepPlan(BaseModel):
    """Plano de preparo completo para N dias de uma seleção de refeições."""

    days: int
    meals: list[str] = Field(default_factory=list)
    cook_items: list[MealPrepItem] = Field(default_factory=list)
    assembly: list[MealPrepAssembly] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
