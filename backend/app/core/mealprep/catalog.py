# backend/app/core/mealprep/catalog.py

"""
catalog.py

Base de preparo do Meal Prep, carregada de ``backend/app/data/meal_prep_base.json``.

A base guarda, em um arquivo editável, o que não vem do plano alimentar:
    - o preparo mais simples por método de cocção;
    - quais alimentos precisam ser cozinhados e quais só são montados;
    - links de receitas da internet como outras sugestões;
    - os modelos de frase para montar lanches.

O módulo só lê e consulta a base; o cálculo de quantidades fica em
``planner.py``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from app.core.models.meal_prep import RecipeLink

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "meal_prep_base.json"
_VALID_MODES = {"cook", "assemble"}


def normalize_text(value: str) -> str:
    """Minúsculas, sem acento e só com letras/números separados por espaço."""
    decomposed = unicodedata.normalize("NFKD", (value or "").casefold())
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


@dataclass(frozen=True)
class CookingMethod:
    key: str
    label: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class FoodPreparation:
    """Entrada da base para um grupo de alimentos."""

    id: str
    keywords: tuple[str, ...]
    mode: str
    default_method: Optional[str] = None
    steps: tuple[str, ...] = ()
    extra_steps: tuple[str, ...] = ()
    assemble_verb: Optional[str] = None
    links: tuple[RecipeLink, ...] = field(default_factory=tuple)


class PreparationCatalog:
    """Consulta à base de preparo do Meal Prep."""

    def __init__(
        self,
        methods: dict[str, CookingMethod],
        foods: list[FoodPreparation],
        assembly_templates: dict[str, str],
    ) -> None:
        self._methods = methods
        self._foods = foods
        self._assembly_templates = assembly_templates

    @classmethod
    def from_file(cls, path: Path) -> "PreparationCatalog":
        """Lê e valida um arquivo da base. Levanta ``ValueError`` se inválido."""
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Base de preparo inválida ({path}): {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "PreparationCatalog":
        try:
            methods = {
                key: CookingMethod(
                    key=key,
                    label=str(value["label"]),
                    steps=tuple(str(step) for step in value["steps"]),
                )
                for key, value in raw["methods"].items()
            }
            templates = {key: str(text) for key, text in raw["assembly"].items()}
            foods = [cls._parse_food(entry, methods) for entry in raw["foods"]]
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"Base de preparo com formato inesperado: {exc!r}") from exc

        if "junte" not in templates or "marmita" not in templates:
            raise ValueError("A base de preparo precisa dos modelos 'junte' e 'marmita'.")
        return cls(methods, foods, templates)

    @staticmethod
    def _parse_food(entry: dict, methods: dict[str, CookingMethod]) -> FoodPreparation:
        mode = entry["mode"]
        if mode not in _VALID_MODES:
            raise ValueError(f"Modo inválido em '{entry.get('id')}': {mode}")
        default_method = entry.get("default_method")
        if default_method is not None and default_method not in methods:
            raise ValueError(
                f"Método '{default_method}' de '{entry['id']}' não existe em 'methods'."
            )
        keywords = tuple(normalize_text(word) for word in entry["keywords"])
        if not keywords or not all(keywords):
            raise ValueError(f"'{entry['id']}' precisa de palavras-chave.")
        links = tuple(
            RecipeLink(
                title=str(link["title"]),
                url=str(link["url"]),
                source=_source_name(str(link["url"])),
            )
            for link in entry.get("links", [])
        )
        return FoodPreparation(
            id=str(entry["id"]),
            keywords=keywords,
            mode=mode,
            default_method=default_method,
            steps=tuple(entry.get("steps", ())),
            extra_steps=tuple(entry.get("extra_steps", ())),
            assemble_verb=entry.get("assemble_verb"),
            links=links,
        )

    def find_food(self, name: str) -> Optional[FoodPreparation]:
        """
        Primeira entrada da base cujas palavras-chave aparecem no nome.

        A comparação é por palavra inteira (aceitando plural simples com
        "s" ou "es"), para que "maçã" não case com "macarrão" nem "mel"
        com "melancia".
        """
        words = normalize_text(name).split()
        if not words:
            return None
        for food in self._foods:
            if any(self._matches(words, keyword) for keyword in food.keywords):
                return food
        return None

    @staticmethod
    def _matches(words: list[str], keyword: str) -> bool:
        parts = keyword.split()
        size = len(parts)
        for start in range(len(words) - size + 1):
            window = words[start:start + size]
            if window[:-1] != parts[:-1]:
                continue
            last, target = window[-1], parts[-1]
            if last in (target, f"{target}s", f"{target}es"):
                return True
        return False

    def get_method(self, key: Optional[str]) -> Optional[CookingMethod]:
        return self._methods.get(key) if key else None

    def steps_for(self, food: Optional[FoodPreparation], method_key: Optional[str]) -> list[str]:
        """Passos do preparo: os próprios do alimento ou os do método, mais extras."""
        if food and food.steps:
            steps = list(food.steps)
        else:
            method = self.get_method(method_key) or self.get_method(
                food.default_method if food else None
            )
            steps = list(method.steps) if method else []
        if food and food.extra_steps:
            steps = steps[:-1] + list(food.extra_steps) + steps[-1:] if steps else list(food.extra_steps)
        return steps

    def assembly_template(self, verb: str) -> str:
        return self._assembly_templates.get(verb) or self._assembly_templates["junte"]

    @classmethod
    @lru_cache(maxsize=1)
    def default(cls) -> "PreparationCatalog":
        """Base padrão do projeto (carregada uma vez)."""
        return cls.from_file(_DEFAULT_PATH)


def _source_name(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host
