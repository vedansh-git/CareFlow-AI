import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# Active tool-calling fallback cascade sequence for Groq
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


class GroqProviderError(Exception):
    """Base exception for Groq provider errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


class GroqProvider:
    """Client for Groq Chat Completions API with Function / Tool Calling and Fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    @property
    def api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key.strip()
        return (settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY") or "").strip()

    @api_key.setter
    def api_key(self, value: Optional[str]):
        self._api_key = value

    @property
    def base_url(self) -> str:
        url = settings.GROQ_BASE_URL or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        return url.rstrip("/")

    @property
    def primary_model(self) -> str:
        return settings.GROQ_MODEL or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to Groq with optional tool definitions.
        Cascades through fallback models if rate limit (429), model unavailability (404/400),
        or service capacity (503/500) occurs.
        """
        if not self.is_configured:
            raise GroqProviderError(
                "Groq API key is not configured. Please set GROQ_API_KEY in the backend environment.",
                status_code=401,
                error_type="unconfigured_api_key",
            )

        # Build candidate model list starting with configured primary model
        candidate_models = [self.primary_model]
        for m in GROQ_FALLBACK_MODELS:
            if m not in candidate_models:
                candidate_models.append(m)

        last_error = None
        attempted_models: List[str] = []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for idx, model in enumerate(candidate_models):
                attempted_models.append(model)
                payload: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = tool_choice

                try:
                    logger.info(f"Invoking Groq API model '{model}' with {len(messages)} messages and {len(tools or [])} tools.")
                    response = await client.post(url, headers=headers, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        choice = data.get("choices", [{}])[0]
                        message = choice.get("message", {})
                        
                        return {
                            "message": message,
                            "finish_reason": choice.get("finish_reason"),
                            "model_used": model,
                            "fallback_used": idx > 0,
                            "attempted_models": attempted_models,
                            "usage": data.get("usage", {}),
                        }

                    # Handle HTTP Errors
                    status = response.status_code
                    error_data = {}
                    try:
                        error_data = response.json().get("error", {})
                    except Exception:
                        pass
                    
                    err_msg = error_data.get("message") or response.text or f"HTTP {status}"
                    err_type = error_data.get("type", f"http_{status}")

                    logger.warning(f"Groq API error on model '{model}': Status {status}, type: {err_type}, message: {err_msg}")

                    # If 401 Unauthorized, key is invalid; abort cascade immediately
                    if status == 401:
                        raise GroqProviderError(
                            f"Groq authentication failed: {err_msg}",
                            status_code=401,
                            error_type="auth_failure",
                        )

                    # For 429 (Rate Limit), 404/400 (Model not available), 500, 502, 503, cascade to next model
                    last_error = GroqProviderError(
                        f"Groq model {model} failed: {err_msg}",
                        status_code=status,
                        error_type=err_type,
                    )

                except httpx.TimeoutException as te:
                    logger.warning(f"Groq model '{model}' timed out: {str(te)}")
                    last_error = GroqProviderError(
                        f"Groq model {model} request timed out.",
                        status_code=408,
                        error_type="timeout",
                    )
                except httpx.RequestError as re:
                    logger.warning(f"Groq network error on model '{model}': {str(re)}")
                    last_error = GroqProviderError(
                        f"Network error communicating with Groq: {str(re)}",
                        status_code=502,
                        error_type="network_error",
                    )

        # All models exhausted
        logger.error(f"All Groq models failed. Attempted: {attempted_models}. Last error: {last_error}")
        raise last_error or GroqProviderError("Groq request failed on all candidate models.", status_code=500)


# Global singleton instance
groq_provider = GroqProvider()
