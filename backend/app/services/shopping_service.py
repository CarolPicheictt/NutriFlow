# backend/app/services/shopping_service.py

"""
shopping_service.py

Orquestra o cálculo da lista de compras, o estado do checklist ("já tenho
em casa") e a exportação da lista em formatos compartilháveis.

Assim como o ``PlanService``, o estado do checklist é mantido em memória
para o MVP, atrás de uma interface simples que pode ser trocada por
persistência real (PostgreSQL) no futuro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

from app.core.models.shopping_list import ShoppingItem
from app.core.shopping.calculator import ShoppingCalculator
from app.core.shopping.consolidator import FoodNameNormalizer
from app.services.plan_service import PlanService


@dataclass
class ShoppingListResult:
    """Resultado do cálculo da lista de compras para um plano."""

    plan_id: UUID
    days: int
    total_items: int
    categories: dict[str, list[ShoppingItem]] = field(default_factory=dict)


class ChecklistRepository(Protocol):
    """
    Interface de armazenamento do estado de checklist por plano.

    O estado é independente do número de dias (`days`): marcar "já tenho
    farinha de aveia em casa" vale tanto para uma lista de 3 quanto de 30
    dias, então a chave de armazenamento é apenas ``(plan_id, nome
    normalizado do item)``.
    """

    def get_checked(self, plan_id: UUID, normalized_name: str) -> bool:
        ...

    def set_checked(
        self, plan_id: UUID, normalized_name: str, checked: bool
    ) -> None:
        ...


class InMemoryChecklistRepository:
    """Implementação em memória de ``ChecklistRepository``."""

    def __init__(self) -> None:
        self._state: dict[UUID, dict[str, bool]] = {}

    def get_checked(self, plan_id: UUID, normalized_name: str) -> bool:
        return self._state.get(plan_id, {}).get(normalized_name, False)

    def set_checked(
        self, plan_id: UUID, normalized_name: str, checked: bool
    ) -> None:
        self._state.setdefault(plan_id, {})[normalized_name] = checked


class ShoppingService:
    """
    Serviço de aplicação responsável pela lista de compras.

    Uso:
        service = ShoppingService(plan_service, ShoppingCalculator(), InMemoryChecklistRepository())
        result = await service.get_shopping_list(plan_id, days=7)
    """

    def __init__(
        self,
        plan_service: PlanService,
        calculator: Optional[ShoppingCalculator] = None,
        checklist_repository: Optional[ChecklistRepository] = None,
    ) -> None:
        self._plan_service = plan_service
        self._calculator = calculator or ShoppingCalculator()
        self._checklist_repository = checklist_repository or InMemoryChecklistRepository()
        self._name_normalizer = FoodNameNormalizer()

    async def get_shopping_list(
        self, plan_id: UUID, days: int
    ) -> Optional[ShoppingListResult]:
        """
        Calcula a lista de compras de um plano, agrupada por categoria.

        Aplica o estado de checklist já salvo (itens marcados como
        disponíveis em casa) antes de retornar.

        Args:
            plan_id: ID do plano alimentar importado.
            days: Número de dias para calcular.

        Returns:
            ``ShoppingListResult`` com os itens agrupados por categoria, ou
            ``None`` se o plano não existir.
        """
        diet_plan = self._plan_service.get_plan(plan_id)
        if diet_plan is None:
            return None

        items = self._calculator.calculate(diet_plan, days=days)
        self._apply_checklist(plan_id, items)

        categories: dict[str, list[ShoppingItem]] = {}
        for item in items:
            categories.setdefault(item.category, []).append(item)

        return ShoppingListResult(
            plan_id=plan_id,
            days=days,
            total_items=len(items),
            categories=categories,
        )

    async def update_item_check(
        self, plan_id: UUID, item_name: str, checked: bool
    ) -> Optional[bool]:
        """
        Marca ou desmarca um item como já disponível em casa.

        Args:
            plan_id: ID do plano alimentar.
            item_name: Nome do item (como exibido na lista de compras).
            checked: Novo estado desejado.

        Returns:
            O valor de ``checked`` aplicado, ou ``None`` se o plano não
            existir.
        """
        if self._plan_service.get_plan(plan_id) is None:
            return None

        normalized_name = self._name_normalizer.normalize(item_name)
        self._checklist_repository.set_checked(plan_id, normalized_name, checked)
        return checked

    async def export_list(
        self, plan_id: UUID, days: int, fmt: str
    ) -> Optional[dict | str]:
        """
        Exporta a lista de compras em formato texto ou JSON.

        Args:
            plan_id: ID do plano alimentar.
            days: Número de dias.
            fmt: ``"text"`` (padrão) ou ``"json"``.

        Returns:
            Uma string formatada para copiar/compartilhar (``fmt="text"``),
            um dicionário serializável (``fmt="json"``), ou ``None`` se o
            plano não existir.

        Raises:
            ValueError: ``fmt`` diferente de ``"text"``/``"json"``.
        """
        result = await self.get_shopping_list(plan_id, days)
        if result is None:
            return None

        if fmt == "json":
            return {
                "plan_id": str(result.plan_id),
                "days": result.days,
                "total_items": result.total_items,
                "categories": {
                    category: [item.model_dump() for item in items]
                    for category, items in result.categories.items()
                },
            }

        if fmt == "text":
            return self._render_text(result)

        raise ValueError(f"Formato de exportação não suportado: {fmt!r}")

    def _apply_checklist(self, plan_id: UUID, items: list[ShoppingItem]) -> None:
        """Preenche ``item.checked`` com o estado salvo no checklist."""
        for item in items:
            item.checked = self._checklist_repository.get_checked(
                plan_id, item.normalized_name
            )

    @staticmethod
    def _render_text(result: ShoppingListResult) -> str:
        """
        Renderiza a lista de compras em texto simples, pronto para
        copiar e colar em um aplicativo de mensagens.
        """
        lines = [f"🛒 Lista de compras — {result.days} dia(s)", ""]

        for category, items in sorted(result.categories.items()):
            lines.append(f"📦 {category.upper()}")
            for item in items:
                mark = "✅" if item.checked else "⬜"
                suggestion = f" — {item.purchase_suggestion}" if item.purchase_suggestion else ""
                lines.append(f"{mark} {item.name}{suggestion}")
            lines.append("")

        lines.append(f"Total de itens: {result.total_items}")
        return "\n".join(lines).strip() + "\n"
