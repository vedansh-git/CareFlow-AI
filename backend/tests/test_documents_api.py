import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def mock_get_current_user_patient():
    return {"id": "patient-uuid", "email": "patient@example.com", "app_role": "patient"}

def mock_get_current_user_doctor():
    return {"id": "doctor-uuid", "email": "doctor@example.com", "app_role": "doctor"}

class MockCredentials:
    credentials = "fake-token"

@pytest.fixture
def auth_patient():
    from app.core.security import get_current_user, security_scheme
    app.dependency_overrides[get_current_user] = mock_get_current_user_patient
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)

@pytest.fixture
def auth_doctor():
    from app.core.security import get_current_user, security_scheme
    app.dependency_overrides[get_current_user] = mock_get_current_user_doctor
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)

@pytest.fixture
def mock_document_service():
    from app.api.documents import get_document_service
    mock_service = AsyncMock()
    app.dependency_overrides[get_document_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.pop(get_document_service, None)


def test_list_documents_unauthenticated():
    response = client.get("/api/documents/")
    assert response.status_code == 401

def test_list_documents_patient(auth_patient, mock_document_service):
    mock_document_service.list_documents.return_value = [
        {
            "id": "doc1",
            "title": "test.txt",
            "owner_id": "patient-uuid",
            "is_private": True,
            "created_at": "2023",
            "updated_at": "2023",
            "rag_indexed": True,
            "chunk_count": 3
        }
    ]
    response = client.get("/api/documents/")
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["rag_indexed"] is True
    assert docs[0]["chunk_count"] == 3
    mock_document_service.list_documents.assert_called_once_with("fake-token", "patient-uuid")

def test_list_documents_doctor(auth_doctor, mock_document_service):
    mock_document_service.list_documents.return_value = []
    response = client.get("/api/documents/")
    assert response.status_code == 200

def test_upload_document_patient(auth_patient, mock_document_service):
    mock_document_service.upload_document.return_value = {
        "id": "new-doc", "title": "blood_test.txt", "owner_id": "patient-uuid", 
        "created_at": "now", "updated_at": "now", "is_private": True,
        "rag_indexed": True, "chunk_count": 2
    }
    
    file_data = b"Some test data for uploading"
    files = {"file": ("blood_test.txt", file_data, "text/plain")}
    response = client.post("/api/documents/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "new-doc"
    assert data["rag_indexed"] is True
    assert data["chunk_count"] == 2
    mock_document_service.upload_document.assert_called_once()


def test_delete_document_patient(auth_patient, mock_document_service):
    mock_document_service.delete_document.return_value = True
    response = client.delete("/api/documents/doc1")
    assert response.status_code == 200
    mock_document_service.delete_document.assert_called_once_with("fake-token", "doc1", "patient-uuid")

def test_delete_document_failure(auth_patient, mock_document_service):
    mock_document_service.delete_document.return_value = False
    response = client.delete("/api/documents/doc1")
    assert response.status_code == 500

def test_download_document(auth_patient, mock_document_service):
    mock_document_service.list_documents.return_value = [
        {"id": "doc1", "file_path": "path/to/file"}
    ]
    mock_document_service.get_download_url.return_value = "http://signed-url"
    
    response = client.get("/api/documents/doc1/download")
    assert response.status_code == 200
    assert response.json()["url"] == "http://signed-url"

def test_download_document_unauthorized(auth_patient, mock_document_service):
    # Document doesn't exist or isn't accessible to user (empty list returned)
    mock_document_service.list_documents.return_value = []
    
    response = client.get("/api/documents/doc1/download")
    assert response.status_code == 404
