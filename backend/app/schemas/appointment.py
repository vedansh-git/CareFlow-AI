from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AppointmentStatusEnum(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentCreate(BaseModel):
    doctor_id: str
    appointment_date: str = Field(..., description="YYYY-MM-DD")
    start_time: str = Field(..., description="HH:MM or HH:MM:SS")
    end_time: str = Field(..., description="HH:MM or HH:MM:SS")
    reason: Optional[str] = Field(None, max_length=500)


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatusEnum] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    appointment_date: str
    start_time: str
    end_time: str
    reason: Optional[str] = None
    status: str = "scheduled"
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    # Joined metadata for presentation
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    patient_name: Optional[str] = None
