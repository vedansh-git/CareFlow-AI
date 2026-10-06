import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.core.agent.appointment_agent import appointment_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Appointment Agent"])


@router.post("/appointment-chat", response_model=AgentChatResponse)
async def chat_with_appointment_agent(
    payload: AgentChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Multi-turn conversation with the Groq-powered CareFlow AI Appointment Agent.
    Executes bounded tool calling for doctor lookup, availability check, and appointment booking.
    Requires verified patient authentication session.
    """
    if not payload.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Messages list cannot be empty.",
        )

    # Convert to dict format for agent loop
    history = [{"role": m.role, "content": m.content} for m in payload.messages]

    try:
        result = await appointment_agent.run(
            conversation_history=history,
            current_user=current_user,
        )
        return AgentChatResponse(**result)
    except Exception as e:
        logger.error(f"Error in appointment agent endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Appointment Agent error: {str(e)}",
        )
