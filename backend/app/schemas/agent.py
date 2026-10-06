from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class AgentChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Chronological chat conversation history")


class BookingConfirmationDetails(BaseModel):
    doctor_id: str
    doctor_name: str
    specialty: Optional[str] = None
    clinic_address: Optional[str] = None
    contact_phone: Optional[str] = None
    consultation_fee: Optional[float] = None
    appointment_date: str
    appointment_time: str
    end_time: Optional[str] = None
    consultation_type: str = "in_person"
    notes: Optional[str] = None


class AgentChatResponse(BaseModel):
    content: str
    tool_calls_executed: List[Dict[str, Any]] = []
    pending_confirmation: Optional[Dict[str, Any]] = None
    booking_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}
