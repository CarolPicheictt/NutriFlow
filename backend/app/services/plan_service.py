# backend/app/services/plan_service.py
"""
plan_service.py

Orquestra a conversão e o armazenamento de planos alimentares.

O serviço usa a interface ``PlanRepository`` para suportar armazenamento
em arquivo ou em memória durante os testes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.models.diet_plan import DietPlan
from scrap_do_pdf import WebDietParser


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


class FilePlanRepository:
    """Armazena planos como arquivos JSON identificados por UUID."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self._storage_dir = storage_dir or repo_root / "data" / "plans"

    def save(self, diet_plan: DietPlan) -> UUID:
        plan_id = uuid4()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        plan_path = self._path_for(plan_id)
        plan_path.write_text(diet_plan.model_dump_json(indent=2), encoding="utf-8")
        return plan_id

    def get(self, plan_id: UUID) -> Optional[DietPlan]:
        plan_path = self._path_for(plan_id)
        if not plan_path.is_file():
            return None
        return DietPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))

    def exists(self, plan_id: UUID) -> bool:
        return self._path_for(plan_id).is_file()

    def _path_for(self, plan_id: UUID) -> Path:
        return self._storage_dir / f"{plan_id}.json"


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
        """
        if content_type == "application/pdf":
            diet_plan = self._parse_pdf_plan(content)
        else:
            diet_plan = self._parse_json_plan(content)

        plan_id = self._repository.save(diet_plan)
        return plan_id, diet_plan

    @staticmethod
    def _parse_pdf_plan(content: bytes) -> DietPlan:
        """Executa o parser WebDiet em um arquivo temporário e limpa-o."""
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
                pdf_file.write(content)
                temporary_path = Path(pdf_file.name)
            return WebDietParser(temporary_path).parse()
        except Exception as exc:
            raise InvalidDietPlanError(
                f"Não foi possível processar o PDF do plano alimentar: {exc}"
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

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
