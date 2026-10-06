from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from app.core.security import get_current_user
from app.services.appointment_service import appointment_service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
)

router = APIRouter()


@router.get("/appointments", response_model=List[AppointmentResponse], tags=["Appointments"])
async def list_appointments(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AppointmentResponse]:
    """
    List appointments for the current authenticated user:
    - If patient: returns patient's appointments.
    - If doctor: returns doctor's assigned appointments.
    """
    return appointment_service.get_user_appointments(current_user)


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Appointments"]
)
async def create_appointment(
    payload: AppointmentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AppointmentResponse:
    """
    Create a new appointment for the authenticated patient:
    - Validates doctor is active
    - Validates slot falls within doctor's availability
    - Validates no conflict / double booking
    """
    return appointment_service.create_appointment(payload, current_user)


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    tags=["Appointments"]
)
async def get_appointment(
    appointment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AppointmentResponse:
    """
    Retrieve specific appointment details.
    Enforces that patients can only view their own appointments, and doctors can view only assigned appointments.
    """
    return appointment_service.get_appointment_by_id(appointment_id, current_user)


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    tags=["Appointments"]
)
async def cancel_appointment(
    appointment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AppointmentResponse:
    """
    Cancel an appointment.
    Patients can cancel only their own appointments.
    """
    return appointment_service.cancel_appointment(appointment_id, current_user)
