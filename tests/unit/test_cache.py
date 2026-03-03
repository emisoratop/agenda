# tests/unit/test_cache.py
"""Tests para el TTLCache."""

import time
import pytest
from src.db.cache import TTLCache


class TestTTLCache:
    """Tests para la clase TTLCache."""

    def test_set_and_get(self):
        """Se puede almacenar y recuperar un valor."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Obtener una key inexistente devuelve None."""
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """Los valores expiran después del TTL."""
        cache = TTLCache(ttl_seconds=0.1)  # 100ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        time.sleep(0.15)  # Esperar a que expire
        assert cache.get("key1") is None

    def test_max_size_eviction(self):
        """Al superar max_size, se elimina la entrada más antigua."""
        cache = TTLCache(ttl_seconds=60, max_size=3)
        cache.set("key1", "value1")
        time.sleep(0.01)
        cache.set("key2", "value2")
        time.sleep(0.01)
        cache.set("key3", "value3")
        time.sleep(0.01)

        # Agregar una cuarta entrada debería eliminar key1 (la más antigua)
        cache.set("key4", "value4")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_invalidate(self):
        """Invalidar una entrada la elimina del caché."""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_nonexistent(self):
        """Invalidar una key inexistente no falla."""
        cache = TTLCache()
        cache.invalidate("nonexistent")  # No debería lanzar excepción

    def test_invalidate_prefix(self):
        """invalidate_prefix elimina todas las entradas con ese prefijo."""
        cache = TTLCache()
        cache.set("eventos_hoy", [1, 2])
        cache.set("eventos_pendientes", [3, 4])
        cache.set("clientes", [5, 6])

        cache.invalidate_prefix("eventos")
        assert cache.get("eventos_hoy") is None
        assert cache.get("eventos_pendientes") is None
        assert cache.get("clientes") == [5, 6]

    def test_clear(self):
        """clear() elimina todo el caché."""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size == 0

    def test_size_property(self):
        """size devuelve la cantidad de entradas."""
        cache = TTLCache()
        assert cache.size == 0
        cache.set("key1", "value1")
        assert cache.size == 1
        cache.set("key2", "value2")
        assert cache.size == 2
        cache.invalidate("key1")
        assert cache.size == 1

    def test_overwrite_existing_key(self):
        """Sobreescribir una key actualiza el valor y el timestamp."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "old_value")
        cache.set("key1", "new_value")
        assert cache.get("key1") == "new_value"

    def test_cache_different_types(self):
        """El caché almacena distintos tipos de datos."""
        cache = TTLCache()
        cache.set("string", "hello")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"a": 1})
        cache.set("none", None)

        assert cache.get("string") == "hello"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"a": 1}
        # None es un valor válido
        assert (
            cache.get("none") is None
        )  # Esto devuelve None por diseño (no distingue de "no encontrado")
