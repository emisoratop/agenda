# tests/unit/test_result.py
"""Tests para el módulo Result pattern."""

from datetime import time

import pytest

from src.core.result import AvailableSlot, Result, ResultStatus


# ── ResultStatus ──────────────────────────────────────────────────────────────


class TestResultStatus:
    """Tests para el enum ResultStatus."""

    def test_has_four_values(self):
        """ResultStatus tiene exactamente 4 valores."""
        assert len(ResultStatus) == 4

    def test_success_value(self):
        assert ResultStatus.SUCCESS.value == "success"

    def test_error_value(self):
        assert ResultStatus.ERROR.value == "error"

    def test_needs_input_value(self):
        assert ResultStatus.NEEDS_INPUT.value == "needs_input"

    def test_conflict_value(self):
        assert ResultStatus.CONFLICT.value == "conflict"


# ── AvailableSlot ─────────────────────────────────────────────────────────────


class TestAvailableSlot:
    """Tests para el dataclass AvailableSlot."""

    def test_creation(self):
        """Se puede crear con start y end."""
        slot = AvailableSlot(start=time(9, 0), end=time(10, 30))
        assert slot.start == time(9, 0)
        assert slot.end == time(10, 30)

    def test_str_format(self):
        """__str__ devuelve formato HH:MM-HH:MM."""
        slot = AvailableSlot(start=time(9, 0), end=time(10, 30))
        assert str(slot) == "09:00-10:30"

    def test_str_midnight(self):
        """__str__ funciona con medianoche."""
        slot = AvailableSlot(start=time(0, 0), end=time(23, 59))
        assert str(slot) == "00:00-23:59"

    def test_str_single_digit_hours(self):
        """__str__ usa zero-padding en horas."""
        slot = AvailableSlot(start=time(8, 5), end=time(9, 0))
        assert str(slot) == "08:05-09:00"


# ── Result: Creación directa ─────────────────────────────────────────────────


class TestResultCreation:
    """Tests para creación directa del dataclass Result."""

    def test_minimal_creation(self):
        """Se puede crear con solo status."""
        r = Result(status=ResultStatus.SUCCESS)
        assert r.status == ResultStatus.SUCCESS
        assert r.data is None
        assert r.message is None
        assert r.question is None
        assert r.errors == []

    def test_full_creation(self):
        """Se puede crear con todos los campos."""
        r = Result(
            status=ResultStatus.ERROR,
            data={"key": "value"},
            message="algo falló",
            question="¿qué pasó?",
            errors=["e1", "e2"],
        )
        assert r.status == ResultStatus.ERROR
        assert r.data == {"key": "value"}
        assert r.message == "algo falló"
        assert r.question == "¿qué pasó?"
        assert r.errors == ["e1", "e2"]

    def test_errors_default_is_independent(self):
        """Cada instancia tiene su propia lista de errors."""
        r1 = Result(status=ResultStatus.SUCCESS)
        r2 = Result(status=ResultStatus.SUCCESS)
        r1.errors.append("oops")
        assert r2.errors == []


# ── Result.ok property ───────────────────────────────────────────────────────


class TestResultOk:
    """Tests para la property ok."""

    def test_ok_when_success(self):
        r = Result(status=ResultStatus.SUCCESS)
        assert r.ok is True

    def test_not_ok_when_error(self):
        r = Result(status=ResultStatus.ERROR)
        assert r.ok is False

    def test_not_ok_when_needs_input(self):
        r = Result(status=ResultStatus.NEEDS_INPUT)
        assert r.ok is False

    def test_not_ok_when_conflict(self):
        r = Result(status=ResultStatus.CONFLICT)
        assert r.ok is False


# ── Result.needs_input property ──────────────────────────────────────────────


class TestResultNeedsInput:
    """Tests para la property needs_input."""

    def test_needs_input_when_needs_input(self):
        r = Result(status=ResultStatus.NEEDS_INPUT)
        assert r.needs_input is True

    def test_not_needs_input_when_success(self):
        r = Result(status=ResultStatus.SUCCESS)
        assert r.needs_input is False

    def test_not_needs_input_when_error(self):
        r = Result(status=ResultStatus.ERROR)
        assert r.needs_input is False

    def test_not_needs_input_when_conflict(self):
        r = Result(status=ResultStatus.CONFLICT)
        assert r.needs_input is False


# ── Result.success() ─────────────────────────────────────────────────────────


class TestResultSuccess:
    """Tests para el factory method Result.success()."""

    def test_success_minimal(self):
        """success() sin argumentos crea Result exitoso."""
        r = Result.success()
        assert r.status == ResultStatus.SUCCESS
        assert r.ok is True
        assert r.data is None
        assert r.message is None

    def test_success_with_data(self):
        """success() acepta data."""
        r = Result.success(data={"id": 42})
        assert r.data == {"id": 42}
        assert r.ok is True

    def test_success_with_message(self):
        """success() acepta message."""
        r = Result.success(message="Evento creado")
        assert r.message == "Evento creado"

    def test_success_with_data_and_message(self):
        """success() acepta ambos."""
        r = Result.success(data=[1, 2, 3], message="ok")
        assert r.data == [1, 2, 3]
        assert r.message == "ok"


# ── Result.error() ───────────────────────────────────────────────────────────


class TestResultError:
    """Tests para el factory method Result.error()."""

    def test_error_minimal(self):
        """error() con solo message."""
        r = Result.error("algo falló")
        assert r.status == ResultStatus.ERROR
        assert r.ok is False
        assert r.message == "algo falló"
        assert r.errors == []

    def test_error_with_errors_list(self):
        """error() acepta lista de errores."""
        r = Result.error("fallaron cosas", errors=["e1", "e2"])
        assert r.errors == ["e1", "e2"]

    def test_error_none_errors_becomes_empty_list(self):
        """error() con errors=None produce lista vacía."""
        r = Result.error("oops", errors=None)
        assert r.errors == []


# ── Result.needs_clarification() ─────────────────────────────────────────────


class TestResultNeedsClarification:
    """Tests para el factory method Result.needs_clarification()."""

    def test_needs_clarification(self):
        """needs_clarification() crea Result con question."""
        r = Result.needs_clarification("¿Para qué día?")
        assert r.status == ResultStatus.NEEDS_INPUT
        assert r.needs_input is True
        assert r.question == "¿Para qué día?"

    def test_needs_clarification_ok_is_false(self):
        """needs_clarification() no es ok."""
        r = Result.needs_clarification("¿qué?")
        assert r.ok is False


# ── Result.conflict() ────────────────────────────────────────────────────────


class TestResultConflict:
    """Tests para el factory method Result.conflict()."""

    def test_conflict(self):
        """conflict() crea Result de conflicto."""
        r = Result.conflict("Horario superpuesto")
        assert r.status == ResultStatus.CONFLICT
        assert r.message == "Horario superpuesto"

    def test_conflict_ok_is_false(self):
        """conflict() no es ok."""
        r = Result.conflict("conflicto")
        assert r.ok is False

    def test_conflict_needs_input_is_false(self):
        """conflict() no necesita input."""
        r = Result.conflict("conflicto")
        assert r.needs_input is False
