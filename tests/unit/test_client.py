# tests/unit/test_client.py
"""Tests para el cliente LLM con cadena de fallback."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.llm.client import (
    GroqAdapter,
    LLMAdapter,
    LLMChain,
    LLMProvider,
    LLMResponse,
    build_llm_chain,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


class MockAdapter:
    """Adapter mock para tests."""

    def __init__(self, name: str = "mock", response: str = "ok"):
        self._name = name
        self._response = response
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content=self._response,
            model=model,
            provider=self.name,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class FailingAdapter:
    """Adapter que siempre falla."""

    def __init__(self, name: str = "failing", error: Exception | None = None):
        self._name = name
        self._error = error or RuntimeError("LLM error")
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        self.call_count += 1
        raise self._error


class SlowAdapter:
    """Adapter que simula un timeout (tarda demasiado)."""

    def __init__(self, name: str = "slow", delay: float = 30.0):
        self._name = name
        self._delay = delay
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        self.call_count += 1
        await asyncio.sleep(self._delay)
        return LLMResponse(content="late", model=model, provider=self.name)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLLMResponse:
    """Tests para el dataclass LLMResponse."""

    def test_creation(self):
        """Se puede crear con todos los campos."""
        resp = LLMResponse(
            content='{"intent": "saludo"}',
            model="llama-3.3-70b",
            provider="groq",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert resp.content == '{"intent": "saludo"}'
        assert resp.model == "llama-3.3-70b"
        assert resp.provider == "groq"
        assert resp.usage["prompt_tokens"] == 10

    def test_usage_optional(self):
        """usage es opcional (default None)."""
        resp = LLMResponse(content="test", model="test", provider="test")
        assert resp.usage is None


class TestLLMAdapterProtocol:
    """Tests para el protocolo LLMAdapter."""

    def test_mock_adapter_is_llm_adapter(self):
        """MockAdapter cumple el protocolo LLMAdapter."""
        adapter = MockAdapter()
        assert isinstance(adapter, LLMAdapter)

    def test_groq_adapter_is_llm_adapter(self):
        """GroqAdapter cumple el protocolo LLMAdapter."""
        # No instanciamos realmente (necesita API key), solo verificamos la clase
        assert hasattr(GroqAdapter, "name")
        assert hasattr(GroqAdapter, "complete")


class TestLLMChain:
    """Tests para la cadena de fallback LLM."""

    async def test_single_provider_success(self):
        """Con un solo proveedor que responde, devuelve su respuesta."""
        adapter = MockAdapter(name="groq", response='{"ok": true}')
        chain = LLMChain(providers=[LLMProvider(adapter=adapter, model="test-model")])
        messages = [{"role": "user", "content": "hola"}]
        response = await chain.complete(messages)

        assert response.content == '{"ok": true}'
        assert response.provider == "groq"
        assert adapter.call_count == 1

    async def test_fallback_to_second_provider(self):
        """Si el primer proveedor falla, usa el segundo."""
        failing = FailingAdapter(name="groq-primary")
        success = MockAdapter(name="groq-fallback", response='{"ok": true}')

        chain = LLMChain(
            providers=[
                LLMProvider(adapter=failing, model="llama-70b", max_retries=1),
                LLMProvider(adapter=success, model="llama-8b", max_retries=1),
            ]
        )
        messages = [{"role": "user", "content": "hola"}]
        response = await chain.complete(messages)

        assert response.provider == "groq-fallback"
        assert failing.call_count == 1
        assert success.call_count == 1

    async def test_retries_before_fallback(self):
        """Reintenta max_retries veces antes de pasar al siguiente proveedor."""
        failing = FailingAdapter(name="groq")
        success = MockAdapter(name="backup", response="ok")

        chain = LLMChain(
            providers=[
                LLMProvider(adapter=failing, model="model-a", max_retries=2),
                LLMProvider(adapter=success, model="model-b", max_retries=1),
            ]
        )
        messages = [{"role": "user", "content": "test"}]

        # Monkey-patch asyncio.sleep para no esperar el backoff real
        with patch("src.llm.client.asyncio.sleep", new_callable=AsyncMock):
            response = await chain.complete(messages)

        assert failing.call_count == 2  # 2 reintentos
        assert success.call_count == 1
        assert response.provider == "backup"

    async def test_all_providers_fail_raises_runtime_error(self):
        """Si todos los proveedores fallan, lanza RuntimeError."""
        failing1 = FailingAdapter(name="p1")
        failing2 = FailingAdapter(name="p2")

        chain = LLMChain(
            providers=[
                LLMProvider(adapter=failing1, model="m1", max_retries=1),
                LLMProvider(adapter=failing2, model="m2", max_retries=1),
            ]
        )
        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(RuntimeError, match="No se pudo obtener respuesta"):
            await chain.complete(messages)

    async def test_timeout_triggers_retry(self):
        """Un timeout dispara reintento y eventualmente fallback."""
        slow = SlowAdapter(name="slow", delay=30)
        fast = MockAdapter(name="fast", response='{"ok": true}')

        chain = LLMChain(
            providers=[
                LLMProvider(
                    adapter=slow, model="slow-model", timeout=0.05, max_retries=1
                ),
                LLMProvider(adapter=fast, model="fast-model", max_retries=1),
            ]
        )
        messages = [{"role": "user", "content": "test"}]
        response = await chain.complete(messages)

        assert response.provider == "fast"
        assert slow.call_count == 1

    async def test_backoff_exponential(self):
        """El backoff entre reintentos es exponencial (2^attempt)."""
        failing = FailingAdapter(name="fail")
        success = MockAdapter(name="ok", response="ok")

        chain = LLMChain(
            providers=[
                LLMProvider(adapter=failing, model="m1", max_retries=3),
                LLMProvider(adapter=success, model="m2", max_retries=1),
            ]
        )
        messages = [{"role": "user", "content": "test"}]
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("src.llm.client.asyncio.sleep", side_effect=mock_sleep):
            await chain.complete(messages)

        # 3 reintentos = 2 sleeps (entre retry 0-1 y retry 1-2)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 1  # 2^0 = 1
        assert sleep_calls[1] == 2  # 2^1 = 2

    async def test_passes_max_tokens_and_temperature(self):
        """Los parámetros max_tokens y temperature se pasan al adapter."""
        adapter = MockAdapter(name="test")
        original_complete = adapter.complete
        received_kwargs = {}

        async def tracking_complete(messages, model, max_tokens=512, temperature=0.1):
            received_kwargs["max_tokens"] = max_tokens
            received_kwargs["temperature"] = temperature
            return await original_complete(messages, model, max_tokens, temperature)

        adapter.complete = tracking_complete
        chain = LLMChain(providers=[LLMProvider(adapter=adapter, model="test")])
        await chain.complete(
            [{"role": "user", "content": "x"}],
            max_tokens=256,
            temperature=0.5,
        )
        assert received_kwargs["max_tokens"] == 256
        assert received_kwargs["temperature"] == 0.5

    async def test_empty_providers_raises(self):
        """Cadena sin proveedores lanza RuntimeError."""
        chain = LLMChain(providers=[])
        with pytest.raises(RuntimeError, match="No se pudo obtener respuesta"):
            await chain.complete([{"role": "user", "content": "test"}])


class TestLLMProvider:
    """Tests para el dataclass LLMProvider."""

    def test_defaults(self):
        """LLMProvider tiene valores por defecto correctos."""
        adapter = MockAdapter()
        provider = LLMProvider(adapter=adapter, model="test-model")
        assert provider.timeout == 10.0
        assert provider.max_retries == 2

    def test_custom_values(self):
        """Se pueden especificar valores custom."""
        adapter = MockAdapter()
        provider = LLMProvider(adapter=adapter, model="m", timeout=5.0, max_retries=3)
        assert provider.timeout == 5.0
        assert provider.max_retries == 3


class TestBuildLLMChain:
    """Tests para la factory build_llm_chain()."""

    def test_builds_chain_with_groq_providers(self):
        """build_llm_chain() crea cadena con al menos 2 providers Groq."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.groq_api_key = "test-key"
        mock_settings.groq_model_primary = "llama-3.3-70b-versatile"
        mock_settings.groq_model_fallback = "llama-3.1-8b-instant"

        with (
            patch("src.config.get_settings", return_value=mock_settings),
            patch("src.llm.client.GroqAdapter") as mock_groq_cls,
            patch(
                "src.llm.client.getattr",
                create=True,
                side_effect=lambda o, n, d=None: None,
            ),
        ):
            mock_groq_cls.return_value = MockAdapter(name="groq")

            # getattr(settings, "gemini_api_key", None) devuelve MagicMock (truthy)
            # necesitamos que devuelva None — lo hacemos eliminando esos attrs
            del mock_settings.gemini_api_key
            del mock_settings.openai_api_key

            chain = build_llm_chain()

            assert isinstance(chain, LLMChain)
            assert len(chain.providers) == 2
            assert chain.providers[0].model == "llama-3.3-70b-versatile"
            assert chain.providers[1].model == "llama-3.1-8b-instant"
            mock_groq_cls.assert_called_once_with(api_key="test-key")

    def test_builds_chain_returns_llm_chain(self):
        """build_llm_chain() retorna una instancia de LLMChain."""
        from unittest.mock import PropertyMock

        # Usamos un objeto simple en vez de MagicMock para controlar getattr
        class FakeSettings:
            groq_api_key = "key"
            groq_model_primary = "model-a"
            groq_model_fallback = "model-b"

        with (
            patch("src.config.get_settings", return_value=FakeSettings()),
            patch("src.llm.client.GroqAdapter") as mock_groq_cls,
        ):
            mock_groq_cls.return_value = MockAdapter(name="groq")

            result = build_llm_chain()
            assert isinstance(result, LLMChain)
            assert len(result.providers) >= 2
