import re
import json
import logging
from typing import Dict, Any, Optional
from app.core.llm.provider import (
    LLMProviderInterface,
    LLMProviderError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError
)
from app.schemas.clinical_notes import SoapGenerateResponse

logger = logging.getLogger(__name__)

SOAP_SYSTEM_PROMPT = """You are CareFlow AI, an expert clinical documentation assistant.
Your job is to transform a doctor-patient conversation or medical consultation transcript into a highly structured, professional SOAP note.

CLINICAL DOCUMENTATION RULES:
1. Divide your response into exactly FOUR distinct sections:
   - Subjective: Chief complaint, history of present illness, symptoms, and medical history reported by the patient.
   - Objective: Vital signs, physical examination findings, and diagnostic measurements explicitly mentioned.
   - Assessment: Clinical diagnosis, differential diagnoses, or physician impression explicitly stated or concluded in the encounter.
   - Plan: Documented medications (with exact doses stated), diagnostic tests ordered, referrals, lifestyle recommendations, and follow-up timing.

2. NEVER INVENT OR HALLUCINATE:
   - If information for any section was not discussed or documented in the transcript, write EXACTLY "Not documented".
   - Never invent diagnoses, vital signs, physical exam findings, medications, dosages, or follow-up dates that were not mentioned.

3. OUTPUT FORMAT:
You MUST respond with a valid JSON object strictly formatted as:
{
  "subjective": "...",
  "objective": "...",
  "assessment": "...",
  "plan": "..."
}
Do not include any surrounding markdown commentary or intro text outside the JSON object.
"""


class SoapNoteGenerator:
    def __init__(self, llm_provider: LLMProviderInterface):
        self.llm = llm_provider

    def _parse_soap_response(self, raw_text: str) -> Dict[str, str]:
        """
        Parses JSON response or falls back to robust regex header extraction if LLM emitted markdown.
        """
        cleaned = raw_text.strip()
        # Strip markdown code fences ```json ... ``` if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 2:
                # remove first line (```json) and last line (```)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

        # Try direct JSON parsing
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {
                    "subjective": str(data.get("subjective") or "Not documented").strip(),
                    "objective": str(data.get("objective") or "Not documented").strip(),
                    "assessment": str(data.get("assessment") or "Not documented").strip(),
                    "plan": str(data.get("plan") or "Not documented").strip(),
                }
        except Exception:
            logger.warning("SOAP Note JSON parsing failed; falling back to section regex parsing.")

        # Fallback regex parsing for Markdown / Text formats
        sections = {
            "subjective": "Not documented",
            "objective": "Not documented",
            "assessment": "Not documented",
            "plan": "Not documented",
        }

        # Pattern matches headers like 'Subjective:', '### Subjective', '**Subjective:**'
        pattern = r"(?:^|\n)(?:###|\*\*|#)?\s*(Subjective|Objective|Assessment|Plan)[:\s\*]*(.*?)(?=(?:\n(?:###|\*\*|#)?\s*(?:Subjective|Objective|Assessment|Plan)[:\s\*]|\Z))"
        matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)

        for section_name, content in matches:
            key = section_name.lower().strip()
            text_val = content.strip()
            # Clean trailing asterisks or markdown syntax
            text_val = re.sub(r"^\*+|\*+$", "", text_val).strip()
            if key in sections and text_val:
                sections[key] = text_val

        # If nothing matched at all, place the whole text in subjective
        if all(v == "Not documented" for v in sections.values()) and raw_text.strip():
            sections["subjective"] = raw_text.strip()

        return sections

    async def generate_soap_note(
        self,
        transcript: str,
        patient_context: Optional[str] = None
    ) -> SoapGenerateResponse:
        """
        Generates a 4-section SOAP note from transcript using the configured LLM provider.
        """
        if not transcript or not transcript.strip():
            return SoapGenerateResponse(
                subjective="Not documented",
                objective="Not documented",
                assessment="Not documented",
                plan="Not documented"
            )

        user_content = f"TRANSCRIPT:\n{transcript.strip()}"
        if patient_context and patient_context.strip():
            user_content = f"PATIENT CONTEXT:\n{patient_context.strip()}\n\n{user_content}"

        messages = [
            {"role": "system", "content": SOAP_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        # Call LLM with metadata tracking
        attribution = None
        if hasattr(self.llm, "generate_response_with_metadata"):
            try:
                gen_result = await self.llm.generate_response_with_metadata(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=2048
                )
                if hasattr(gen_result, "text") and hasattr(gen_result, "model") and isinstance(getattr(gen_result, "text", None), str):
                    raw_response = gen_result.text
                    from app.schemas.clinical_notes import AIModelAttribution
                    attribution = AIModelAttribution(
                        provider=str(getattr(gen_result, "provider", "Google Gemini")),
                        model=str(getattr(gen_result, "model", "unknown")),
                        fallback_used=bool(getattr(gen_result, "fallback_used", False)),
                        attempted_models=list(getattr(gen_result, "attempted_models", []))
                    )
                else:
                    raw_response = await self.llm.generate_response(
                        messages=messages,
                        temperature=0.0,
                        max_tokens=2048
                    )
            except LLMProviderError:
                raise
            except Exception:
                raw_response = await self.llm.generate_response(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=2048
                )
        else:
            raw_response = await self.llm.generate_response(
                messages=messages,
                temperature=0.0,
                max_tokens=2048
            )

        parsed = self._parse_soap_response(raw_response)

        return SoapGenerateResponse(
            subjective=parsed["subjective"],
            objective=parsed["objective"],
            assessment=parsed["assessment"],
            plan=parsed["plan"],
            model_attribution=attribution
        )
