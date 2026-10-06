import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.core.config import Settings
from app.core.llm.provider import (
    GeminiNativeProvider,
    GroqLLMProvider,
    FallbackLLMProvider,
    OpenAILikeProvider,
    GenerationResult,
    LLMProviderError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError
)


# ==============================================================================
# 1. SUCCESSFUL GENERATION
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_success():
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello! I am CareFlow AI assistant."}],
                    "role": "model"
                },
                "finishReason": "STOP"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        messages = [
            {"role": "system", "content": "You are a clinical assistant."},
            {"role": "user", "content": "Hello"}
        ]
        
        result = await provider.generate_response(messages)
        assert result == "Hello! I am CareFlow AI assistant."
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "models/gemini-3.8-flash:generateContent" in call_args[0][0]
        assert call_args[1]["headers"]["x-goog-api-key"] == "test-key"
        payload = call_args[1]["json"]
        assert payload["system_instruction"]["parts"][0]["text"] == "You are a clinical assistant."
        assert payload["contents"][0]["role"] == "user"
        assert payload["contents"][0]["parts"][0]["text"] == "Hello"


# ==============================================================================
# 2. AUTHENTICATION & PERMISSION ERRORS (NO BLIND RETRIES)
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_missing_key():
    provider = GeminiNativeProvider(api_key="")
    with pytest.raises(LLMAuthenticationError) as exc_info:
        await provider.generate_response([{"role": "user", "content": "hi"}])
    assert "not configured" in str(exc_info.value.detail)


@pytest.mark.anyio
async def test_gemini_provider_auth_error_401_no_fallback():
    """401 is a permanent auth error and must NOT try secondary fallback models."""
    provider = GeminiNativeProvider(api_key="invalid-key", model="gemini-3.8-flash")
    
    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.json.return_value = {"error": {"code": 401, "message": "API_KEY_INVALID"}}
    resp_401.text = '{"error": {"code": 401, "message": "API_KEY_INVALID"}}'
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_401
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        
        assert exc_info.value.status_code == 401
        # Must fail immediately on the first attempt without triggering fallback models
        assert mock_post.call_count == 1


@pytest.mark.anyio
async def test_gemini_provider_permission_error_403_no_fallback():
    """403 is a permission error and must NOT try secondary fallback models."""
    provider = GeminiNativeProvider(api_key="forbidden-key", model="gemini-3.8-flash")
    
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.json.return_value = {"error": {"code": 403, "message": "PERMISSION_DENIED"}}
    resp_403.text = '{"error": {"code": 403, "message": "PERMISSION_DENIED"}}'
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_403
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        
        assert exc_info.value.status_code == 401  # LLMAuthenticationError default/HTTP mapping
        assert mock_post.call_count == 1


# ==============================================================================
# 3. FALLBACK CHAIN ON ELIGIBLE TRANSIENT / CAPACITY / MODEL ERRORS
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_model_fallback_on_404():
    """404 (model not found/deprecated) triggers the next model in the fallback chain."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.json.return_value = {"error": {"code": 404, "message": "Model not found"}}
    resp_404.text = "Model not found"
    
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Recovered via 3.7-flash fallback model."}]}}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_404, resp_200]
        
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Recovered via 3.7-flash fallback model."
        assert mock_post.call_count == 2
        # First call was gemini-3.8-flash, second call was gemini-3.7-flash
        assert "models/gemini-3.8-flash:generateContent" in mock_post.call_args_list[0][0][0]
        assert "models/gemini-3.7-flash:generateContent" in mock_post.call_args_list[1][0][0]


@pytest.mark.anyio
async def test_gemini_provider_fallback_on_429_rate_limit():
    """429 (Resource Exhausted / Rate Limit) on primary model triggers secondary fallback."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.json.return_value = {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}
    resp_429.text = "RESOURCE_EXHAUSTED"
    
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Recovered via gemini-3.7-flash after 429."}]}}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_429, resp_200]
        
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Recovered via gemini-3.7-flash after 429."
        assert mock_post.call_count == 2
        assert "models/gemini-3.8-flash:generateContent" in mock_post.call_args_list[0][0][0]
        assert "models/gemini-3.7-flash:generateContent" in mock_post.call_args_list[1][0][0]


