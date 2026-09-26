# backend/app/core/shopping/categorizer.py

"""
categorizer.py

Agrupamento de alimentos por categoria de supermercado.

Implementação MVP: classificação determinística por palavras-chave.
Isolada em sua própria classe para permitir evolução futura (ex.: tabela
curada por nutricionistas, categorização por corredor de supermercado
específico, ou um serviço de categorização mais sofisticado) sem alterar o
``ShoppingCalculator``.
"""

from __future__ import annotations


class FoodCategorizer:
    """
    Classifica o nome (já normalizado) de um alimento em uma categoria.

    A ordem de verificação importa: um alimento é atribuído à primeira
    categoria cuja palavra-chave aparece no nome. As categorias mais
    específicas são verificadas antes das mais genéricas para reduzir
    falsos positivos (ex.: "leite de coco" deve cair em laticínios antes de
    qualquer regra mais ampla).

    Uso:
        categorizer = FoodCategorizer()
        categoria = categorizer.categorize("peito de frango")  # "proteínas"
    """

    # Palavras-chave por categoria. Mantidas em minúsculas e sem acento
    # neutro (a comparação é feita sobre o nome já normalizado em
    # lowercase pelo FoodNameNormalizer).
    _KEYWORDS: dict[str, tuple[str, ...]] = {
        "suplementos": (
            "whey", "creatina", "albumina", "bcaa", "beta-alanina",
            "glutamina", "suplemento", "pré-treino", "pre-treino",
            "pré treino", "pre treino", "caseína", "caseina",
            "proteína isolada", "proteina isolada", "hipercalórico",
            "hipercalorico", "multivitamínico", "multivitaminico",
            "maltodextrina", "dextrose", "termogênico", "termogenico",
            "colágeno hidrolisado", "colageno hidrolisado",
        ),
        "proteínas": (
            "frango", "sobrecoxa", "peito", "carne", "boi", "patinho",
            "acém", "peixe", "tilápia", "salmão", "atum", "sardinha",
            "ovo", "ovos", "clara", "proteína", "tofu",
            "linguiça", "peru", "presunto", "bacon", "camarão", "suíno",
            "porco", "costela",
        ),
        "carboidratos": (
            "arroz", "pão", "macarrão", "massa", "batata", "mandioca",
            "aveia", "granola", "farinha", "tapioca", "cuscuz", "quinoa",
            "milho", "torrada", "biscoito", "cereal", "polenta",
            "inhame", "feijão", "lentilha", "grão de bico", "ervilha",
        ),
        "frutas": (
            "banana", "maçã", "laranja", "mamão", "melancia", "melão",
            "uva", "morango", "abacaxi", "manga", "pera", "kiwi",
            "abacate", "limão", "tangerina", "goiaba", "ameixa",
            "maracujá", "fruta",
        ),
        "verduras e legumes": (
            "alface", "tomate", "cenoura", "brócolis", "couve",
            "abobrinha", "abóbora", "pepino", "beterraba", "espinafre",
            "cebola", "alho", "pimentão", "chuchu", "rúcula", "repolho",
            "vagem", "berinjela", "salada", "legume", "verdura",
        ),
        "laticínios": (
            "leite", "queijo", "iogurte", "requeijão", "manteiga",
            "coalhada", "ricota", "cottage", "creme de leite",
        ),
        "gorduras": (
            "azeite", "óleo", "castanha", "amêndoa", "nozes",
            "amendoim", "semente", "chia", "linhaça", "coco",
            "pasta de amendoim",
        ),
    }

    _DEFAULT_CATEGORY = "outros"

    def categorize(self, name: str) -> str:
        """
        Retorna a categoria de um alimento com base em palavras-chave.

        Args:
            name: Nome do alimento, idealmente já normalizado
                (ver ``FoodNameNormalizer``).

        Returns:
            Nome da categoria correspondente, ou "outros" quando nenhuma
            palavra-chave corresponder.
        """
        name_lower = (name or "").lower()

        for category, keywords in self._KEYWORDS.items():
            if any(keyword in name_lower for keyword in keywords):
                return category

        return self._DEFAULT_CATEGORY
