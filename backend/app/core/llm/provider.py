import logging
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication with the LLM provider fails."""
    def __init__(self, detail: str = "Invalid or missing LLM API credentials"):
        super().__init__(detail, status_code=401)


class LLMRateLimitError(LLMProviderError):
    """Raised when the LLM provider returns a rate limit (429)."""
    def __init__(self, detail: str = "LLM provider rate limit exceeded"):
        super().__init__(detail, status_code=429)


class LLMTimeoutError(LLMProviderError):
    """Raised when the request to the LLM provider times out."""
    def __init__(self, detail: str = "LLM provider request timed out"):
        super().__init__(detail, status_code=504)


class LLMServiceUnavailableError(LLMProviderError):
    """Raised when the LLM provider is unavailable or overloaded (503)."""
    def __init__(self, detail: str = "LLM provider service temporarily unavailable"):
        super().__init__(detail, status_code=503)


class GenerationResult:
    """Encapsulates generated text with AI model attribution metadata."""
    def __init__(
        self,
        text: str,
        model: str,
        provider: str = "Google Gemini",
        fallback_used: bool = False,
        attempted_models: Optional[List[str]] = None
    ):
        self.text = text
        self.model = model
        self.provider = provider
        self.fallback_used = fallback_used
        self.attempted_models = attempted_models or [model]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "fallback_used": self.fallback_used,
            "attempted_models": self.attempted_models
        }


class LLMProviderInterface:
    """Interface for LLM providers."""
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        res = await self.generate_response_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return res.text

    async def generate_response_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> GenerationResult:
        raise NotImplementedError


class GeminiNativeProvider(LLMProviderInterface):
    """
    Native Google Gemini REST API provider.
    Uses x-goog-api-key header for secure authentication without exposing keys in URLs or logs.
    Includes automated fallback to active candidate models if the primary model is deprecated or overloaded.
    """
    FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-flash-latest"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        raw_url = base_url if base_url is not None else (settings.LLM_BASE_URL or "https://generativelanguage.googleapis.com/v1beta")
        # Strip trailing slashes and any /openai path suffix
        self.base_url = raw_url.rstrip("/").removesuffix("/openai")
        self.model = model or settings.LLM_MODEL or "gemini-3.8-flash"
        self.timeout = timeout
        self.http_timeout = httpx.Timeout(timeout=timeout, connect=8.0, read=25.0, write=10.0)

    def _build_payload(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float, 
        max_tokens: int
    ) -> Dict[str, Any]:
        system_instruction_text = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction_text = (
                    f"{system_instruction_text}\n{content}".strip() 
                    if system_instruction_text 
                    else content
                )
            elif role in ["assistant", "model"]:
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
            else:
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })

        # Ensure at least one content part exists
        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        if system_instruction_text:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction_text}]
            }

        return payload

    async def _send_request(
        self,
        client: httpx.AsyncClient,
        model_name: str,
        payload: Dict[str, Any]
    ) -> str:
        url = f"{self.base_url}/models/{model_name}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        response = await client.post(url, headers=headers, json=payload)
        
        # Handle error status codes with sanitized logging
        if response.status_code >= 400:
            sanitized_status = response.status_code
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", "Unknown error")
                err_code = err_data.get("error", {}).get("code", sanitized_status)
            except Exception:
                err_msg = response.text[:200]
                err_code = sanitized_status

            logger.warning(
                f"Gemini API returned HTTP {sanitized_status} for model '{model_name}': code={err_code}, msg={err_msg}"
            )

            if sanitized_status in (401, 403):
                raise LLMAuthenticationError(f"Gemini API authentication failed (HTTP {sanitized_status})")
            elif sanitized_status == 429:
                raise LLMRateLimitError(f"Gemini model '{model_name}' rate limit or quota exceeded (HTTP 429).")
            elif sanitized_status == 503:
                raise LLMServiceUnavailableError(f"Gemini model '{model_name}' is currently experiencing high demand (HTTP 503).")
            elif sanitized_status == 404:
                raise LLMProviderError(f"Gemini model '{model_name}' not found or unavailable.", status_code=404)
            elif sanitized_status in (500, 502, 504):
                raise LLMServiceUnavailableError(f"Gemini model '{model_name}' returned server error (HTTP {sanitized_status}).")
            else:
                raise LLMProviderError(f"Gemini API error (HTTP {sanitized_status}): {err_msg}", status_code=sanitized_status)

        data = response.json()
        
        # Validate response structure
        candidates = data.get("candidates")
        if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
            raise LLMProviderError("Gemini response missing candidate content", status_code=502)

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")

        if finish_reason == "SAFETY":
            raise LLMProviderError("Response was blocked by content safety filters.", status_code=400)
        elif finish_reason == "RECITATION":
            raise LLMProviderError("Response was blocked due to recitation policy.", status_code=400)

        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts or not isinstance(parts, list) or len(parts) == 0:
            raise LLMProviderError("Gemini candidate missing text parts", status_code=502)

        text = parts[0].get("text", "").strip()
        if not text:
            raise LLMProviderError("AI provider returned an empty response.", status_code=502)

        if finish_reason == "MAX_TOKENS":
            text += "\n\n*(Note: Output reached the token length limit and was truncated.)*"

        return text

    async def generate_response_with_metadata(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> GenerationResult:
        if not self.api_key:
            logger.warning("LLM_API_KEY is not configured.")
            raise LLMAuthenticationError("LLM API key is not configured on the backend.")

        payload = self._build_payload(messages, temperature, max_tokens)
        
        # Build list of candidate models starting with primary
        models_to_try = [self.model]
        for fb in self.FALLBACK_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        last_error: Optional[Exception] = None
        attempted_errors: List[str] = []
        attempted_sequence: List[str] = []

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            for idx, model_name in enumerate(models_to_try):
                attempted_sequence.append(model_name)
                try:
                    text_response = await self._send_request(client, model_name, payload)
                    fallback_used = (model_name != self.model)
                    
                    logger.info(
                        f"AI generation succeeded using model '{model_name}' "
                        f"(provider='Google Gemini', fallback_used={fallback_used}, "
                        f"attempted_sequence={attempted_sequence})"
                    )
                    
                    return GenerationResult(
                        text=text_response,
                        model=model_name,
                        provider="Google Gemini",
                        fallback_used=fallback_used,
                        attempted_models=attempted_sequence.copy()
                    )
                except LLMAuthenticationError as e:
                    # Permanent auth error - never retry across fallback models
                    logger.error(f"Permanent authentication failure for Gemini API (model '{model_name}'): {e.detail}")
                    raise e
                except (LLMRateLimitError, LLMServiceUnavailableError, LLMProviderError, LLMTimeoutError) as e:
                    # Check if error is eligible for fallback to next candidate model
                    status_code = getattr(e, "status_code", None)
                    is_fallback_eligible = (
                        isinstance(e, (LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError))
                        or status_code in (404, 429, 500, 502, 503, 504)
                    )

                    if not is_fallback_eligible:
                        # Non-retryable client error (e.g. 400 Bad Request, Safety Filter)
                        raise e

                    last_error = e
                    attempted_errors.append(f"{model_name}: {e.detail}")
                    
                    if idx < len(models_to_try) - 1:
                        next_model = models_to_try[idx + 1]
                        logger.warning(
                            f"Model '{model_name}' failed with eligible error ({e.detail}). "
                            f"Attempting fallback to '{next_model}'..."
                        )
                        await asyncio.sleep(0.2)
                        continue
                    else:
                        logger.error(
                            f"All candidate Gemini models {models_to_try} exhausted without success. "
                            f"Errors: {'; '.join(attempted_errors)}"
                        )

                except httpx.TimeoutException:
                    last_error = LLMTimeoutError(f"Request to model '{model_name}' timed out after {self.timeout}s.")
                    attempted_errors.append(f"{model_name}: Timeout ({self.timeout}s)")
                    if idx < len(models_to_try) - 1:
                        next_model = models_to_try[idx + 1]
                        logger.warning(
                            f"Model '{model_name}' timed out. Attempting fallback to '{next_model}'..."
                        )
                        await asyncio.sleep(0.2)
                        continue
                    else:
                        logger.error(f"All candidate Gemini models timed out. Errors: {'; '.join(attempted_errors)}")

                except httpx.RequestError as req_err:
                    last_error = LLMProviderError(f"Network error connecting to model '{model_name}': {type(req_err).__name__}", status_code=503)
                    attempted_errors.append(f"{model_name}: Network Error ({type(req_err).__name__})")
                    if idx < len(models_to_try) - 1:
                        next_model = models_to_try[idx + 1]
                        logger.warning(
                            f"Network error for model '{model_name}'. Attempting fallback to '{next_model}'..."
                        )
                        await asyncio.sleep(0.2)
                        continue
                    else:
                        logger.error(f"Network errors across all models: {'; '.join(attempted_errors)}")

        if last_error:
            raise last_error
        raise LLMProviderError("All configured AI models failed to respond.", status_code=503)

    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        result = await self.generate_response_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return result.text


class GroqLLMProvider(LLMProviderInterface):
    """
    Groq LLM Provider reusing existing Groq configuration and model cascade.
    Used as an automatic fallback provider for clinical AI and RAG assistant.
    """
    FALLBACK_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0
    ):
        self._custom_api_key = api_key
        self._custom_base_url = base_url
        self._custom_model = model
        self.timeout = timeout
        self.http_timeout = httpx.Timeout(timeout=timeout, connect=8.0, read=25.0, write=10.0)

    @property
    def api_key(self) -> str:
        if self._custom_api_key is not None:
            return self._custom_api_key.strip()
        import os
        return (settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY") or "").strip()

    @property
    def base_url(self) -> str:
        if self._custom_base_url is not None:
            return self._custom_base_url.rstrip("/")
        import os
        return (settings.GROQ_BASE_URL or os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")

    @property
    def model(self) -> str:
        if self._custom_model is not None:
            return self._custom_model
        import os
        return settings.GROQ_MODEL or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"

    async def generate_response_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> GenerationResult:
        if not self.api_key:
            logger.warning("[LLM] Groq API key is not configured.")
            raise LLMAuthenticationError("Groq API key is not configured on the backend.")

        candidate_models = [self.model]
        for fb in self.FALLBACK_MODELS:
            if fb not in candidate_models:
                candidate_models.append(fb)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/chat/completions"

        last_error: Optional[Exception] = None
        attempted_sequence: List[str] = []

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            for idx, model_name in enumerate(candidate_models):
                attempted_sequence.append(model_name)
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                try:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code >= 400:
                        status_code = response.status_code
                        err_msg = ""
                        try:
                            err_data = response.json()
                            err_msg = err_data.get("error", {}).get("message", response.text[:200])
                        except Exception:
                            err_msg = response.text[:200]

                        logger.warning(f"[LLM] Groq API HTTP {status_code} for model '{model_name}': {err_msg}")

                        if status_code in (401, 403):
                            raise LLMAuthenticationError(f"Groq API authentication failed (HTTP {status_code})")
                        elif status_code == 429:
                            last_error = LLMRateLimitError(f"Groq model '{model_name}' rate limit exceeded.")
                        elif status_code in (500, 502, 503, 504):
                            last_error = LLMServiceUnavailableError(f"Groq model '{model_name}' service temporarily unavailable (HTTP {status_code}).")
                        else:
                            last_error = LLMProviderError(f"Groq model '{model_name}' returned HTTP {status_code}", status_code=status_code)

                        if idx < len(candidate_models) - 1:
                            await asyncio.sleep(0.2)
                            continue
                        else:
                            break

                    data = response.json()
                    choices = data.get("choices")
                    if not choices or not isinstance(choices, list) or len(choices) == 0:
                        raise LLMProviderError("Groq response missing choices", status_code=502)

                    choice = choices[0]
                    msg = choice.get("message", {})
                    content = msg.get("content", "").strip()
                    if not content:
                        raise LLMProviderError("Groq choice missing message content", status_code=502)

                    finish_reason = choice.get("finish_reason")
                    if finish_reason == "length":
                        content += "\n\n*(Note: Output reached the token length limit and was truncated.)*"

                    actual_model = data.get("model") or model_name
                    return GenerationResult(
                        text=content,
                        model=actual_model,
                        provider="Groq",
                        fallback_used=True,
                        attempted_models=attempted_sequence.copy()
                    )

                except httpx.TimeoutException:
                    last_error = LLMTimeoutError(f"Groq request to model '{model_name}' timed out.")
                    if idx < len(candidate_models) - 1:
                        await asyncio.sleep(0.2)
                        continue
                except httpx.RequestError as req_err:
                    last_error = LLMProviderError(f"Groq network error on model '{model_name}': {type(req_err).__name__}", status_code=503)
                    if idx < len(candidate_models) - 1:
                        await asyncio.sleep(0.2)
                        continue

        if last_error:
            raise last_error
        raise LLMProviderError("All candidate Groq models failed to respond.", status_code=503)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        res = await self.generate_response_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return res.text


class FallbackLLMProvider(LLMProviderInterface):
    """
    LLM Router with Gemini as Primary and Groq as Automatic Fallback.
    Always attempts Gemini first. If Gemini encounters a provider/service failure
    (503, 429, 500, 502, 504, timeout, network error, empty response), automatically
    routes to Groq with the exact same context.
    """
    def __init__(
        self,
        primary: Optional[LLMProviderInterface] = None,
        fallback: Optional[LLMProviderInterface] = None
    ):
        self.primary = primary if primary is not None else GeminiNativeProvider()
        self.fallback = fallback if fallback is not None else GroqLLMProvider()

    def _is_fallback_eligible(self, error: Exception) -> bool:
        if isinstance(error, (LLMServiceUnavailableError, LLMRateLimitError, LLMTimeoutError)):
            return True
        status_code = getattr(error, "status_code", None)
        if status_code in (404, 429, 500, 502, 503, 504):
            return True
        if isinstance(error, (httpx.TimeoutException, httpx.RequestError)):
            return True
        if isinstance(error, LLMAuthenticationError):
            return True
        if isinstance(error, LLMProviderError) and status_code not in (400, 422):
            return True
        return False

    async def generate_response_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> GenerationResult:
        primary_error: Optional[Exception] = None
        try:
            result = await self.primary.generate_response_with_metadata(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info("[LLM] Gemini primary provider succeeded")
            return result
        except Exception as e:
            primary_error = e
            if not self._is_fallback_eligible(e):
                raise e

            status_code = getattr(e, "status_code", None)
            detail = getattr(e, "detail", str(e))
            err_summary = f"HTTP {status_code}" if status_code else detail
            logger.warning(f"[LLM] Gemini primary provider failed: {err_summary}")
            logger.info("[LLM] Falling back to Groq")

        try:
            fallback_res = await self.fallback.generate_response_with_metadata(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info("[LLM] Groq fallback provider succeeded")
            fallback_res.fallback_used = True
            primary_model = getattr(self.primary, "model", "gemini-3.8-flash")
            attempted = [primary_model] + [m for m in (fallback_res.attempted_models or []) if m != primary_model]
            fallback_res.attempted_models = attempted
            return fallback_res
        except Exception as fallback_error:
            logger.error(f"[LLM] Primary and fallback providers failed. Primary: {type(primary_error).__name__}, Fallback: {type(fallback_error).__name__}")
            raise LLMServiceUnavailableError("The AI service is temporarily unavailable. Please try again shortly.")

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        res = await self.generate_response_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return res.text


class OpenAILikeProvider(LLMProviderInterface):
    """
    Universal LLM Provider supporting OpenAI-compatible and Google Gemini endpoints.
    When configured for Gemini, automatically leverages FallbackLLMProvider (Gemini -> Groq).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.model = model or settings.LLM_MODEL or "gemini-3.8-flash"
        self.timeout = timeout
        self.http_timeout = httpx.Timeout(timeout=timeout, connect=8.0, read=25.0, write=10.0)

        self._is_gemini = (
            "googleapis.com" in self.base_url or 
            self.model.startswith("gemini")
        )

        if self._is_gemini:
            self._gemini_provider = GeminiNativeProvider(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                timeout=self.timeout
            )
            self._fallback_provider = FallbackLLMProvider(
                primary=self._gemini_provider,
                fallback=GroqLLMProvider(timeout=self.timeout)
            )
        else:
            self._gemini_provider = None
            self._fallback_provider = None

    async def generate_response_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> GenerationResult:
        if self._fallback_provider:
            return await self._fallback_provider.generate_response_with_metadata(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

        if not self.api_key:
            logger.warning("[LLM] LLM_API_KEY is not configured.")
            raise LLMAuthenticationError("AI Provider API key is not configured.")

        # Standard OpenAI-compatible implementation
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        url = f"{self.base_url}/chat/completions"
        
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code >= 400:
                    status_code = response.status_code
                    logger.warning(f"OpenAI-compatible LLM HTTP {status_code}: {response.text[:200]}")
                    if status_code in (401, 403):
                        raise LLMAuthenticationError(f"LLM API authentication failed (HTTP {status_code})")
                    elif status_code == 429:
                        raise LLMRateLimitError("LLM API rate limit exceeded")
                    elif status_code == 503:
                        raise LLMServiceUnavailableError("LLM API service temporarily unavailable")
                    else:
                        raise LLMProviderError(f"LLM API returned HTTP {status_code}", status_code=status_code)
                
                data = response.json()
                choices = data.get("choices")
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    raise LLMProviderError("LLM response missing choices", status_code=502)
                
                choice = choices[0]
                msg = choice.get("message", {})
                content = msg.get("content", "").strip()
                if not content:
                    raise LLMProviderError("LLM choice missing message content", status_code=502)

                finish_reason = choice.get("finish_reason")
                if finish_reason == "length":
                    content += "\n\n*(Note: Output reached the token length limit and was truncated.)*"
                
                actual_model = data.get("model") or self.model
                logger.info(f"AI generation succeeded using OpenAI model '{actual_model}'")
                return GenerationResult(
                    text=content,
                    model=actual_model,
                    provider="OpenAI",
                    fallback_used=False,
                    attempted_models=[self.model]
                )
        except httpx.TimeoutException:
            logger.error(f"LLM Provider Timeout after {self.timeout}s")
            raise LLMTimeoutError(f"LLM provider request timed out after {self.timeout} seconds.")
        except httpx.RequestError as req_err:
            logger.error(f"LLM Provider network error: {type(req_err).__name__}")
            raise LLMProviderError("Unable to connect to AI provider service.", status_code=503)

    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        result = await self.generate_response_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return result.text

