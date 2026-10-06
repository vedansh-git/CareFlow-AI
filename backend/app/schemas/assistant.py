from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class AIModelAttribution(BaseModel):
    provider: str = Field("Google Gemini", description="AI provider name")
    model: str = Field(..., description="Actual model that generated the response")
    fallback_used: bool = Field(False, description="Whether fallback model was used")
    attempted_models: List[str] = Field(default_factory=list, description="Sequence of attempted models")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's input message.")
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Previous conversation history.")


class SourceCitation(BaseModel):
    content: str
    metadata: Dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    model_attribution: Optional[AIModelAttribution] = None
