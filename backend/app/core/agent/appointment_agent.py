import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.core.agent.groq_provider import groq_provider, GroqProviderError
from app.core.agent.tools import AGENT_TOOLS_SCHEMA, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CareFlow AI's intelligent Appointment Agent.
Your role is to help patients find the right doctor, check real-time availability, inspect clinic details & consultation fees, and schedule or manage appointments.

Operational Guidelines:
1. DATA INTEGRITY:
   - ALWAYS use the provided tools (`search_doctors`, `get_doctor_details`, `check_doctor_availability`, `get_my_appointments`, `cancel_appointment`, `prepare_booking_confirmation`, `book_appointment`).
   - ONLY provide information grounded in real tool outputs. If a field (e.g. bio, phone, fee) is missing or null, explicitly state that it is unavailable rather than inventing details.
   - Contact phone numbers with +1-555-010X are non-contactable demonstration numbers.
   - Ratings and reviews returned from tool calls with 'is_demo: True' are sample demonstration feedback.

2. APPOINTMENT BOOKING CONVERSATION FLOW:
   - When a patient expresses interest in booking an appointment, identify:
     (a) Specialty or Doctor preference
     (b) Target date (if relative, e.g. "tomorrow" or "next Monday", calculate based on current date)
     (c) Preferred time of day
   - Always call `check_doctor_availability` to retrieve actual free slots before proposing times.
   - Once a doctor, date, and slot are identified, use `prepare_booking_confirmation` to construct the booking summary.
   - ALWAYS present the booking details (Doctor Name, Specialty, Clinic Address, Fee, Date, Time) and ASK FOR EXPLICIT CONFIRMATION:
     "Would you like me to book your appointment with [Doctor Name] on [Date] at [Time]?"
   - NEVER call `book_appointment` with `confirmed: true` unless the patient has explicitly said yes/confirmed.

3. SECURITY & TONE:
   - Maintain a compassionate, professional, and concise healthcare assistant tone.
   - If the patient asks for medical diagnosis, provide a brief helpful overview and advise them to consult a licensed physician during their appointment.
   - Today's date reference: {current_date} ({current_day}).
"""


class AppointmentAgent:
    """Orchestrator for multi-turn tool calling with Groq."""

    def __init__(self):
        self.groq = groq_provider
        self.max_tool_turns = 5

    async def run(
        self,
        conversation_history: List[Dict[str, str]],
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute agent reasoning and bounded tool calling loop.
        """
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        current_day_str = now.strftime("%A")

        system_message = {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                current_date=current_date_str,
                current_day=current_day_str,
            ),
        }

        # Build message history
        messages: List[Dict[str, Any]] = [system_message]
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        executed_tools: List[Dict[str, Any]] = []
        pending_confirmation: Optional[Dict[str, Any]] = None
        booking_result: Optional[Dict[str, Any]] = None
        last_model_meta: Dict[str, Any] = {}

        for turn in range(self.max_tool_turns):
            logger.info(f"Agent Turn {turn + 1}/{self.max_tool_turns}")

            try:
                response = await self.groq.chat_completion(
                    messages=messages,
                    tools=AGENT_TOOLS_SCHEMA,
                    tool_choice="auto",
                )
            except GroqProviderError as ge:
                logger.error(f"Groq execution failed: {str(ge)}")
                return {
                    "content": (
                        "I am currently having trouble connecting to the AI booking service. "
                        "You can still book your appointment directly using the **Book Manually** tab above at any time."
                    ),
                    "tool_calls_executed": executed_tools,
                    "error": str(ge),
                    "metadata": {
                        "provider": "Groq",
                        "status": "error",
                        "error_type": ge.error_type,
                    },
                }

            msg = response.get("message", {})
            last_model_meta = {
                "provider": "Groq",
                "model_used": response.get("model_used"),
                "fallback_used": response.get("fallback_used", False),
                "attempted_models": response.get("attempted_models", []),
            }

            tool_calls = msg.get("tool_calls")

            # Append assistant message to context
            messages.append(msg)

            if not tool_calls:
                # No more tools requested, agent has finished speaking
                return {
                    "content": msg.get("content") or "How else can I assist you with your appointment today?",
                    "tool_calls_executed": executed_tools,
                    "pending_confirmation": pending_confirmation,
                    "booking_result": booking_result,
                    "metadata": last_model_meta,
                }

            # Execute all tool calls
            for tc in tool_calls:
                tc_id = tc.get("id")
                func = tc.get("function", {})
                func_name = func.get("name")
                raw_args = func.get("arguments", "{}")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                logger.info(f"Executing tool '{func_name}' (ID: {tc_id}) with args: {args}")
                tool_output = execute_tool(func_name, args, current_user)

                executed_tools.append({
                    "id": tc_id,
                    "tool": func_name,
                    "arguments": args,
                    "output": tool_output,
                })

                # Check if tool produced a booking confirmation or booking result
                if func_name == "prepare_booking_confirmation" and tool_output.get("status") == "ready_for_confirmation":
                    pending_confirmation = tool_output.get("confirmation_details")
                elif func_name == "book_appointment" and tool_output.get("status") == "booking_success":
                    booking_result = tool_output

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": func_name,
                    "content": json.dumps(tool_output),
                })

        # Exceeded turns fallback
        return {
            "content": msg.get("content") or "I have processed your request. Let me know if you would like to proceed.",
            "tool_calls_executed": executed_tools,
            "pending_confirmation": pending_confirmation,
            "booking_result": booking_result,
            "metadata": last_model_meta,
        }


# Global instance
appointment_agent = AppointmentAgent()
