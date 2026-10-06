import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.core.rag.document_loader import DocumentLoader
from app.core.rag.text_chunker import TextChunker
from app.core.rag.embeddings import EmbeddingsInterface
from app.core.rag.vector_store import VectorStoreInterface
from app.core.rag.retrieval_service import RetrievalService


def test_document_loader():
    loader = DocumentLoader()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        txt_file = os.path.join(temp_dir, "doc1.txt")
        md_file = os.path.join(temp_dir, "doc2.md")
        csv_file = os.path.join(temp_dir, "data.csv")
        
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("This is a text document.")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# This is a markdown document.")
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("a,b,c\n1,2,3")
            
        docs = loader.load_documents(temp_dir)
        
        assert len(docs) == 2
        filenames = [doc["metadata"]["filename"] for doc in docs]
        assert "doc1.txt" in filenames
        assert "doc2.md" in filenames
        assert "data.csv" not in filenames
        
        for doc in docs:
            if doc["metadata"]["filename"] == "doc1.txt":
                assert doc["text"] == "This is a text document."
            elif doc["metadata"]["filename"] == "doc2.md":
                assert doc["text"] == "# This is a markdown document."


def test_text_chunker():
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    
    docs = [
        {
            "text": "abcdefghijklmnopqrstuvwxyz",
            "metadata": {"filename": "test.txt"}
        }
    ]
    
    chunks = chunker.chunk_documents(docs)
    
    assert len(chunks) == 3
    assert chunks[0]["text"] == "abcdefghij"
    assert chunks[0]["metadata"]["chunk_start"] == 0
    assert chunks[0]["metadata"]["chunk_end"] == 10
    
    assert chunks[1]["text"] == "ijklmnopqr"
    assert chunks[1]["metadata"]["chunk_start"] == 8
    assert chunks[1]["metadata"]["chunk_end"] == 18
    
    assert chunks[2]["text"] == "qrstuvwxyz"
    assert chunks[2]["metadata"]["chunk_start"] == 16
    assert chunks[2]["metadata"]["chunk_end"] == 26


def test_document_loader_invalid_path():
    loader = DocumentLoader()
    with pytest.raises(ValueError):
        loader.load_documents("/invalid/path/that/does/not/exist/12345")


@patch("sentence_transformers.SentenceTransformer")
def test_embeddings(mock_st):
    mock_model_instance = MagicMock()
    mock_st.return_value = mock_model_instance
    
    def mock_encode(text_or_texts):
        if isinstance(text_or_texts, str):
            return np.ones(384) * 0.5
        else:
            return np.ones((len(text_or_texts), 384)) * 0.5
            
    mock_model_instance.encode.side_effect = mock_encode

    embeddings = EmbeddingsInterface()
    
    vec1 = embeddings.embed_text("Hello World")
    assert len(vec1) == 384
    assert all(isinstance(v, float) for v in vec1)
    
    vec2 = embeddings.embed_text("Hello World")
    assert vec1 == vec2
    
    docs = ["Doc 1", "Doc 2", "Doc 3"]
    vecs = embeddings.embed_documents(docs)
    assert len(vecs) == 3
    assert len(vecs[0]) == 384
    
    empty_vec = embeddings.embed_text("")
    assert empty_vec == [0.0] * 384


def test_vector_store_headers_separation():
    store = VectorStoreInterface(
        supabase_url="https://test.supabase.co",
        anon_key="anon-key-123",
        service_key="service-key-456",
    )
    
    assert store.write_headers["Authorization"] == "Bearer service-key-456"
    assert store.write_headers["apikey"] == "service-key-456"
    assert store.write_headers["Prefer"] == "return=representation"
    
    assert store.read_headers["Authorization"] == "Bearer anon-key-123"
    assert store.read_headers["apikey"] == "anon-key-123"
    assert "Prefer" not in store.read_headers