@pytest.mark.anyio
async def test_gemini_provider_fallback_on_503_service_unavailable():
    """503 (high demand / capacity) triggers fallback to the next model."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.json.return_value = {"error": {"code": 503, "message": "High demand"}}
    resp_503.text = "High demand"
    
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Recovered via gemini-3.7-flash after 503."}]}}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_503, resp_200]
        
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Recovered via gemini-3.7-flash after 503."
        assert mock_post.call_count == 2


@pytest.mark.anyio
async def test_gemini_provider_fallback_on_timeout():
    """Timeout on primary triggers fallback to next model."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash", timeout=5.0)
    
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Recovered after timeout."}]}}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [httpx.TimeoutException("Timed out"), resp_200]
        
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Recovered after timeout."
        assert mock_post.call_count == 2


# ==============================================================================
# 4. EXHAUSTION OF ALL FALLBACK MODELS
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_all_models_fail_with_429():
    """When all models in the fallback chain (3.8-flash -> 3.7-flash -> flash-latest) hit 429."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.json.return_value = {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}
    resp_429.text = "RESOURCE_EXHAUSTED"
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # 3 calls: gemini-3.8-flash, gemini-3.7-flash, gemini-flash-latest
        mock_post.side_effect = [resp_429, resp_429, resp_429]
        
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        
        assert exc_info.value.status_code == 429
        assert mock_post.call_count == 3
        # Verify complete cascade order
        assert "gemini-3.8-flash" in mock_post.call_args_list[0][0][0]
        assert "gemini-3.7-flash" in mock_post.call_args_list[1][0][0]
        assert "gemini-flash-latest" in mock_post.call_args_list[2][0][0]


@pytest.mark.anyio
async def test_gemini_provider_all_models_fail_mixed():
    """When all models fail with mixed eligible errors (404 -> 429 -> 503)."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.json.return_value = {"error": {"code": 404, "message": "Not found"}}
    resp_404.text = "Not found"
    
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.json.return_value = {"error": {"code": 429, "message": "Rate limited"}}
    resp_429.text = "Rate limited"
    
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.json.return_value = {"error": {"code": 503, "message": "High demand"}}
    resp_503.text = "High demand"
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_404, resp_429, resp_503]
        
        with pytest.raises(LLMServiceUnavailableError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        
        assert exc_info.value.status_code == 503
        assert mock_post.call_count == 3


# ==============================================================================
# 5. CONTENT SAFETY AND PROTOCOL RESPONSES
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_malformed_response():
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"candidates": []}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        assert "missing candidate" in str(exc_info.value.detail).lower()


@pytest.mark.anyio
async def test_gemini_provider_max_tokens_truncated():
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Patient has elevated blood pressure and"}],
                    "role": "model"
                },
                "finishReason": "MAX_TOKENS"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate_response([{"role": "user", "content": "summarize"}])
        assert "Patient has elevated blood pressure and" in result
        assert "truncated" in result.lower()


@pytest.mark.anyio
async def test_gemini_provider_safety_blocked():
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "SAFETY"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        assert "safety filters" in str(exc_info.value.detail).lower()


@pytest.mark.anyio
async def test_gemini_provider_recitation_blocked():
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "RECITATION"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate_response([{"role": "user", "content": "hi"}])
        assert "recitation policy" in str(exc_info.value.detail).lower()


# ==============================================================================
# 6. OPENAI-LIKE PROVIDER & CONFIG PRECEDENCE
# ==============================================================================

