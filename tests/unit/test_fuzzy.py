# tests/unit/test_fuzzy.py
"""Tests para la búsqueda fuzzy de clientes."""

import pytest
import aiosqlite

from src.db.models import Cliente
from src.db.repository import Repository


# db_connection fixture está en conftest.py


@pytest.fixture
async def repo_with_clients(db_connection):
    """Repository con clientes de ejemplo ya cargados."""
    repo = Repository(db_connection, cache_ttl=300)
    await repo.create_cliente(Cliente(nombre="Juan Pérez", telefono="+5491100001111"))
    await repo.create_cliente(Cliente(nombre="María García", telefono="+5491100002222"))
    await repo.create_cliente(
        Cliente(nombre="Pedro Martínez", telefono="+5491100003333")
    )
    await repo.create_cliente(Cliente(nombre="Ana López", telefono="+5491100004444"))
    await repo.create_cliente(
        Cliente(nombre="Carlos Rodríguez", telefono="+5491100005555")
    )
    return repo


class TestFuzzySearch:
    """Tests para la búsqueda fuzzy de clientes."""

    async def test_exact_match(self, repo_with_clients):
        """Coincidencia exacta tiene score alto."""
        results = await repo_with_clients.search_clientes_fuzzy("Juan Pérez")
        assert len(results) > 0
        cliente, score = results[0]
        assert cliente.nombre == "Juan Pérez"
        assert score >= 90

    async def test_match_without_accents(self, repo_with_clients):
        """Buscar sin acentos encuentra 'Pérez' (con threshold más permisivo)."""
        results = await repo_with_clients.search_clientes_fuzzy(
            "Juan Perez", threshold=75
        )
        assert len(results) > 0
        cliente, score = results[0]
        assert cliente.nombre == "Juan Pérez"
        assert score > 75

    async def test_reversed_name_order(self, repo_with_clients):
        """token_sort_ratio ignora el orden de las palabras."""
        results = await repo_with_clients.search_clientes_fuzzy(
            "Garcia Maria", threshold=75
        )
        assert len(results) > 0
        cliente, score = results[0]
        assert cliente.nombre == "María García"
        assert score >= 75

    async def test_high_threshold_fewer_results(self, repo_with_clients):
        """Con threshold alto, hay menos resultados."""
        results_low = await repo_with_clients.search_clientes_fuzzy(
            "Juan", threshold=50
        )
        results_high = await repo_with_clients.search_clientes_fuzzy(
            "Juan", threshold=90
        )
        assert len(results_low) >= len(results_high)

    async def test_no_match_below_threshold(self, repo_with_clients):
        """Búsquedas con score bajo del threshold no aparecen."""
        results = await repo_with_clients.search_clientes_fuzzy("XYZABC", threshold=75)
        assert len(results) == 0

    async def test_limit_parameter(self, repo_with_clients):
        """El parámetro limit limita la cantidad de resultados."""
        results = await repo_with_clients.search_clientes_fuzzy(
            "a", threshold=1, limit=2
        )
        assert len(results) <= 2

    async def test_empty_database(self, db_connection):
        """Buscar en BD vacía devuelve lista vacía."""
        repo = Repository(db_connection, cache_ttl=300)
        results = await repo.search_clientes_fuzzy("Juan")
        assert results == []

    async def test_martinez_pedro_matches(self, repo_with_clients):
        """'Martinez Pedro' encuentra 'Pedro Martínez'."""
        results = await repo_with_clients.search_clientes_fuzzy(
            "Martinez Pedro", threshold=75
        )
        assert len(results) > 0
        cliente, score = results[0]
        assert cliente.nombre == "Pedro Martínez"
        assert score >= 75
