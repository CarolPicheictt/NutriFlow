# backend/app/core/shopping/calculator.py

"""
calculator.py

Engine de cálculo da lista de compras inteligente.
Recebe um DietPlan e retorna os itens consolidados
com quantidades para N dias de dieta.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

#from app.core.models.diet_plan import DietPlan, FoodItem
from scrap_do_pdf import DietPlan, FoodItem


class UnitType(str, Enum):
    """
    Classifica o tipo de unidade de medida de um alimento.
    Usada para determinar a estratégia de consolidação.
    """
    WEIGHT_G = "weight_g"        # gramas
    VOLUME_ML = "volume_ml"      # mililitros
    UNIT = "unit"                # unidades (ovos, bananas)
    FREE = "free"                # "à vontade"
    UNKNOWN = "unknown"


@dataclass
class ShoppingItem:
    """
    Item consolidado da lista de compras.

    Attributes:
        name: Nome normalizado do alimento.
        total_quantity: Quantidade total calculada para N dias.
        unit: Unidade de medida normalizada.
        unit_type: Classificação do tipo de unidade.
        category: Categoria do alimento (proteína, carboidrato etc.).
        checked: Se o usuário já marcou como disponível em casa.
        source_meals: Refeições de onde o item foi extraído.
        purchase_suggestion: Texto de sugestão de compra
                             (ex: "2 dúzias de ovos").
    """
    name: str
    total_quantity: float
    unit: str
    unit_type: UnitType
    category: str = "outros"
    checked: bool = False
    source_meals: list[str] = field(default_factory=list)
    purchase_suggestion: Optional[str] = None


class UnitNormalizer:
    """
    Normaliza unidades de medida para permitir consolidação
    de um mesmo alimento com unidades diferentes.

    Exemplos:
        "Unidade(s)" → UnitType.UNIT
        "g"          → UnitType.WEIGHT_G
        "ml"         → UnitType.VOLUME_ML
        "À vontade"  → UnitType.FREE
    """

    _WEIGHT_KEYWORDS = {"g", "kg", "grama", "gramas"}
    _VOLUME_KEYWORDS = {"ml", "l", "litro", "litros", "xícara", "copo"}
    _UNIT_KEYWORDS = {"unidade", "unidades", "unidade(s)", "fatia", "fatias",
                      "colher", "colheres", "dosador", "dosadores"}

    def classify(self, unit: Optional[str]) -> UnitType:
        """
        Classifica o tipo de uma unidade de medida.

        Args:
            unit: String da unidade extraída do PDF.

        Returns:
            UnitType correspondente à unidade fornecida.
        """
        if not unit:
            return UnitType.UNKNOWN

        unit_lower = unit.lower().strip()

        if "vontade" in unit_lower:
            return UnitType.FREE
        if any(kw in unit_lower for kw in self._WEIGHT_KEYWORDS):
            return UnitType.WEIGHT_G
        if any(kw in unit_lower for kw in self._VOLUME_KEYWORDS):
            return UnitType.VOLUME_ML
        if any(kw in unit_lower for kw in self._UNIT_KEYWORDS):
            return UnitType.UNIT

        return UnitType.UNKNOWN

    def to_base_unit(self, quantity: float, unit: str) -> float:
        """
        Converte quantidade para unidade base (gramas ou ml).
        Útil para consolidar "150g" + "0.15kg" do mesmo item.

        Args:
            quantity: Valor numérico da quantidade.
            unit: String da unidade.

        Returns:
            Quantidade na unidade base.
        """
        unit_lower = (unit or "").lower()
        if "kg" in unit_lower:
            return quantity * 1000
        if unit_lower in {"l", "litro", "litros"}:
            return quantity * 1000
        return quantity


class FoodNameNormalizer:
    """
    Normaliza nomes de alimentos para permitir deduplicação.

    Problema: o mesmo alimento pode aparecer com nomes ligeiramente
    diferentes no PDF:
        "Arroz branco cozido"
        "Arroz branco"
        "Feijão Preto (Pronto Light)"
        "Feijão Preto"

    Estratégia MVP: normalização por stemming simples e
    remoção de qualificadores comuns. Para v2, usar
    embedding semântico.
    """

    # Qualificadores que não identificam o alimento em si
    _QUALIFIERS = {
        "cozido", "cozida", "assado", "assada", "desfiado",
        "desfiada", "integral", "light", "natural", "caseiro",
        "caseira", "coado", "pronto",
    }

    def normalize(self, name: str) -> str:
        """
        Normaliza o nome de um alimento removendo qualificadores
        e padronizando capitalização.

        Args:
            name: Nome bruto do alimento extraído do PDF.

        Returns:
            Nome normalizado em lowercase sem qualificadores.

        Note:
            Esta é uma implementação MVP intencional.
            Para produção, considerar modelo de NLP ou
            tabela de equivalências curada manualmente.
        """
        words = name.lower().strip().split()
        normalized = [w for w in words if w not in self._QUALIFIERS]
        return " ".join(normalized)


class ShoppingCalculator:
    """
    Engine principal de cálculo da lista de compras.

    Responsabilidades:
        1. Extrair todos os alimentos do DietPlan
        2. Normalizar nomes e unidades
        3. Consolidar duplicatas somando quantidades
        4. Escalonar para N dias
        5. Gerar sugestão de compra humanizada

    Uso:
        calculator = ShoppingCalculator()
        items = calculator.calculate(diet_plan, days=7)
    """

    def __init__(self) -> None:
        self._unit_normalizer = UnitNormalizer()
        self._name_normalizer = FoodNameNormalizer()

    def calculate(
        self,
        diet_plan: DietPlan,
        days: int = 7,
    ) -> list[ShoppingItem]:
        """
        Calcula a lista de compras consolidada para N dias.

        Pipeline:
            1. Extrai itens de todas as refeições
            2. Normaliza nomes e unidades
            3. Consolida por alimento (soma quantidades)
            4. Escala para N dias
            5. Gera sugestões de compra

        Args:
            diet_plan: Plano alimentar parseado.
            days: Número de dias para calcular (padrão: 7).

        Returns:
            Lista de ShoppingItem ordenada por categoria.
        """
        raw_items = self._extract_all_items(diet_plan)
        consolidated = self._consolidate(raw_items)
        scaled = self._scale(consolidated, days)
        enriched = self._enrich_suggestions(scaled)

        return sorted(enriched, key=lambda x: (x.category, x.name))

    def _extract_all_items(
        self,
        diet_plan: DietPlan,
    ) -> list[tuple[str, FoodItem, str]]:
        """
        Extrai todos os FoodItems de todas as refeições,
        incluindo nome da refeição de origem para rastreabilidade.

        Args:
            diet_plan: Plano alimentar completo.

        Returns:
            Lista de tuplas (nome_normalizado, food_item, nome_refeição).
        """
        result: list[tuple[str, FoodItem, str]] = []

        for meal in diet_plan.meals:
            for item in meal.items:
                if not item.name:
                    continue
                normalized_name = self._name_normalizer.normalize(item.name)
                result.append((normalized_name, item, meal.name))

        return result

    def _consolidate(
        self,
        raw_items: list[tuple[str, FoodItem, str]],
    ) -> dict[str, ShoppingItem]:
        """
        Consolida alimentos iguais somando suas quantidades.

        Quando o mesmo alimento aparece em refeições diferentes
        (ex: ovo no café e no almoço), as quantidades são somadas
        e as refeições de origem são registradas.

        Args:
            raw_items: Lista de itens extraídos com nomes normalizados.

        Returns:
            Dicionário com nome normalizado como chave e
            ShoppingItem consolidado como valor.
        """
        consolidated: dict[str, ShoppingItem] = {}

        for norm_name, food_item, meal_name in raw_items:
            unit_type = self._unit_normalizer.classify(food_item.unit)

            # Itens "à vontade" não entram no cálculo de quantidade
            if unit_type == UnitType.FREE:
                if norm_name not in consolidated:
                    consolidated[norm_name] = ShoppingItem(
                        name=food_item.name,
                        total_quantity=0,
                        unit="À vontade",
                        unit_type=UnitType.FREE,
                        source_meals=[meal_name],
                    )
                continue

            qty = food_item.quantity or 0
            base_qty = self._unit_normalizer.to_base_unit(
                qty, food_item.unit or ""
            )

            if norm_name in consolidated:
                existing = consolidated[norm_name]
                existing.total_quantity += base_qty
                if meal_name not in existing.source_meals:
                    existing.source_meals.append(meal_name)
            else:
                consolidated[norm_name] = ShoppingItem(
                    name=food_item.name,
                    total_quantity=base_qty,
                    unit=self._resolve_unit(unit_type, food_item.unit),
                    unit_type=unit_type,
                    source_meals=[meal_name],
                )

        return consolidated

    def _scale(
        self,
        consolidated: dict[str, ShoppingItem],
        days: int,
    ) -> list[ShoppingItem]:
        """
        Multiplica todas as quantidades pelo número de dias.

        O DietPlan representa 1 dia de dieta.
        Para 7 dias, todas as quantidades são × 7.

        Args:
            consolidated: Itens consolidados de 1 dia.
            days: Número de dias desejados.

        Returns:
            Lista de ShoppingItem com quantidades escalonadas.
        """
        scaled: list[ShoppingItem] = []

        for item in consolidated.values():
            if item.unit_type != UnitType.FREE:
                item.total_quantity = round(item.total_quantity * days, 1)
            scaled.append(item)

        return scaled

    def _enrich_suggestions(
        self,
        items: list[ShoppingItem],
    ) -> list[ShoppingItem]:
        """
        Gera sugestões de compra humanizadas para cada item.

        Transforma quantidades brutas em sugestões práticas
        para o momento da compra:
            - 420g de frango → "~500g (1 bandeja)"
            - 14 unidades de ovos → "14 unidades (1 dúzia + 2)"

        Args:
            items: Lista de ShoppingItem escalonados.

        Returns:
            Lista com campo purchase_suggestion preenchido.
        """
        for item in items:
            item.purchase_suggestion = self._generate_suggestion(item)
        return items

    def _generate_suggestion(self, item: ShoppingItem) -> Optional[str]:
        """
        Gera o texto de sugestão de compra para um item específico.

        Args:
            item: ShoppingItem com quantidade e unidade definidos.

        Returns:
            String com sugestão humanizada, ou None para itens
            sem quantidade definida.
        """
        if item.unit_type == UnitType.FREE:
            return "Compre a quantidade que preferir"

        qty = item.total_quantity

        if item.unit_type == UnitType.UNIT:
            dozens = int(qty // 12)
            remainder = int(qty % 12)
            # Sugestão especial para ovos (produto mais comum em dúzia)
            if "ovo" in item.name.lower() and dozens > 0:
                extra = f" + {remainder}" if remainder else ""
                return f"{int(qty)} unidades ({dozens} dúzia{extra})"
            return f"{int(qty)} unidades"

        if item.unit_type == UnitType.WEIGHT_G:
            if qty >= 1000:
                return f"{qty/1000:.1f}kg"
            # Arredonda para a embalagem comercial mais próxima
            rounded = self._round_to_package(qty)
            return f"~{rounded}g"

        if item.unit_type == UnitType.VOLUME_ML:
            if qty >= 1000:
                return f"{qty/1000:.1f}L"
            return f"{qty:.0f}ml"

        return f"{qty} {item.unit}"

    @staticmethod
    def _round_to_package(grams: float) -> int:
        """
        Arredonda gramas para o tamanho de embalagem comercial
        mais próximo e suficiente.

        Tamanhos comuns: 250g, 500g, 1000g, 1500g, 2000g

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

    @staticmethod
    def _resolve_unit(unit_type: UnitType, original_unit: Optional[str]) -> str:
        """
        Retorna a unidade canônica para exibição ao usuário.

        Args:
            unit_type: Tipo classificado da unidade.
            original_unit: Unidade original extraída do PDF.

        Returns:
            String da unidade para exibição.
        """
        unit_map = {
            UnitType.WEIGHT_G: "g",
            UnitType.VOLUME_ML: "ml",
            UnitType.UNIT: "un",
            UnitType.FREE: "à vontade",
        }
        return unit_map.get(unit_type, original_unit or "")