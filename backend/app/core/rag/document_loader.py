import os
from pathlib import Path
from typing import List, Dict, Any

class DocumentLoader:
    """
    Service for loading documents from various sources for RAG.
    """
    def __init__(self) -> None:
        pass
        
    def load_documents(self, source_path: str) -> List[Dict[str, Any]]:
        """
        Load documents from a given directory path.
        Supports .txt and .md files.
        
        Args:
            source_path (str): The directory path to load documents from.
            
        Returns:
            List[Dict[str, Any]]: A list of loaded documents with text and metadata.
        """
        documents = []
        path = Path(source_path)
        
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Source path {source_path} is not a valid directory.")
            
        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                        documents.append({
                            "text": text,
                            "metadata": {
                                "filename": file_path.name,
                                "source": str(file_path)
                            }
                        })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
                    
        return documents

    def extract_text_from_bytes(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """
        Extract text from raw file bytes for supported formats.
        """
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                import pypdf
                import io
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                text = ""
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                return text
            except ImportError:
                print("pypdf is not installed. Please install pypdf to extract text from PDFs.")
                return ""
            except Exception as e:
                print(f"Error extracting text from PDF: {e}")
                return ""
        elif content_type in ["text/plain", "text/markdown"] or filename.lower().endswith((".txt", ".md")):
            try:
                return file_bytes.decode("utf-8")
            except Exception as e:
                print(f"Error decoding text file: {e}")
                return ""
        else:
            return ""
