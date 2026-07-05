"""
Groq Service — Async client for cloud LLM inference via Groq API.
Uses httpx to call the OpenAI-compatible Groq API directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


class GroqService:
    """
    Async wrapper for the Groq API (OpenAI compatible endpoint).
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout: int | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.groq_api_key
        self._default_model = default_model or settings.groq_default_model
        self._timeout = timeout or 60
        self._base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def _get_api_key(self) -> str | None:
        from infrastructure.repositories.sqlite_settings_repo import get_settings_repo
        repo = get_settings_repo()
        db_key = await repo.get_setting("groq_api_key")
        if db_key and db_key.strip():
            return db_key.strip()
        return self._api_key

    async def is_available(self) -> bool:
        """Check if Groq API key is configured."""
        key = await self._get_api_key()
        if not key:
            return False
        return True

    async def list_models(self) -> list[dict[str, Any]]:
        """
        List available Groq models (hardcoded for simplicity since Groq is API based).
        """
        return [
            {"name": "LLaMA 3.1 8B (Fast)", "model": "llama-3.1-8b-instant"},
            {"name": "LLaMA 3.3 70B (Smart)", "model": "llama-3.3-70b-versatile"},
            {"name": "LLaMA 3 70B", "model": "llama3-70b-8192"},
            {"name": "LLaMA 3 8B", "model": "llama3-8b-8192"},
        ]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs,
    ) -> str:
        """Non-streaming chat."""
        api_key = await self._get_api_key()
        if not api_key:
            raise ValueError("Groq API key is not configured.")

        model_name = model or self._default_model

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }

        # Inject additional options like temperature
        options = kwargs.get("options", {})
        if "temperature" in options:
            payload["temperature"] = options["temperature"]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._base_url, headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                logger.debug(
                    f"Groq chat [{model_name}]: "
                    f"{len(messages)} msgs → {len(content)} chars"
                )
                return content

        except Exception as e:
            logger.error(f"Groq chat failed [{model_name}]: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat."""
        api_key = await self._get_api_key()
        if not api_key:
            raise ValueError("Groq API key is not configured.")

        model_name = model or self._default_model

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
        }

        options = kwargs.get("options", {})
        if "temperature" in options:
            payload["temperature"] = options["temperature"]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST", self._base_url, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line or line.strip() == "data: [DONE]":
                            continue
                        
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                continue

        except httpx.HTTPStatusError as e:
            await e.response.aread()
            error_text = e.response.text
            logger.error(f"Groq stream HTTP error [{model_name}]: {error_text}")
            raise ValueError(f"Groq API Error: {error_text}")
        except Exception as e:
            logger.error(f"Groq stream failed [{model_name}]: {e}")
            raise

    @property
    def default_model(self) -> str:
        return self._default_model

    @default_model.setter
    def default_model(self, model: str):
        self._default_model = model


# ── Singleton ─────────────────────────────────────────────────

_groq_service: GroqService | None = None


def get_groq_service() -> GroqService:
    """Get the Groq service singleton."""
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService()
    return _groq_service
