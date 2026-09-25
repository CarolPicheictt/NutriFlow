# backend/app/api/dependencies.py

"""
dependencies.py

Injeção de dependências da API.

Para o MVP, os serviços são singletons de processo (o armazenamento é em
memória, então uma única instância precisa ser compartilhada entre as
requisições). Quando o armazenamento em memória for substituído por
PostgreSQL, estas funções passam a construir os serviços com um
repositório real (ex.: uma sessão de banco por requisição), sem exigir
mudanças nas rotas que os consomem via ``Depends``.
"""

from __future__ import annotations

from app.services.plan_service import InMemoryPlanRepository, PlanService
from app.services.shopping_service import InMemoryChecklistRepository, ShoppingService

_plan_service = PlanService(InMemoryPlanRepository())
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
