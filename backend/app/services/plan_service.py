# backend/app/services/plan_service.py

"""
plan_service.py

Orquestra o recebimento e o armazenamento de planos alimentares.

O armazenamento é em memória para o MVP, mas fica atrás de uma interface
(``PlanRepository``) para que possa ser substituído por um repositório
com PostgreSQL no futuro sem alterar o serviço nem as rotas da API.
"""

from __future__ import annotations

import json
from typing import Optional, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.models.diet_plan import DietPlan


class PDFUploadNotSupportedError(NotImplementedError):
    """
    Levantado quando o upload de um PDF é recebido.

    O MVP atual só processa planos alimentares em JSON. A camada já está
    preparada para receber PDFs (ver ``PlanService.process_upload``), mas a
    extração real via ``WebDietParser`` (``scrap_do_pdf.py``) será ligada em
    uma etapa futura.
    """


class InvalidDietPlanError(ValueError):
    """Levantado quando o conteúdo enviado não é um `DietPlan` válido."""


class PlanRepository(Protocol):
    """
    Interface de armazenamento de planos alimentares.

    Qualquer implementação (em memória, PostgreSQL, etc.) precisa apenas
    destes três métodos. O ``PlanService`` depende apenas desta interface,
    nunca de uma implementação concreta.
    """

    def save(self, diet_plan: DietPlan) -> UUID:
        """Persiste um plano e retorna o identificador gerado."""
        ...

    def get(self, plan_id: UUID) -> Optional[DietPlan]:
        """Retorna o plano armazenado, ou ``None`` se não existir."""
        ...

    def exists(self, plan_id: UUID) -> bool:
        """Indica se um plano com esse identificador está armazenado."""
        ...


class InMemoryPlanRepository:
    """
    Implementação em memória de ``PlanRepository``.

    Adequada para o MVP (sem persistência entre reinícios do processo).
    Para trocar por PostgreSQL no futuro, basta implementar uma nova classe
    com os mesmos três métodos e injetá-la no lugar desta.
    """

    def __init__(self) -> None:
        self._plans: dict[UUID, DietPlan] = {}

    def save(self, diet_plan: DietPlan) -> UUID:
        plan_id = uuid4()
        self._plans[plan_id] = diet_plan
        return plan_id

    def get(self, plan_id: UUID) -> Optional[DietPlan]:
        return self._plans.get(plan_id)

    def exists(self, plan_id: UUID) -> bool:
        return plan_id in self._plans


class PlanService:
    """
    Serviço de aplicação responsável por receber e armazenar planos
    alimentares.

    Uso:
        service = PlanService(InMemoryPlanRepository())
        plan_id, diet_plan = await service.process_upload(content, "application/json")
    """

    def __init__(self, repository: PlanRepository) -> None:
        self._repository = repository

    async def process_upload(
        self,
        content: bytes,
        content_type: str,
    ) -> tuple[UUID, DietPlan]:
        """
        Valida o conteúdo enviado, armazena o plano e retorna seu ID.

        Args:
            content: Bytes brutos do arquivo enviado.
            content_type: Content-Type declarado no upload
                ("application/json" ou "application/pdf").

        Returns:
            Tupla ``(plan_id, diet_plan)`` do plano armazenado.

        Raises:
            InvalidDietPlanError: O conteúdo não é um JSON válido, ou não
                corresponde ao formato de ``DietPlan``.
            PDFUploadNotSupportedError: O upload é um PDF. O parser
                (``scrap_do_pdf.WebDietParser``) já existe no repositório,
                mas a ligação com este endpoint fica para uma etapa futura.
        """
        if content_type == "application/pdf":
            raise PDFUploadNotSupportedError(
                "Upload de PDF ainda não é suportado nesta versão do MVP. "
                "Envie o plano já convertido em JSON (ex.: exportado pelo "
                "parser do WebDiet)."
            )

        diet_plan = self._parse_json_plan(content)
        plan_id = self._repository.save(diet_plan)
        return plan_id, diet_plan

    def get_plan(self, plan_id: UUID) -> Optional[DietPlan]:
        """Retorna o plano armazenado, ou ``None`` se não existir."""
        return self._repository.get(plan_id)

    @staticmethod
    def _parse_json_plan(content: bytes) -> DietPlan:
        """
        Decodifica e valida o JSON recebido como um ``DietPlan``.

        Args:
            content: Bytes do corpo JSON enviado.

        Returns:
            ``DietPlan`` validado.

        Raises:
            InvalidDietPlanError: JSON malformado ou incompatível com o
                modelo ``DietPlan``.
        """
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidDietPlanError(f"JSON inválido: {exc}") from exc

        try:
            return DietPlan.model_validate(raw)
        except ValidationError as exc:
            raise InvalidDietPlanError(
                f"O JSON enviado não corresponde a um plano alimentar válido: {exc}"
            ) from exc
