"""Azure OpenAI integration for chat completions and embeddings.

Authentication uses DefaultAzureCredential via a bearer-token provider,
so no API keys are required. The service exposes two capabilities:

1. ``stream_chat`` -- streaming chat completion (async generator of tokens)
2. ``embed`` -- text embedding via text-embedding-3-small
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

# Temperature presets per deployment
_TEMPERATURE_MAP: dict[str, float] = {
    "gpt-4o-mini": 0.3,
    "gpt-4o": 0.2,
}

# Max-token limits per query type (controlled by caller via parameter)
MAX_TOKENS_FAQ = 800
MAX_TOKENS_BILL = 1200


class OpenAIService:
    """Thin wrapper around the Azure OpenAI async client."""

    def __init__(self, settings: Settings, credential: DefaultAzureCredential) -> None:
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default",
        )
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
        self._embedding_deployment = settings.azure_openai_embedding_deployment
        logger.info(
            "OpenAIService initialised (endpoint=%s)",
            settings.azure_openai_endpoint,
        )

    # ------------------------------------------------------------------
    # Chat completion (streaming)
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        deployment_name: str,
        *,
        max_tokens: int = MAX_TOKENS_FAQ,
    ) -> AsyncGenerator[str, None]:
        """Stream chat-completion tokens from the given deployment.

        Args:
            messages: OpenAI-format message list (system, user, assistant).
            deployment_name: Azure OpenAI deployment to call.
            max_tokens: Maximum tokens in the completion.

        Yields:
            Individual text tokens as they arrive from the model.
        """
        temperature = _TEMPERATURE_MAP.get(deployment_name, 0.3)
        logger.debug(
            "Streaming chat: deployment=%s temperature=%.1f max_tokens=%d",
            deployment_name,
            temperature,
            max_tokens,
        )

        stream = await self._client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Generate a 1536-dimension embedding vector for the given text.

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        response = await self._client.embeddings.create(
            model=self._embedding_deployment,
            input=text,
        )
        return response.data[0].embedding

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if the OpenAI endpoint is reachable."""
        try:
            # Lightweight call: embed a single token
            await self._client.embeddings.create(
                model=self._embedding_deployment,
                input="health",
            )
            return True
        except Exception:
            logger.warning("OpenAI health check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