@patch("app.core.rag.vector_store.httpx.Client")
def test_vector_store_add_documents_uses_service_role(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    doc_res = MagicMock()
    doc_res.status_code = 201
    doc_res.json.return_value = [{"id": "doc-uuid-123"}]
    
    chunk_res = MagicMock()
    chunk_res.status_code = 201
    
    mock_client.post.side_effect = [doc_res, chunk_res]
    
    store = VectorStoreInterface(
        supabase_url="http://localhost:8000",
        anon_key="anon_key",
        service_key="service_role_key",
    )
    
    docs = [{"text": "Hello", "metadata": {"filename": "test.txt"}}]
    embeddings = [[0.1] * 384]
    
    store.add_documents(docs, embeddings)
    
    assert mock_client.post.call_count == 2
    
    call1 = mock_client.post.call_args_list[0]
    assert "clinical_documents" in call1[0][0]
    assert call1[1]["headers"]["Authorization"] == "Bearer service_role_key"
    assert call1[1]["json"]["title"] == "test.txt"
    
    call2 = mock_client.post.call_args_list[1]
    assert "document_chunks" in call2[0][0]
    assert call2[1]["headers"]["Authorization"] == "Bearer service_role_key"
    assert call2[1]["json"][0]["document_id"] == "doc-uuid-123"
    assert call2[1]["json"][0]["content"] == "Hello"


@patch("app.core.rag.vector_store.httpx.Client")
def test_vector_store_similarity_search_uses_read_credentials(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    search_res = MagicMock()
    search_res.status_code = 200
    search_res.json.return_value = [
        {"id": "chunk-123", "content": "Hello", "similarity": 0.9}
    ]
    mock_client.post.return_value = search_res
    
    store = VectorStoreInterface(
        supabase_url="http://localhost:8000",
        anon_key="anon_key",
        service_key="service_role_key",
    )
    
    results = store.similarity_search([0.1] * 384, limit=2, match_threshold=0.3)
    
    assert len(results) == 1
    assert results[0]["content"] == "Hello"
    assert results[0]["similarity"] == 0.9
    
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "match_document_chunks" in call_args[0][0]
    assert call_args[1]["headers"]["Authorization"] == "Bearer anon_key"
    assert call_args[1]["json"]["query_embedding"] == [0.1] * 384
    assert call_args[1]["json"]["match_threshold"] == 0.3
    assert call_args[1]["json"]["match_count"] == 2


@patch("app.core.rag.vector_store.httpx.Client")
def test_vector_store_delete_document_uses_service_role(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    del_res = MagicMock()
    del_res.status_code = 200
    mock_client.delete.return_value = del_res
    
    store = VectorStoreInterface(
        supabase_url="http://localhost:8000",
        anon_key="anon_key",
        service_key="service_role_key",
    )
    
    success = store.delete_document("doc-123")
    assert success is True
    mock_client.delete.assert_called_once()
    assert "id=eq.doc-123" in mock_client.delete.call_args[0][0]
    assert mock_client.delete.call_args[1]["headers"]["Authorization"] == "Bearer service_role_key"


def test_retrieval_service():
    mock_embeddings = MagicMock()
    mock_embeddings.embed_text.return_value = [0.1] * 384
    
    mock_vector_store = MagicMock()
    mock_vector_store.similarity_search.return_value = [
        {"id": "1", "content": "Best match", "similarity": 0.9},
        {"id": "2", "content": "Okay match", "similarity": 0.6},
        {"id": "3", "content": "Bad match", "similarity": 0.3},
    ]
    
    service = RetrievalService(embeddings=mock_embeddings, vector_store=mock_vector_store)
    
    results = service.retrieve_context("Test query", top_k=5, similarity_threshold=0.5)
    
    assert len(results) == 2
    assert results[0]["content"] == "Best match"
    assert results[1]["content"] == "Okay match"
    
    mock_embeddings.embed_text.assert_called_once_with("Test query")
    mock_vector_store.similarity_search.assert_called_once_with([0.1] * 384, limit=5, match_threshold=0.5, token=None)
    
    assert service.retrieve_context("") == []
    
    mock_embeddings.embed_text.side_effect = Exception("Embed error")
    assert service.retrieve_context("Error query") == []