@pytest.mark.anyio
async def test_openai_like_provider_gemini_delegation():
    provider = OpenAILikeProvider(
        api_key="test-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-3.8-flash"
    )
    assert provider._gemini_provider is not None
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Native Gemini response"}]},
                "finishReason": "STOP"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Native Gemini response"


@pytest.mark.anyio
async def test_openai_like_provider_success():
    provider = OpenAILikeProvider(
        api_key="test-openai-key", 
        base_url="https://api.openai.com/v1", 
        model="gpt-4o"
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "OpenAI answer."}
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        result = await provider.generate_response([{"role": "user", "content": "hi"}])
        assert result == "OpenAI answer."
        call_args = mock_post.call_args
        assert "https://api.openai.com/v1/chat/completions" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-openai-key"


def test_configuration_precedence_and_env_loading(monkeypatch):
    """Verify that environment variables override defaults and settings load correctly."""
    monkeypatch.setenv("LLM_MODEL", "gemini-3.7-flash")
    test_settings = Settings()
    assert test_settings.LLM_MODEL == "gemini-3.7-flash"
    assert test_settings.LLM_BASE_URL == "https://generativelanguage.googleapis.com/v1beta"


# ==============================================================================
# 7. AI MODEL ATTRIBUTION & METADATA TESTS
# ==============================================================================

