# backend/app/main.py

"""
main.py

Ponto de entrada da API do NutriFlow.

Uso local:
    uvicorn app.main:app --reload --app-dir backend
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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


# Front-end estático (frontend/index.html, style.css, script.js) servido pela
# própria API: em produção (Render) site e API ficam na mesma origem, sem
# precisar configurar "Endereço da API". Este mount deve ser o ÚLTIMO, pois
# captura qualquer rota não definida acima.
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
