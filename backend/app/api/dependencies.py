# backend/app/api/dependencies.py

"""
dependencies.py

Injeção de dependências da API.

Os planos são salvos em arquivos JSON e o checklist é mantido em memória.
Os serviços permanecem compartilhados entre as requisições do processo.
"""

from __future__ import annotations

from app.services.plan_service import FilePlanRepository, PlanService
from app.services.shopping_service import InMemoryChecklistRepository, ShoppingService

_plan_service = PlanService(FilePlanRepository())
_shopping_service = ShoppingService(
    plan_service=_plan_service,
    checklist_repository=InMemoryChecklistRepository(),
)


def get_plan_service() -> PlanService:
    """Retorna a instância compartilhada de ``PlanService``."""
    return _plan_service


def get_shopping_service() -> ShoppingService:
    """Retorna a instância compartilhada de ``ShoppingService``."""
    return _shopping_service
