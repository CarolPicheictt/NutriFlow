# backend/app/api/routes/shopping.py

"""
shopping.py

Rotas da API relacionadas à lista de compras inteligente.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.core.shopping.calculator import ShoppingCalculator, ShoppingItem
from app.services.shopping_service import ShoppingService
from app.services.plan_service import PlanService
from app.api.dependencies import get_shopping_service, get_plan_service

router = APIRouter(prefix="/api/v1", tags=["shopping"])


class UploadResponse(BaseModel):
    """Retorno do upload de PDF ou JSON."""
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


@router.post("/upload", response_model=UploadResponse)
async def upload_diet(
    file: UploadFile = File(...),
    service: PlanService = Depends(get_plan_service),
):
    """
    Recebe um PDF exportado do WebDiet ou um JSON já parseado.
    Processa e armazena o plano alimentar do usuário.

    Aceita:
        - application/pdf
        - application/json

    Returns:
        UploadResponse com o ID do plano criado.
    """
    allowed = {"application/pdf", "application/json"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Formato não suportado: {file.content_type}",
        )

    content = await file.read()
    plan = await service.process_upload(content, file.content_type)

    return UploadResponse(
        plan_id=plan.id,
        patient_name=plan.patient.patient_name,
        meals_found=len(plan.meals),
        message="Plano importado com sucesso",
    )


@router.get("/shopping/{plan_id}", response_model=ShoppingListResponse)
async def get_shopping_list(
    plan_id: UUID,
    days: int = 7,
    service: ShoppingService = Depends(get_shopping_service),
):
    """
    Retorna a lista de compras calculada para N dias.

    Args:
        plan_id: ID do plano alimentar importado.
        days: Número de dias para calcular (padrão: 7, máximo: 30).

    Returns:
        ShoppingListResponse com itens agrupados por categoria.
    """
    if not (1 <= days <= 30):
        raise HTTPException(
            status_code=422,
            detail="O parâmetro 'days' deve estar entre 1 e 30.",
        )

    result = await service.get_shopping_list(plan_id, days)
    if not result:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return result


@router.patch("/checklist/{plan_id}")
async def update_checklist(
    plan_id: UUID,
    update: ChecklistUpdate,
    service: ShoppingService = Depends(get_shopping_service),
):
    """
    Atualiza o estado de checagem de um item da lista de compras.
    Permite que o usuário marque o que já tem em casa.

    Args:
        plan_id: ID do plano alimentar.
        update: Item e novo estado (checked: true/false).
    """
    await service.update_item_check(plan_id, update.item_name, update.checked)
    return {"status": "updated"}


@router.get("/shopping/{plan_id}/export")
async def export_shopping_list(
    plan_id: UUID,
    days: int = 7,
    fmt: str = "text",
    service: ShoppingService = Depends(get_shopping_service),
):
    """
    Exporta a lista de compras em formato compartilhável.

    Args:
        plan_id: ID do plano.
        days: Número de dias.
        fmt: Formato de saída — 'text' (padrão) ou 'json'.

    Returns:
        Lista formatada para copiar/compartilhar via WhatsApp, etc.
    """
    result = await service.export_list(plan_id, days, fmt)
    return result