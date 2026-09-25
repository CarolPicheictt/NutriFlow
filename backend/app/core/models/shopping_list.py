# backend/app/core/models/shopping_list.py

"""
shopping_list.py

Modelos de saída da lista de compras inteligente: o resultado produzido
pelo núcleo de cálculo (``app.core.shopping``) e consumido pelos serviços
e pelas rotas da API.

Mantidos separados do plano alimentar (``diet_plan.py``) porque representam
um conceito diferente: não é o que o nutricionista prescreveu, e sim o que
o paciente precisa comprar.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UnitType(str, Enum):
    """
    Classifica o tipo de unidade de medida de um alimento.

    Usada para decidir como consolidar quantidades (não faz sentido somar
    "2 unidades" com "100 g" do mesmo alimento) e como gerar a sugestão de
    compra.
    """

    WEIGHT_G = "weight_g"  # gramas (após conversão de kg)
    VOLUME_ML = "volume_ml"  # mililitros (após conversão de litros)
    UNIT = "unit"  # unidades (ovos, bananas, fatias, colheres...)
    FREE = "free"  # "à vontade" — sem quantidade numérica
    UNKNOWN = "unknown"  # unidade não reconhecida


class ShoppingItem(BaseModel):
    """
    Item consolidado da lista de compras.

    Attributes:
        name: Nome do alimento (forma de exibição, não normalizada).
        total_quantity: Quantidade total calculada para N dias. Sempre 0
            para itens "à vontade" (ver ``unit_type``).
        unit: Unidade de medida canônica para exibição (ex.: "g", "ml",
            "un", "à vontade").
        unit_type: Classificação do tipo de unidade, usada para saber como
            interpretar ``total_quantity``.
        category: Categoria do alimento (proteínas, carboidratos etc.).
        checked: Se o usuário já marcou este item como disponível em casa.
        source_meals: Nomes das refeições de onde o item foi extraído.
        purchase_suggestion: Texto de sugestão de compra humanizada
            (ex.: "42 unidades (3 dúzias + 6)").
    """

    name: str
    total_quantity: float
    unit: str
    unit_type: UnitType
    category: str = "outros"
    checked: bool = False
    source_meals: list[str] = Field(default_factory=list)
    purchase_suggestion: Optional[str] = None
    # Chave de deduplicação interna (ver FoodNameNormalizer). Não faz parte
    # do contrato da API (exclude=True): serve apenas para o checklist
    # localizar o item certo sem depender do nome de exibição, que pode
    # variar em acentuação/capitalização entre refeições.
    normalized_name: str = Field(default="", exclude=True)
