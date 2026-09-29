# backend/app/core/shopping/calculator.py

"""
calculator.py

Engine de cálculo da lista de compras inteligente.
Recebe um ``DietPlan`` e retorna os itens consolidados com quantidades
para N dias de dieta, categorizados e com sugestão de compra.

Este módulo é o orquestrador: a normalização de nomes e a consolidação de
duplicatas vivem em ``consolidator.py``, a classificação/conversão de
unidades vive em ``units.py`` e o agrupamento por categoria vive em
``categorizer.py``. Isso mantém cada peça com responsabilidade única e
fácil de evoluir isoladamente.
"""

from __future__ import annotations

from typing import Optional

from app.core.models.diet_plan import DietPlan
from app.core.models.shopping_list import ShoppingItem, UnitType
from app.core.shopping.categorizer import FoodCategorizer
from app.core.shopping.consolidator import FoodNameNormalizer, ShoppingConsolidator
from app.core.shopping.units import UnitNormalizer

__all__ = [
    "ShoppingCalculator",
    "ShoppingItem",
    "UnitType",
    "UnitNormalizer",
    "FoodNameNormalizer",
]


class ShoppingCalculator:
    """
    Engine principal de cálculo da lista de compras.

    Responsabilidades:
        1. Consolidar os alimentos do ``DietPlan`` (via ``ShoppingConsolidator``)
        2. Escalonar as quantidades consolidadas para N dias
        3. Categorizar cada item (via ``FoodCategorizer``)
        4. Gerar uma sugestão de compra humanizada por item
        5. Retornar os itens ordenados por categoria e nome

    Uso:
        calculator = ShoppingCalculator()
        items = calculator.calculate(diet_plan, days=7)
    """

    def __init__(
        self,
        unit_normalizer: Optional[UnitNormalizer] = None,
        categorizer: Optional[FoodCategorizer] = None,
        consolidator: Optional[ShoppingConsolidator] = None,
    ) -> None:
        self._unit_normalizer = unit_normalizer or UnitNormalizer()
        self._categorizer = categorizer or FoodCategorizer()
        self._consolidator = consolidator or ShoppingConsolidator(
            self._unit_normalizer
        )

    def calculate(
        self,
        diet_plan: DietPlan,
        days: int = 7,
        meal_names: Optional[list[str]] = None,
        leftovers_grams: Optional[dict[str, float]] = None,
    ) -> list[ShoppingItem]:
        """
        Calcula a lista de compras consolidada para N dias.

        Pipeline:
            1. Extrai e consolida os itens das refeições selecionadas (1 dia)
            2. Escala as quantidades para N dias
            3. Categoriza cada item
            4. Gera sugestões de compra
            5. Ordena por categoria e nome

        Args:
            diet_plan: Plano alimentar parseado (representa 1 dia).
            days: Número de dias para calcular (padrão: 7).
            meal_names: Quando informado, calcula a lista apenas com os
                alimentos das refeições listadas (ex.: ``["Café da manhã",
                "Pré-treino"]``). ``None`` considera todas as refeições.

        Returns:
            Lista de ``ShoppingItem`` ordenada por categoria e nome.
        """
        consolidated = self._consolidator.consolidate(diet_plan, meal_names)
        scaled = self._scale(consolidated, days)
        scaled = self._subtract_leftovers(scaled, leftovers_grams or {})
        categorized = self._categorize(scaled)
        enriched = self._enrich_suggestions(categorized)

        return sorted(enriched, key=lambda item: (item.category, item.name))

    @staticmethod
    def _subtract_leftovers(
        items: list[ShoppingItem], leftovers_grams: dict[str, float]
    ) -> list[ShoppingItem]:
        for item in items:
            if item.unit_type == UnitType.WEIGHT_G:
                leftover = leftovers_grams.get(item.name, 0.0)
                item.total_quantity = round(max(0.0, item.total_quantity - leftover), 1)

        return items

    def _scale(
        self,
        consolidated: dict[str, ShoppingItem],
        days: int,
    ) -> list[ShoppingItem]:
        """
        Multiplica todas as quantidades pelo número de dias.

        O ``DietPlan`` representa 1 dia de dieta. Para 7 dias, todas as
        quantidades (exceto itens "à vontade") são multiplicadas por 7.

        Args:
            consolidated: Itens consolidados de 1 dia.
            days: Número de dias desejados.

        Returns:
            Lista de ``ShoppingItem`` com quantidades escalonadas.
        """
        scaled: list[ShoppingItem] = []

        for item in consolidated.values():
            if item.unit_type != UnitType.FREE:
                item.total_quantity = round(item.total_quantity * days, 1)
            scaled.append(item)

        return scaled

    def _categorize(self, items: list[ShoppingItem]) -> list[ShoppingItem]:
        """
        Atribui uma categoria a cada item da lista.

        A categorização usa o nome de exibição do item (não o nome
        normalizado internamente), em lowercase, o que é suficiente para
        a correspondência por palavra-chave do MVP.

        Args:
            items: Itens escalonados, ainda sem categoria definitiva.

        Returns:
            A mesma lista, com o campo ``category`` preenchido.
        """
        for item in items:
            item.category = self._categorizer.categorize(item.name)
        return items

    def _enrich_suggestions(
        self,
        items: list[ShoppingItem],
    ) -> list[ShoppingItem]:
        """
        Gera sugestões de compra humanizadas para cada item.

        Transforma quantidades brutas em sugestões práticas para o momento
        da compra:
            - 420 g de frango → "~500g"
            - 42 unidades de ovos → "42 unidades (3 dúzias + 6)"

        Args:
            items: Lista de ``ShoppingItem`` escalonados e categorizados.

        Returns:
            A mesma lista, com o campo ``purchase_suggestion`` preenchido.
        """
        for item in items:
            item.purchase_suggestion = self._generate_suggestion(item)
        return items

    def _generate_suggestion(self, item: ShoppingItem) -> Optional[str]:
        """
        Gera o texto de sugestão de compra para um item específico.

        Args:
            item: ``ShoppingItem`` com quantidade e unidade definidos.

        Returns:
            String com sugestão humanizada, ou ``None`` quando não houver
            unidade reconhecida o suficiente para gerar uma sugestão.
        """
        if item.unit_type == UnitType.FREE:
            return "Compre a quantidade que preferir"

        qty = item.total_quantity

        if item.unit_type == UnitType.UNIT:
            dozens = int(qty // 12)
            remainder = int(qty % 12)
            # Sugestão especial para ovos (produto mais comum em dúzia).
            if "ovo" in item.name.lower() and dozens > 0:
                extra = f" + {remainder}" if remainder else ""
                return f"{int(qty)} unidades ({dozens} dúzia{extra})"
            unit_label = item.unit or "unidades"
            if unit_label == "fatias":
                unit_label = "fatia" if qty == 1 else "fatias"
            elif unit_label == "un":
                unit_label = "unidade" if qty == 1 else "unidades"
            return f"{int(qty)} {unit_label}"

        if item.unit_type == UnitType.WEIGHT_G:
            if qty <= 0:
                return None
            if item.category == "suplementos":
                return self._supplement_package_suggestion(qty)
            if self._is_meat(item.name):
                packages = max(1, int((qty + 499) // 500))
                package_weight = packages * 500
                package_text = UnitNormalizer.format_weight_quantity(package_weight)
                package_label = "pacote" if packages == 1 else "pacotes"
                return f"{packages} {package_label} (~{package_text})"
            if qty >= 1000:
                return UnitNormalizer.format_weight_quantity(qty)
            # Arredonda para a embalagem comercial mais próxima.
            rounded = self._round_to_package(qty)
            return f"~{UnitNormalizer.format_weight_quantity(rounded)}"

        if item.unit_type == UnitType.VOLUME_ML:
            if qty >= 1000:
                return f"{qty / 1000:.1f}L"
            return f"{qty:.0f}ml"

        return f"{qty} {item.unit}" if item.unit else None

    @staticmethod
    def _is_meat(name: str) -> bool:
        meat_keywords = (
            "frango", "sobrecoxa", "peito", "carne", "boi", "patinho",
            "acém", "acem", "peixe", "tilápia", "tilapia", "salmão",
            "salmao", "atum", "sardinha", "peru", "linguiça", "linguica",
            "bacon", "camarão", "camarao", "suíno", "suino", "porco",
            "costela",
        )
        name_lower = name.lower()
        return any(keyword in name_lower for keyword in meat_keywords)

    @staticmethod
    def _supplement_package_suggestion(quantity: float) -> str:
        package_sizes = (
            (4500, "pacote atacado de 4,5kg"),
            (2000, "pacote família de 2kg"),
            (900, "pacote intermediário de 900g"),
            (500, "pacote pequeno de 500g"),
            (30, "sachê individual de 30g"),
        )
        if quantity <= 4500:
            size, label = next((size, label) for size, label in reversed(package_sizes) if quantity <= size)
            return f"1 {label}"

        bulk_count = int(quantity // 4500)
        remainder = quantity - bulk_count * 4500
        parts = [f"{bulk_count} pacotes atacado de 4,5kg"]
        if remainder > 0:
            size, label = next((size, label) for size, label in reversed(package_sizes) if remainder <= size)
            parts.append(f"1 {label}")
        return " + ".join(parts)

    @staticmethod
    def _round_to_package(grams: float) -> int:
        """
        Arredonda gramas para o tamanho de embalagem comercial mais
        próximo e suficiente.

        Tamanhos comuns considerados: 250 g, 500 g, 1000 g, 1500 g, 2000 g,
        3000 g, 5000 g.

        Args:
            grams: Quantidade em gramas a ser arredondada.

        Returns:
            Tamanho de embalagem sugerido em gramas.
        """
        packages = [250, 500, 1000, 1500, 2000, 3000, 5000]
        for pkg in packages:
            if grams <= pkg:
                return pkg
        return int(grams * 1.1)  # +10% de margem se ultrapassar todos