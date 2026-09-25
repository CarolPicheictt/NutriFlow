# backend/app/api/routes/shopping.py

"""
shopping.py

Rotas da API relacionadas à lista de compras inteligente.

Nenhuma regra de negócio vive aqui: as rotas apenas validam entrada/saída
HTTP e delegam para os serviços de aplicação (``PlanService`` e
``ShoppingService``).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.dependencies import get_plan_service, get_shopping_service
from app.core.models.shopping_list import ShoppingItem
from app.services.plan_service import (
    InvalidDietPlanError,
    PDFUploadNotSupportedError,
    PlanService,
)
from app.services.shopping_service import ShoppingService

router = APIRouter(prefix="/api/v1", tags=["shopping"])


class UploadResponse(BaseModel):
    """Retorno do upload de um plano alimentar."""

    plan_id: UUID
    patient_name: str | None
    meals_found: int
    message: str


class ShoppingListResponse(BaseModel):
    """Retorno da lista de compras calculada."""

    plan_id: UUID
    days: int
    total_items: int
    categories: dict[str, list[ShoppingItem]]


class ChecklistUpdate(BaseModel):
    """Payload para atualizar estado de checklist."""

    item_name: str
    checked: bool


class ChecklistResponse(BaseModel):
    """Retorno da atualização de checklist."""

    item_name: str
    checked: bool


@router.post("/upload", response_model=UploadResponse)
async def upload_diet(
    file: UploadFile = File(...),
    service: PlanService = Depends(get_plan_service),
) -> UploadResponse:
    """
    Recebe um plano alimentar em JSON (formato ``DietPlan``) e o armazena.

    Aceita:
        - application/json (suportado nesta versão)
        - application/pdf (a camada já está preparada, mas a extração real
          via ``WebDietParser`` ainda não está ligada a este endpoint)

    Returns:
        ``UploadResponse`` com o ID do plano criado.
    """
    allowed = {"application/pdf", "application/json"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Formato não suportado: {file.content_type}",
        )

    content = await file.read()

    try:
        plan_id, diet_plan = await service.process_upload(content, file.content_type)
    except PDFUploadNotSupportedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except InvalidDietPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return UploadResponse(
        plan_id=plan_id,
        patient_name=diet_plan.patient.patient_name,
        meals_found=len(diet_plan.meals),
        message="Plano importado com sucesso",
    )


@router.get("/shopping/{plan_id}", response_model=ShoppingListResponse)
async def get_shopping_list(
    plan_id: UUID,
    days: int = Query(7, ge=1, le=30),
    service: ShoppingService = Depends(get_shopping_service),
) -> ShoppingListResponse:
    """
    Retorna a lista de compras calculada para N dias.

    Args:
        plan_id: ID do plano alimentar importado.
        days: Número de dias para calcular (entre 1 e 30).

    Returns:
        ``ShoppingListResponse`` com itens agrupados por categoria.
    """
    result = await service.get_shopping_list(plan_id, days)
    if result is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return ShoppingListResponse(
        plan_id=result.plan_id,
        days=result.days,
        total_items=result.total_items,
        categories=result.categories,
    )


@router.patch("/checklist/{plan_id}", response_model=ChecklistResponse)
async def update_checklist(
    plan_id: UUID,
    update: ChecklistUpdate,
    service: ShoppingService = Depends(get_shopping_service),
) -> ChecklistResponse:
    """
    Atualiza o estado de checagem de um item da lista de compras.

    Permite que o usuário marque (ou desmarque) o que já tem em casa.

    Args:
        plan_id: ID do plano alimentar.
        update: Item e novo estado (``checked: true/false``).
    """
    checked = await service.update_item_check(
        plan_id, update.item_name, update.checked
    )
    if checked is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return ChecklistResponse(item_name=update.item_name, checked=checked)


@router.get("/shopping/{plan_id}/export")
async def export_shopping_list(
    plan_id: UUID,
    days: int = Query(7, ge=1, le=30),
    fmt: str = Query("text", pattern="^(text|json)$"),
    service: ShoppingService = Depends(get_shopping_service),
):
    """
    Exporta a lista de compras em formato compartilhável.

    Args:
        plan_id: ID do plano.
        days: Número de dias.
        fmt: Formato de saída — ``"text"`` (padrão) ou ``"json"``.

    Returns:
        Texto pronto para copiar/compartilhar (``fmt="text"``) ou um objeto
        JSON equivalente (``fmt="json"``).
    """
    result = await service.export_list(plan_id, days, fmt)
    if result is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return result
