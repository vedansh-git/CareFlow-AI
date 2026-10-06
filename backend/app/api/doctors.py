from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from app.core.security import get_current_user
from app.services.doctor_service import doctor_service
from app.schemas.doctor import (
    DoctorResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityCreate,
    DoctorAvailabilityUpdate,
)

router = APIRouter()


# -------------------------------------------------------------
# Public / Authenticated Doctor Endpoints
# -------------------------------------------------------------

@router.get("/doctors", response_model=List[DoctorResponse], tags=["Doctors"])
async def list_doctors(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[DoctorResponse]:
    """
    Retrieve all active doctor profiles.
    Requires authenticated user.
    """
    return doctor_service.get_all_active_doctors()


@router.get("/doctors/{doctor_id}", response_model=DoctorResponse, tags=["Doctors"])
async def get_doctor_details(
    doctor_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DoctorResponse:
    """
    Retrieve details for a specific active doctor.
    """
    return doctor_service.get_doctor_by_id(doctor_id)


@router.get("/doctors/{doctor_id}/availability", response_model=List[DoctorAvailabilityResponse], tags=["Doctors"])
async def get_doctor_availability(
    doctor_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[DoctorAvailabilityResponse]:
    """
    Retrieve active weekly availability slots for a doctor.
    """
    return doctor_service.get_doctor_availability(doctor_id)


# -------------------------------------------------------------
# Doctor Self-Management Endpoints
# -------------------------------------------------------------

@router.get("/doctor/me", response_model=DoctorResponse, tags=["Doctor Portal"])
async def get_my_doctor_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DoctorResponse:
    """
    Retrieve the doctor profile of the logged-in doctor user.
    """
    return doctor_service.get_doctor_by_profile_id(current_user["id"])


@router.get("/doctor/me/availability", response_model=List[DoctorAvailabilityResponse], tags=["Doctor Portal"])
async def get_my_availability(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[DoctorAvailabilityResponse]:
    """
    Retrieve all availability slots (active and inactive) for the logged-in doctor.
    """
    return doctor_service.get_doctor_me_availability(current_user["id"])


@router.post(
    "/doctor/me/availability",
    response_model=DoctorAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Doctor Portal"]
)
async def create_my_availability(
    payload: DoctorAvailabilityCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DoctorAvailabilityResponse:
    """
    Create a new availability slot for the logged-in doctor.
    """
    return doctor_service.add_doctor_availability(current_user["id"], payload)


@router.put(
    "/doctor/me/availability/{availability_id}",
    response_model=DoctorAvailabilityResponse,
    tags=["Doctor Portal"]
)
async def update_my_availability(
    availability_id: str,
    payload: DoctorAvailabilityUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DoctorAvailabilityResponse:
    """
    Update an existing availability slot for the logged-in doctor.
    """
    return doctor_service.update_doctor_availability(
        profile_id=current_user["id"],
        availability_id=availability_id,
        payload=payload
    )


@router.delete(
    "/doctor/me/availability/{availability_id}",
    tags=["Doctor Portal"]
)
async def delete_my_availability(
    availability_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete an availability slot for the logged-in doctor.
    """
    return doctor_service.delete_doctor_availability(
        profile_id=current_user["id"],
        availability_id=availability_id
    )
