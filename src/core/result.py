# src/core/result.py
"""Result pattern para operaciones del orquestador."""

from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Any, Optional


class ResultStatus(Enum):
    """Estados posibles del resultado de una operación."""

    SUCCESS = "success"
    ERROR = "error"
    NEEDS_INPUT = "needs_input"
    CONFLICT = "conflict"


@dataclass
class AvailableSlot:
    """Un bloque horario disponible."""

    start: time
    end: time

    def __str__(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


@dataclass
class Result:
    """Resultado genérico de una operación del orquestador."""

    status: ResultStatus
    data: Optional[Any] = None
    message: Optional[str] = None
    question: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True si la operación fue exitosa."""
        return self.status == ResultStatus.SUCCESS

    @property
    def needs_input(self) -> bool:
        """True si se necesita más información del usuario."""
        return self.status == ResultStatus.NEEDS_INPUT

    @staticmethod
    def success(data: Any = None, message: str | None = None) -> "Result":
        """Crea un Result exitoso."""
        return Result(status=ResultStatus.SUCCESS, data=data, message=message)

    @staticmethod
    def error(message: str, errors: list[str] | None = None) -> "Result":
        """Crea un Result de error."""
        return Result(status=ResultStatus.ERROR, message=message, errors=errors or [])

    @staticmethod
    def needs_clarification(question: str) -> "Result":
        """Crea un Result que necesita más datos del usuario."""
        return Result(status=ResultStatus.NEEDS_INPUT, question=question)

    @staticmethod
    def conflict(message: str) -> "Result":
        """Crea un Result de conflicto (ej: superposición de horario)."""
        return Result(status=ResultStatus.CONFLICT, message=message)