@pytest.mark.anyio
async def test_gemini_provider_metadata_primary_success():
    """Verify metadata when primary model succeeds directly."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Attributed primary response."}]},
                "finishReason": "STOP"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        result = await provider.generate_response_with_metadata([{"role": "user", "content": "hi"}])
        assert result.text == "Attributed primary response."
        assert result.provider == "Google Gemini"
        assert result.model == "gemini-3.8-flash"
        assert result.fallback_used is False
        assert result.attempted_models == ["gemini-3.8-flash"]


@pytest.mark.anyio
async def test_gemini_provider_metadata_fallback_success():
    """Verify metadata when fallback model is activated after primary failure."""
    provider = GeminiNativeProvider(api_key="test-key", model="gemini-3.8-flash")
    
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.json.return_value = {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}
    resp_429.text = "RESOURCE_EXHAUSTED"
    
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Attributed fallback response."}]},
                "finishReason": "STOP"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_429, resp_200]
        
        result = await provider.generate_response_with_metadata([{"role": "user", "content": "hi"}])
        assert result.text == "Attributed fallback response."
        assert result.provider == "Google Gemini"
        assert result.model == "gemini-3.7-flash"
        assert result.fallback_used is True
        assert result.attempted_models == ["gemini-3.8-flash", "gemini-3.7-flash"]


# ==============================================================================
# 8. GROQ LLM PROVIDER TESTS
# ==============================================================================

@pytest.mark.anyio
async def test_groq_llm_provider_success():
    provider = GroqLLMProvider(api_key="test-groq-key", model="openai/gpt-oss-120b")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Groq generated response."},
                "finish_reason": "stop"
            }
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        result = await provider.generate_response_with_metadata([{"role": "user", "content": "hi"}])
        assert result.text == "Groq generated response."
        assert result.provider == "Groq"
        assert result.model == "openai/gpt-oss-120b"
        assert result.fallback_used is True


@pytest.mark.anyio
async def test_groq_llm_provider_missing_key():
    provider = GroqLLMProvider(api_key="")
    with pytest.raises(LLMAuthenticationError) as exc_info:
        await provider.generate_response([{"role": "user", "content": "hi"}])
    assert "not configured" in str(exc_info.value.detail).lower()


# ==============================================================================
# 9. FALLBACK ROUTER TESTS (GEMINI PRIMARY -> GROQ FALLBACK)
# ==============================================================================

@pytest.mark.anyio
async def test_fallback_provider_gemini_succeeds_groq_not_called():
    """Scenario A: Gemini primary succeeds directly; Groq fallback MUST NOT be invoked."""
    mock_gemini = MagicMock()
    mock_gemini.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="Primary Gemini answer.",
            model="gemini-3.8-flash",
            provider="Google Gemini",
            fallback_used=False,
            attempted_models=["gemini-3.8-flash"]
        )
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock()
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    result = await router.generate_response_with_metadata([{"role": "user", "content": "hi"}])
    assert result.text == "Primary Gemini answer."
    assert result.provider == "Google Gemini"
    assert result.fallback_used is False
    
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_not_called()


@pytest.mark.anyio
async def test_fallback_provider_gemini_503_triggers_groq_fallback():
    """Scenario B: Gemini hits 503 high demand; automatically routes to Groq."""
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMServiceUnavailableError("Gemini model 'gemini-flash-latest' is currently experiencing high demand (HTTP 503).")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="Groq fallback answer after 503.",
            model="openai/gpt-oss-120b",
            provider="Groq",
            fallback_used=True,
            attempted_models=["openai/gpt-oss-120b"]
        )
    )
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    result = await router.generate_response_with_metadata([{"role": "user", "content": "hi"}])
    assert result.text == "Groq fallback answer after 503."
    assert result.provider == "Groq"
    assert result.fallback_used is True
    assert "gemini-3.8-flash" in result.attempted_models
    assert "openai/gpt-oss-120b" in result.attempted_models
    
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_called_once()


@pytest.mark.anyio
async def test_fallback_provider_gemini_429_triggers_groq_fallback():
    """Scenario C: Gemini hits 429 rate limit; automatically routes to Groq."""
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMRateLimitError("Gemini rate limit exceeded (HTTP 429)")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="Groq fallback answer after 429.",
            model="openai/gpt-oss-120b",
            provider="Groq",
            fallback_used=True,
            attempted_models=["openai/gpt-oss-120b"]
        )
    )
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    result = await router.generate_response_with_metadata([{"role": "user", "content": "hi"}])
    assert result.text == "Groq fallback answer after 429."
    assert result.provider == "Groq"
    assert result.fallback_used is True
    
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_called_once()


@pytest.mark.anyio
async def test_fallback_provider_gemini_timeout_triggers_groq_fallback():
    """Scenario D: Gemini request times out; automatically routes to Groq."""
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMTimeoutError("Gemini request timed out after 30s.")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="Groq fallback answer after timeout.",
            model="openai/gpt-oss-120b",
            provider="Groq",
            fallback_used=True,
            attempted_models=["openai/gpt-oss-120b"]
        )
    )
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    result = await router.generate_response_with_metadata([{"role": "user", "content": "hi"}])
    assert result.text == "Groq fallback answer after timeout."
    assert result.provider == "Groq"
    assert result.fallback_used is True
    
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_called_once()


@pytest.mark.anyio
async def test_fallback_provider_both_fail_raises_service_unavailable():
    """Scenario G: Both Gemini and Groq fail; raises clean service unavailable error without exposing secrets."""
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMServiceUnavailableError("Gemini 503")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        side_effect=LLMServiceUnavailableError("Groq 503")
    )
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    with pytest.raises(LLMServiceUnavailableError) as exc_info:
        await router.generate_response_with_metadata([{"role": "user", "content": "hi"}])
    
    assert "temporarily unavailable" in str(exc_info.value.detail).lower()
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_called_once()


@pytest.mark.anyio
async def test_fallback_provider_client_400_not_fallback_eligible():
    """Client-side errors (e.g. prompt safety rejection) are not fallback eligible and fail immediately."""
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMProviderError("Response was blocked by content safety filters.", status_code=400)
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock()
    
    router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    with pytest.raises(LLMProviderError) as exc_info:
        await router.generate_response_with_metadata([{"role": "user", "content": "unsafe prompt"}])
    
    assert exc_info.value.status_code == 400
    mock_gemini.generate_response_with_metadata.assert_called_once()
    mock_groq.generate_response_with_metadata.assert_not_called()



