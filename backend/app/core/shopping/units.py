# backend/app/core/shopping/units.py

"""
units.py

Classificação e conversão de unidades de medida.

Separado do restante do ``core.shopping`` porque é usado tanto pelo
consolidador (para decidir se duas quantidades podem ser somadas) quanto
pelo calculador (para gerar sugestões de compra humanizadas).
"""

from __future__ import annotations

from typing import Optional

from app.core.models.shopping_list import UnitType


class UnitNormalizer:
    """
    Normaliza unidades de medida para permitir consolidação de um mesmo
    alimento expresso com unidades diferentes.

    Exemplos:
        "Unidade(s)" → UnitType.UNIT
        "g"          → UnitType.WEIGHT_G
        "ml"         → UnitType.VOLUME_ML
        "À vontade"  → UnitType.FREE

    Suporte inicial (MVP):
        Peso:      g, grama, gramas, kg
        Volume:    ml, l, litro, litros
        Unidade:   unidade, unidades, unidade(s), fatia, fatias,
                   colher, colheres, dosador
        Livre:     qualquer expressão contendo "à vontade"
        Desconhecida: qualquer outra unidade
    """

    _WEIGHT_KEYWORDS = {"g", "grama", "gramas", "kg"}
    _VOLUME_KEYWORDS = {"ml", "l", "litro", "litros"}
    _UNIT_KEYWORDS = {
        "unidade", "unidades", "unidade(s)", "fatia", "fatias",
        "colher", "colheres", "dosador", "dosadores",
    }

    def classify(self, unit: Optional[str]) -> UnitType:
        """
        Classifica o tipo de uma unidade de medida.

        A comparação é feita por palavra completa (após tokenização por
        espaços/parênteses), não por substring solta, para evitar que
        "colher" seja confundido com "l" (litro) ou vice-versa.

        Args:
            unit: String da unidade extraída do plano alimentar.

        Returns:
            ``UnitType`` correspondente à unidade fornecida.
        """
        if not unit:
            return UnitType.UNKNOWN

        unit_lower = unit.lower().strip()

        if "vontade" in unit_lower:
            return UnitType.FREE

        tokens = self._tokenize(unit_lower)

        if tokens & self._WEIGHT_KEYWORDS:
            return UnitType.WEIGHT_G
        if tokens & self._VOLUME_KEYWORDS:
            return UnitType.VOLUME_ML
        if tokens & self._UNIT_KEYWORDS:
            return UnitType.UNIT

        return UnitType.UNKNOWN

    def to_base_unit(self, quantity: float, unit: str) -> float:
        """
        Converte uma quantidade para a unidade base do seu tipo
        (gramas para peso, mililitros para volume).

        Útil para consolidar, por exemplo, "150 g" com "0.15 kg" do mesmo
        alimento.

        Args:
            quantity: Valor numérico da quantidade.
            unit: String da unidade original.

        Returns:
            Quantidade convertida para a unidade base. Unidades que não
            são de peso/volume (ex.: "unidade", "à vontade") são
            retornadas sem alteração.
        """
        tokens = self._tokenize((unit or "").lower())

        if "kg" in tokens:
            return quantity * 1000
        if tokens & {"l", "litro", "litros"}:
            return quantity * 1000

        return quantity

    def resolve_display_unit(
        self, unit_type: UnitType, original_unit: Optional[str]
    ) -> str:
        """
        Retorna a unidade canônica para exibição ao usuário.

        Args:
            unit_type: Tipo classificado da unidade.
            original_unit: Unidade original extraída do plano alimentar,
                usada como fallback para tipos desconhecidos.

        Returns:
            String da unidade para exibição (ex.: "g", "ml", "un").
        """
        unit_map = {
            UnitType.WEIGHT_G: "g",
            UnitType.VOLUME_ML: "ml",
            UnitType.UNIT: "un",
            UnitType.FREE: "à vontade",
        }
        return unit_map.get(unit_type, original_unit or "")

    @staticmethod
    def _tokenize(unit_lower: str) -> set[str]:
        """
        Quebra a unidade em tokens simples, removendo parênteses e "(s)"
        de plural, para permitir comparação por palavra completa.

        Exemplos:
            "unidade(s)" → {"unidade(s)", "unidade"}
            "kg"         → {"kg"}
        """
        cleaned = unit_lower.replace("(", " ").replace(")", " ")
        tokens = set(cleaned.split())
        tokens.add(unit_lower)
        # Também adiciona a forma sem o sufixo "(s)" pra bater com
        # "unidade(s)" quando o keyword set usa "unidade(s)" inteiro.
        return tokens
