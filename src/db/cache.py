# src/db/cache.py
"""Caché TTL en memoria para consultas frecuentes."""

import time
from typing import Optional, Any


class TTLCache:
    """Caché en memoria con Time-To-Live."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 128):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché si existe y no expiró."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Almacena un valor en el caché."""
        if len(self._cache) >= self._max_size:
            # Eliminar el más antiguo
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        """Invalida una entrada del caché."""
        self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Invalida todas las entradas que empiecen con el prefijo dado."""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]

    def clear(self) -> None:
        """Limpia todo el caché."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Cantidad de entradas en el caché."""
        return len(self._cache)
