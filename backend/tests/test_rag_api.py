import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper to mock dependencies
def mock_get_current_user():
    return {"id": "test-uuid", "email": "test@example.com", "app_role": "patient"}

# We'll use dependency overrides in tests
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
def mock_retrieval_service():
    from app.api.rag import get_retrieval_service
    mock_service = MagicMock()
    app.dependency_overrides[get_retrieval_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.pop(get_retrieval_service, None)

def test_rag_health_unauthenticated():
    response = client.get("/api/rag/health")
    assert response.status_code == 401

def test_rag_health_authenticated(auth_override, mock_retrieval_service):
    mock_retrieval_service.vector_store.supabase_url = "https://mock.supabase.co"
    mock_retrieval_service.embeddings = MagicMock()
    
    response = client.get("/api/rag/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "vector_store": "connected",
        "embeddings": "initialized"
    }

def test_rag_search_unauthenticated():
    response = client.post("/api/rag/search", json={"question": "test?"})
    assert response.status_code == 401

def test_rag_search_validation_error(auth_override):
    # Missing question
    response = client.post("/api/rag/search", json={"top_k": 5})
    assert response.status_code == 422
    
    # Empty question
    response = client.post("/api/rag/search", json={"question": ""})
    assert response.status_code == 422
    
    # Invalid top_k
    response = client.post("/api/rag/search", json={"question": "test?", "top_k": 0})
    assert response.status_code == 422

def test_rag_search_success(auth_override, mock_retrieval_service):
    mock_retrieval_service.retrieve_context.return_value = [
        {
            "content": "Test context",
            "similarity": 0.85,
            "metadata": {"source": "test.txt"}
        }
    ]
    
    response = client.post("/api/rag/search", json={"question": "What is testing?", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "What is testing?"
    assert len(data["results"]) == 1
    assert data["results"][0]["content"] == "Test context"
    assert data["results"][0]["similarity"] == 0.85
    assert data["results"][0]["metadata"]["source"] == "test.txt"
    
    mock_retrieval_service.retrieve_context.assert_called_once_with(
        query="What is testing?",
        top_k=3,
        similarity_threshold=0.0,
        token="fake-token"
    )

def test_rag_search_internal_error(auth_override, mock_retrieval_service):
    mock_retrieval_service.retrieve_context.side_effect = Exception("Mock DB error")
    
    response = client.post("/api/rag/search", json={"question": "What is testing?", "top_k": 3})
    assert response.status_code == 500
    assert response.json()["detail"] == "An error occurred during retrieval."
