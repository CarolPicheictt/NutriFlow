# backend/app/core/shopping/consolidator.py

"""
consolidator.py

Normalização de nomes e consolidação de alimentos duplicados.

Isolado do ``ShoppingCalculator`` para manter responsabilidade única:
este módulo só sabe como decidir se dois ``FoodItem`` representam "o mesmo
alimento" e como somar suas quantidades (para 1 dia de dieta). Escalonar
para N dias, categorizar e gerar sugestões de compra são responsabilidades
de outras classes.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.core.models.diet_plan import DietPlan, FoodItem
from app.core.models.shopping_list import ShoppingItem, UnitType
from app.core.shopping.units import UnitNormalizer


class FoodNameNormalizer:
    """
    Normaliza nomes de alimentos para permitir deduplicação.

    Problema: o mesmo alimento pode aparecer com nomes ligeiramente
    diferentes no plano alimentar:
        "Arroz branco cozido"
        "Arroz branco"
        "Feijão Preto (Pronto Light)"
        "Feijão Preto"

    Estratégia MVP: lowercase + remoção de espaços extras + remoção de
    qualificadores comuns. Para v2, considerar stemming ou embedding
    semântico — propositalmente fora do escopo aqui.
    """

    # Qualificadores que não identificam o alimento em si.
    _QUALIFIERS = {
        "cozido", "cozida", "assado", "assada", "desfiado",
        "desfiada", "integral", "light", "natural", "caseiro",
        "caseira", "coado", "pronto",
    }

    def normalize(self, name: str) -> str:
        """
        Normaliza o nome de um alimento removendo qualificadores,
        espaços extras e padronizando capitalização.

        Args:
            name: Nome bruto do alimento, conforme veio do plano alimentar.

        Returns:
            Nome normalizado em lowercase, sem espaços extras e sem
            qualificadores simples.

        Note:
            Esta é uma implementação MVP intencional. Não faz stemming
            complexo nem inteligência semântica.
        """
        # Colapsa espaços extras (múltiplos espaços, tabs) antes de dividir
        # em palavras, para não gerar tokens vazios.
        words = name.lower().strip().split()
        normalized = [w for w in words if w not in self._QUALIFIERS]
        return " ".join(normalized)


class ShoppingConsolidator:
    """
    Extrai os alimentos de um ``DietPlan`` e consolida os que são iguais.

    "Iguais" aqui significa: mesmo nome normalizado. Alimentos com o mesmo
    nome normalizado, mas com unidades de tipos incompatíveis (ex.: "100 g"
    de um lado e "2 unidades" de outro), **não** têm suas quantidades
    somadas — o comportamento é manter a primeira unidade encontrada e
    ignorar a quantidade das ocorrências seguintes com tipo incompatível,
    registrando-as apenas em ``source_meals`` para rastreabilidade. Isso é
    intencional e documentado aqui para não gerar somas sem sentido do tipo
    "100 g + 2 unidades = 102".

    Uso:
        consolidator = ShoppingConsolidator(UnitNormalizer())
        itens = consolidator.consolidate(diet_plan)
    """

    def __init__(self, unit_normalizer: UnitNormalizer | None = None) -> None:
        self._unit_normalizer = unit_normalizer or UnitNormalizer()
        self._name_normalizer = FoodNameNormalizer()

    def consolidate(
        self,
        diet_plan: DietPlan,
        meal_names: Optional[Iterable[str]] = None,
    ) -> dict[str, ShoppingItem]:
        """
        Percorre as refeições do plano e consolida alimentos iguais.

        Alimentos sem nome são ignorados. Também são ignorados itens que na
        verdade são um resumo nutricional de uma refeição capturado por
        engano como se fosse um alimento (ver ``_is_nutrient_summary_row``)
        — um problema conhecido do parser do WebDiet, onde uma linha como
        "Almoço 42.2g 20.1g 63.5g" aparece com ``unit="Kcal"`` dentro de
        outra refeição. Calorias não são algo que se compra, então nunca
        deveriam virar item da lista de compras.

        As quantidades somadas aqui representam sempre 1 dia de dieta — o
        escalonamento para N dias é responsabilidade do
        ``ShoppingCalculator``.

        Args:
            diet_plan: Plano alimentar completo (representa 1 dia).
            meal_names: Quando informado, restringe o cálculo às refeições
                com esse nome (ex.: apenas "Café da manhã" e "Pré-treino").
                ``None`` ou vazio inclui todas as refeições do plano.

        Returns:
            Dicionário com o nome normalizado como chave e o
            ``ShoppingItem`` consolidado (ainda não escalonado) como valor.
        """
        selected_meals = set(meal_names) if meal_names else None
        consolidated: dict[str, ShoppingItem] = {}

        for meal in diet_plan.meals:
            if selected_meals is not None and meal.name not in selected_meals:
                continue
            for item in meal.items:
                if not item.name or not item.name.strip():
                    continue
                if self._is_nutrient_summary_row(item):
                    continue
                self._merge_item(consolidated, item, meal.name)

        return consolidated

    @staticmethod
    def _is_nutrient_summary_row(food_item: FoodItem) -> bool:
        """
        Detecta um item que na verdade é um resumo nutricional de refeição
        (nome da refeição + macros), não um alimento comprável.

        O sinal é a unidade: "Kcal" nunca é algo que se compra no mercado.
        Qualquer item vindo do parser com essa unidade é descartado, não
        importa o nome — inclusive quando o nome contém o de uma refeição
        (ex.: "Almoço 42.2g 20.1g 63.5g", "Total das refeições ...").
        """
        unit = (food_item.unit or "").strip().lower()
        return unit == "kcal"

    def _merge_item(
        self,
        consolidated: dict[str, ShoppingItem],
        food_item: FoodItem,
        meal_name: str,
    ) -> None:
        """
        Mescla um único ``FoodItem`` no dicionário de itens consolidados.

        Args:
            consolidated: Dicionário acumulador, alterado in-place.
            food_item: Alimento extraído de uma refeição.
            meal_name: Nome da refeição de origem, para rastreabilidade.
        """
        norm_name = self._name_normalizer.normalize(food_item.name)
        unit_type = self._unit_normalizer.classify(food_item.unit)

        existing = consolidated.get(norm_name)

        # Itens "à vontade" não recebem quantidade numérica.
        if unit_type == UnitType.FREE:
            if existing is None:
                consolidated[norm_name] = ShoppingItem(
                    name=food_item.name,
                    total_quantity=0,
                    unit="à vontade",
                    unit_type=UnitType.FREE,
                    source_meals=[meal_name],
                    normalized_name=norm_name,
                )
            elif meal_name not in existing.source_meals:
                existing.source_meals.append(meal_name)
            return

        qty = food_item.quantity or 0
        base_qty = self._unit_normalizer.to_base_unit(qty, food_item.unit or "")

        if existing is None:
            consolidated[norm_name] = ShoppingItem(
                name=food_item.name,
                total_quantity=base_qty,
                unit=self._unit_normalizer.resolve_display_unit(
                    unit_type, food_item.unit
                ),
                unit_type=unit_type,
                source_meals=[meal_name],
                normalized_name=norm_name,
            )
            return

        if existing.unit_type != unit_type:
            # Tipos incompatíveis (ex.: peso vs. unidade) não são somados.
            # Mantemos o item já existente e apenas registramos a refeição,
            # para não produzir uma soma sem sentido.
            if meal_name not in existing.source_meals:
                existing.source_meals.append(meal_name)
            return

        existing.total_quantity += base_qty
        if meal_name not in existing.source_meals:
            existing.source_meals.append(meal_name)