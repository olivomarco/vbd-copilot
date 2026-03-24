"""Tests for services/openai_service.py -- Azure OpenAI integration.

Covers streaming chat completions, embeddings, temperature selection,
token limits, and error handling. The Azure OpenAI client is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.openai_service import (
    MAX_TOKENS_BILL,
    MAX_TOKENS_FAQ,
    OpenAIService,
    _TEMPERATURE_MAP,
)


@pytest.fixture
def service(mock_settings: MagicMock, mock_credential: MagicMock) -> OpenAIService:
    """Create an OpenAIService with mocked dependencies."""
    with patch("app.services.openai_service.get_bearer_token_provider") as mock_token, \
         patch("app.services.openai_service.AsyncAzureOpenAI") as mock_oai_cls:
        mock_token.return_value = lambda: "fake-bearer"
        mock_client = AsyncMock()
        mock_oai_cls.return_value = mock_client

        svc = OpenAIService(mock_settings, mock_credential)
        svc._client = mock_client
        return svc


class TestStreamChat:
    """Test streaming chat completion."""

    @pytest.mark.asyncio
    async def test_stream_chat_yields_tokens(self, service: OpenAIService) -> None:
        """Streaming chat yields individual text tokens."""
        # Build mock chunks
        chunks = []
        for text in ["Buon", "giorno", ", come ", "posso ", "aiutarla?"]:
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta.content = text
            chunk.choices = [choice]
            chunks.append(chunk)

        # Add final chunk with None content
        final_chunk = MagicMock()
        final_choice = MagicMock()
        final_choice.delta.content = None
        final_chunk.choices = [final_choice]
        chunks.append(final_chunk)

        async def mock_stream():  # type: ignore[no-untyped-def]
            for c in chunks:
                yield c

        service._client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        tokens = []
        async for token in service.stream_chat(
            messages=[{"role": "user", "content": "Ciao"}],
            deployment_name="gpt-4o-mini",
        ):
            tokens.append(token)

        assert tokens == ["Buon", "giorno", ", come ", "posso ", "aiutarla?"]

    @pytest.mark.asyncio
    async def test_stream_chat_correct_params_mini(self, service: OpenAIService) -> None:
        """Verify temperature and max_tokens for gpt-4o-mini."""
        async def mock_stream():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        async for _ in service.stream_chat(
            messages=messages,
            deployment_name="gpt-4o-mini",
            max_tokens=MAX_TOKENS_FAQ,
        ):
            pass

        call_kwargs = service._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == _TEMPERATURE_MAP["gpt-4o-mini"]
        assert call_kwargs["max_tokens"] == MAX_TOKENS_FAQ
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["stream"] is True

    @pytest.mark.asyncio
    async def test_stream_chat_correct_params_4o(self, service: OpenAIService) -> None:
        """Verify temperature for gpt-4o deployment."""
        async def mock_stream():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        async for _ in service.stream_chat(
            messages=messages,
            deployment_name="gpt-4o",
            max_tokens=MAX_TOKENS_BILL,
        ):
            pass

        call_kwargs = service._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == _TEMPERATURE_MAP["gpt-4o"]
        assert call_kwargs["max_tokens"] == MAX_TOKENS_BILL
        assert call_kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_stream_chat_unknown_deployment_default_temp(
        self, service: OpenAIService
    ) -> None:
        """Unknown deployment name falls back to 0.3 temperature."""
        async def mock_stream():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        async for _ in service.stream_chat(
            messages=messages,
            deployment_name="custom-deployment",
        ):
            pass

        call_kwargs = service._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_stream_chat_error_handling(self, service: OpenAIService) -> None:
        """API error during streaming raises exception."""
        service._client.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenAI API Error")
        )

        with pytest.raises(Exception, match="OpenAI API Error"):
            async for _ in service.stream_chat(
                messages=[{"role": "user", "content": "Test"}],
                deployment_name="gpt-4o-mini",
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_chat_empty_choices(self, service: OpenAIService) -> None:
        """Chunks with empty choices are skipped."""
        chunk_empty = MagicMock()
        chunk_empty.choices = []

        chunk_valid = MagicMock()
        choice = MagicMock()
        choice.delta.content = "Token"
        chunk_valid.choices = [choice]

        async def mock_stream():  # type: ignore[no-untyped-def]
            yield chunk_empty
            yield chunk_valid

        service._client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        tokens = []
        async for token in service.stream_chat(
            messages=[{"role": "user", "content": "Test"}],
            deployment_name="gpt-4o-mini",
        ):
            tokens.append(token)

        assert tokens == ["Token"]


class TestEmbed:
    """Test text embedding generation."""

    @pytest.mark.asyncio
    async def test_embed_returns_vector(self, service: OpenAIService) -> None:
        """Embedding returns a list of 1536 floats."""
        embedding = [0.01] * 1536
        mock_response = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = embedding
        mock_response.data = [mock_data]

        service._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await service.embed("Testo di esempio")

        assert isinstance(result, list)
        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_embed_correct_model(self, service: OpenAIService) -> None:
        """Verify the correct embedding deployment is used."""
        mock_response = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.0] * 1536
        mock_response.data = [mock_data]

        service._client.embeddings.create = AsyncMock(return_value=mock_response)

        await service.embed("test")

        call_kwargs = service._client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_error_handling(self, service: OpenAIService) -> None:
        """Embedding API error propagates."""
        service._client.embeddings.create = AsyncMock(
            side_effect=Exception("Embedding API Error")
        )

        with pytest.raises(Exception, match="Embedding API Error"):
            await service.embed("test")


class TestOpenAIServiceHealthCheck:
    """Test the health probe."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, service: OpenAIService) -> None:
        """Successful health check returns True."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        service._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, service: OpenAIService) -> None:
        """Failed health check returns False."""
        service._client.embeddings.create = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await service.health_check()
        assert result is False


class TestOpenAIServiceClose:
    """Test client lifecycle."""

    @pytest.mark.asyncio
    async def test_close(self, service: OpenAIService) -> None:
        """close() delegates to underlying client."""
        service._client.close = AsyncMock()
        await service.close()
        service._client.close.assert_awaited_once()


class TestConstants:
    """Verify module-level constants."""

    def test_max_tokens_faq(self) -> None:
        """FAQ token limit is 800."""
        assert MAX_TOKENS_FAQ == 800

    def test_max_tokens_bill(self) -> None:
        """Bill analysis token limit is 1200."""
        assert MAX_TOKENS_BILL == 1200

    def test_temperature_map(self) -> None:
        """Temperature presets match expected values."""
        assert _TEMPERATURE_MAP["gpt-4o-mini"] == 0.3
        assert _TEMPERATURE_MAP["gpt-4o"] == 0.2
