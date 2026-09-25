# backend/app/main.py

"""
main.py

Ponto de entrada da API do NutriFlow.

Uso local:
    uvicorn app.main:app --reload --app-dir backend
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.shopping import router as shopping_router

app = FastAPI(
    title="NutriFlow",
    description=(
        "Transforma um plano alimentar prescrito em uma lista de compras "
        "inteligente. Não cria dietas e não substitui o nutricionista."
    ),
    version="0.1.0",
)

app.include_router(shopping_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Endpoint simples de verificação de saúde da API."""
    return {"status": "ok"}
