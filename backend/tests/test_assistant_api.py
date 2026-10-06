import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
import httpx

client = TestClient(app)

# Helper to mock auth
def mock_get_current_user():
    return {"id": "test-uuid", "email": "test@example.com", "app_role": "doctor"}

@pytest.fixture
def auth_override():
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-token"
        
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)

@pytest.fixture
def mock_dependencies():
    from app.api.rag import get_retrieval_service
    from app.api.assistant import get_llm_provider
    
    mock_retrieval = MagicMock()
    mock_llm = MagicMock()
    
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    yield mock_retrieval, mock_llm
    
    app.dependency_overrides.pop(get_retrieval_service, None)
    app.dependency_overrides.pop(get_llm_provider, None)

def test_chat_unauthenticated():
    response = client.post("/api/assistant/chat", json={"message": "hello"})
    assert response.status_code == 401

def test_chat_empty_message(auth_override):
    response = client.post("/api/assistant/chat", json={"message": ""})
    assert response.status_code == 422

def test_chat_no_context(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    mock_retrieval.retrieve_context.return_value = []
    
    response = client.post("/api/assistant/chat", json={"message": "What is lupus?"})
    assert response.status_code == 200
    data = response.json()
    assert "cannot answer this" in data["answer"].lower()
    assert len(data["sources"]) == 0
    mock_llm.generate_response.assert_not_called()

def test_chat_with_context(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    mock_retrieval.retrieve_context.return_value = [
        {"content": "Lupus is an autoimmune disease.", "similarity": 0.9, "metadata": {"source": "doc1.txt"}}
    ]
    
    from unittest.mock import AsyncMock
    mock_llm.generate_response = AsyncMock(return_value="Based on the context, lupus is an autoimmune disease.")
    
    response = client.post("/api/assistant/chat", json={"message": "What is lupus?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Based on the context, lupus is an autoimmune disease."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["content"] == "Lupus is an autoimmune disease."

def test_chat_provider_failure(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    mock_retrieval.retrieve_context.return_value = [{"content": "Context", "similarity": 0.8, "metadata": {}}]
    
    from unittest.mock import AsyncMock
    from app.core.llm.provider import LLMProviderError
    mock_llm.generate_response = AsyncMock(side_effect=LLMProviderError("AI provider error", status_code=502))
    
    response = client.post("/api/assistant/chat", json={"message": "What is lupus?"})
    assert response.status_code == 502
    assert "AI provider error" in response.json()["detail"]


def test_chat_provider_timeout(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    mock_retrieval.retrieve_context.return_value = [{"content": "Context", "similarity": 0.8, "metadata": {}}]
    
    from unittest.mock import AsyncMock
    from app.core.llm.provider import LLMTimeoutError
    mock_llm.generate_response = AsyncMock(side_effect=LLMTimeoutError("Request to AI provider timed out after 30 seconds."))
    
    response = client.post("/api/assistant/chat", json={"message": "What is lupus?"})
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


def test_chat_chunk_deduplication(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    # Simulate duplicate chunks from multiple document uploads
    mock_retrieval.retrieve_context.return_value = [
        {"content": "Duplicate content passage from report.", "similarity": 0.95, "metadata": {"doc": "upload_1.pdf"}},
        {"content": "Duplicate content passage from report.", "similarity": 0.94, "metadata": {"doc": "upload_2.pdf"}},
        {"content": "Unique clinical findings paragraph.", "similarity": 0.88, "metadata": {"doc": "upload_1.pdf"}},
    ]
    
    from unittest.mock import AsyncMock
    mock_llm.generate_response = AsyncMock(return_value="Summary answer.")
    
    response = client.post("/api/assistant/chat", json={"message": "Summarize findings"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 2  # Deduplicated from 3 down to 2


def test_chat_with_model_attribution(auth_override, mock_dependencies):
    mock_retrieval, mock_llm = mock_dependencies
    mock_retrieval.retrieve_context.return_value = [
        {"content": "Clinical protocol guidelines.", "similarity": 0.92, "metadata": {"doc": "protocol.pdf"}}
    ]
    
    from unittest.mock import AsyncMock
    from app.core.llm.provider import GenerationResult
    mock_llm.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="Follow standard protocol.",
            model="gemini-3.8-flash",
            provider="Google Gemini",
            fallback_used=False,
            attempted_models=["gemini-3.8-flash"]
        )
    )
    
    response = client.post("/api/assistant/chat", json={"message": "What is the protocol?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Follow standard protocol."
    assert "model_attribution" in data
    assert data["model_attribution"]["model"] == "gemini-3.8-flash"
    assert data["model_attribution"]["provider"] == "Google Gemini"
    assert data["model_attribution"]["fallback_used"] is False
    assert data["model_attribution"]["attempted_models"] == ["gemini-3.8-flash"]


def test_chat_fallback_activation_on_gemini_503(auth_override):
    """Verify Assistant Chat endpoint when FallbackLLMProvider routes Gemini 503 to Groq."""
    from app.api.rag import get_retrieval_service
    from app.api.assistant import get_llm_provider
    from app.core.llm.provider import FallbackLLMProvider, GenerationResult, LLMServiceUnavailableError
    from unittest.mock import AsyncMock
    
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve_context.return_value = [
        {"content": "Patient was prescribed Metformin 500mg daily.", "similarity": 0.95, "metadata": {"filename": "SOAP_Note.txt"}}
    ]
    
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMServiceUnavailableError("Gemini model 'gemini-flash-latest' is currently experiencing high demand (HTTP 503).")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text="According to the document, the patient was prescribed Metformin 500mg daily.",
            model="openai/gpt-oss-120b",
            provider="Groq",
            fallback_used=True,
            attempted_models=["openai/gpt-oss-120b"]
        )
    )
    
    fallback_router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval
    app.dependency_overrides[get_llm_provider] = lambda: fallback_router
    
    try:
        response = client.post("/api/assistant/chat", json={"message": "What medication was prescribed?"})
        assert response.status_code == 200
        data = response.json()
        assert "Metformin 500mg" in data["answer"]
        assert len(data["sources"]) == 1
        assert "SOAP_Note.txt" in data["sources"][0]["metadata"]["filename"]
        assert data["model_attribution"]["provider"] == "Groq"
        assert data["model_attribution"]["fallback_used"] is True
        
        # Verify both providers were called appropriately and SAME RAG context was delivered
        mock_gemini.generate_response_with_metadata.assert_called_once()
        mock_groq.generate_response_with_metadata.assert_called_once()
        call_args = mock_groq.generate_response_with_metadata.call_args
        groq_messages = call_args.kwargs.get("messages") or (call_args[0][0] if call_args[0] else [])
        assert any("Metformin 500mg daily" in m.get("content", "") for m in groq_messages)
    finally:
        app.dependency_overrides.pop(get_retrieval_service, None)
        app.dependency_overrides.pop(get_llm_provider, None)


def test_chat_no_context_never_calls_fallback_router(auth_override):
    """Critical RAG Safety Rule: When no context is found, neither Gemini nor Groq is called."""
    from app.api.rag import get_retrieval_service
    from app.api.assistant import get_llm_provider
    from app.core.llm.provider import FallbackLLMProvider
    from unittest.mock import AsyncMock
    
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve_context.return_value = []
    
    mock_gemini = MagicMock()
    mock_gemini.generate_response_with_metadata = AsyncMock()
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock()
    
    fallback_router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval
    app.dependency_overrides[get_llm_provider] = lambda: fallback_router
    
    try:
        response = client.post("/api/assistant/chat", json={"message": "What is the diagnosis for an unknown patient?"})
        assert response.status_code == 200
        data = response.json()
        assert "cannot answer this" in data["answer"].lower()
        assert len(data["sources"]) == 0
        mock_gemini.generate_response_with_metadata.assert_not_called()
        mock_groq.generate_response_with_metadata.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_retrieval_service, None)
        app.dependency_overrides.pop(get_llm_provider, None)




