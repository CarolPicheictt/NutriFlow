# backend/app/main.py

"""
main.py

Ponto de entrada da API do NutriFlow.

Uso local:
    uvicorn app.main:app --reload --app-dir backend
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.shopping import router as shopping_router

app = FastAPI(
    title="NutriFlow",
    description=(
        "Transforma um plano alimentar prescrito em uma lista de compras "
        "inteligente. Não cria dietas e não substitui o nutricionista."
    ),
    version="0.1.0",
)

# CORS liberado para uso local do MVP: o front-end (frontend/index.html)
# roda em outra origem (arquivo local ou um servidor estático em outra
# porta) e precisa poder chamar esta API a partir do navegador. Antes de
# expor a API fora da máquina do usuário, restrinja allow_origins às
# origens reais do front-end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shopping_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Endpoint simples de verificação de saúde da API."""
    return {"status": "ok"}
