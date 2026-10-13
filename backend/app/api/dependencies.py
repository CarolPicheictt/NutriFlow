# backend/app/api/dependencies.py

"""
dependencies.py

Injeção de dependências da API.

Por padrão, planos e checklist ficam apenas em memória do servidor: a cópia
que vale é a guardada no navegador do usuário (localStorage), que o
front-end reenvia (``PUT /api/v1/plans/{id}``) se o servidor tiver reiniciado.
Defina ``NUTRIFLOW_DATA_DIR`` para também gravar os planos em arquivos JSON.
Os serviços permanecem compartilhados entre as requisições do processo.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.services.plan_service import FilePlanRepository, InMemoryPlanRepository, PlanService
from app.services.shopping_service import InMemoryChecklistRepository, ShoppingService

_data_dir = os.environ.get("NUTRIFLOW_DATA_DIR")
_plan_service = PlanService(
    FilePlanRepository(Path(_data_dir)) if _data_dir else InMemoryPlanRepository()
)
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
