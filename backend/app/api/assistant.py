import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import get_current_user, security_scheme
from app.schemas.assistant import ChatRequest, ChatResponse, SourceCitation
from app.core.rag.retrieval_service import RetrievalService
from app.api.rag import get_retrieval_service
from app.core.llm.provider import (
    FallbackLLMProvider,
    OpenAILikeProvider, 
    LLMProviderInterface, 
    LLMProviderError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Singletons
_llm_provider = None

def get_llm_provider() -> LLMProviderInterface:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = FallbackLLMProvider()
    return _llm_provider

SYSTEM_PROMPT = """You are CareFlow AI, a clinical workflow and documentation assistant.
You are given a user question and a set of relevant context passages from clinical documents.
Your task is to answer the question using ONLY the information provided in the context passages.

RULES:
1. Ground your answer strictly in the provided context.
2. If the context does not contain the answer, say "I cannot answer this based on the provided clinical documents." Do NOT invent or hallucinate information.
3. Distinguish evidence from uncertainty.
4. Do NOT invent citations. If you refer to a document, make sure it is in the context.
5. NEVER claim to diagnose a patient. You are an assistant, not a doctor.
6. Provide a concise, clear, and professional response.

CONTEXT:
{context}
"""

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm: LLMProviderInterface = Depends(get_llm_provider)
) -> ChatResponse:
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty."
        )
        
    try:
        # 1. Retrieve relevant chunks (retrieve top 8 to allow deduplication)
        raw_chunks = retrieval_service.retrieve_context(
            query=request.message,
            top_k=8,
            similarity_threshold=0.25,
            token=credentials.credentials
        )
        
        # 2. Deduplicate chunks by normalized text content
        seen_texts = set()
        unique_chunks = []
        for chunk in raw_chunks:
            content = (chunk.get("content") or "").strip()
            if not content:
                continue
            # Simple content signature
            norm = " ".join(content.split()[:40])
            if norm not in seen_texts:
                seen_texts.add(norm)
                unique_chunks.append(chunk)
                if len(unique_chunks) >= 5:
                    break

        # If no context found
        if not unique_chunks:
            return ChatResponse(
                answer="I cannot answer this based on the provided clinical documents as no relevant context was found.",
                sources=[]
            )
            
        # 3. Prepare Context
        context_texts = []
        sources = []
        for i, chunk in enumerate(unique_chunks):
            content = chunk.get("content", "")
            context_texts.append(f"[Document {i+1}]: {content}")
            sources.append(SourceCitation(
                content=content,
                metadata=chunk.get("metadata", {})
            ))
            
        context_str = "\n\n".join(context_texts)
        
        # 4. Construct Prompt
        system_message = SYSTEM_PROMPT.format(context=context_str)
        
        messages = [{"role": "system", "content": system_message}]
        
        # Append history if any (keep last 5 messages for context)
        if request.history:
            for msg in request.history[-5:]:
                if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
                    
        # Append current question
        messages.append({"role": "user", "content": request.message})
        
        # 5. Generate Answer with increased token limit (2048 tokens) and model attribution tracking
        attribution = None
        if hasattr(llm, "generate_response_with_metadata"):
            try:
                gen_result = await llm.generate_response_with_metadata(messages, temperature=0.0, max_tokens=2048)
                if hasattr(gen_result, "text") and hasattr(gen_result, "model") and isinstance(getattr(gen_result, "text", None), str):
                    answer = gen_result.text
                    from app.schemas.assistant import AIModelAttribution
                    attribution = AIModelAttribution(
                        provider=str(getattr(gen_result, "provider", "Google Gemini")),
                        model=str(getattr(gen_result, "model", "unknown")),
                        fallback_used=bool(getattr(gen_result, "fallback_used", False)),
                        attempted_models=list(getattr(gen_result, "attempted_models", []))
                    )
                else:
                    answer = await llm.generate_response(messages, temperature=0.0, max_tokens=2048)
            except (LLMProviderError, HTTPException):
                raise
            except Exception:
                answer = await llm.generate_response(messages, temperature=0.0, max_tokens=2048)
        else:
            answer = await llm.generate_response(messages, temperature=0.0, max_tokens=2048)
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            model_attribution=attribution
        )

        
    except LLMProviderError as e:
        logger.warning(f"Assistant LLM provider failure: {e.detail}")
        err_status = e.status_code if e.status_code in (400, 401, 403, 404, 429, 502, 503, 504) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=err_status,
            detail=e.detail
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assistant Chat Unexpected Error: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the response."
        )

