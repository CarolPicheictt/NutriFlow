# backend/app/api/decoders.py

"""
decoders.py

Decodificação dos parâmetros de query em JSON compartilhados pelas rotas
(escolhas de substituição e sobras em gramas).
"""

from __future__ import annotations

import json
import math

from fastapi import HTTPException


def decode_substitution_choices(raw_choices: str | None) -> dict[str, str] | None:
    if raw_choices is None:
        return None
    try:
        choices = json.loads(raw_choices)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Escolhas de substituição inválidas.") from exc
    if not isinstance(choices, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in choices.items()
    ):
        raise HTTPException(status_code=422, detail="Escolhas de substituição inválidas.")
    return choices


def decode_leftovers_grams(raw_leftovers: str | None) -> dict[str, float] | None:
    if raw_leftovers is None:
        return None
    try:
        leftovers = json.loads(raw_leftovers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.") from exc
    if not isinstance(leftovers, dict):
        raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.")

    decoded: dict[str, float] = {}
    for name, quantity in leftovers.items():
        if (
            not isinstance(name, str)
            or isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
            or quantity < 0
        ):
            raise HTTPException(status_code=422, detail="Quantidades de sobra inválidas.")
        decoded[name] = float(quantity)
    return decoded
