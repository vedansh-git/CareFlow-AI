from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DemoReview(BaseModel):
    author: str = "Demonstration Patient"
    rating: int = Field(5, ge=1, le=5)
    comment: str
    date: Optional[str] = None
    is_demo: bool = True


class DoctorResponse(BaseModel):
    id: str
    profile_id: str
    full_name: str
    email: Optional[str] = None
    specialty: Optional[str] = "General Medicine"
    qualification: Optional[str] = "MD"
    bio: Optional[str] = None
    clinic_address: Optional[str] = None
    contact_phone: Optional[str] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    demo_reviews: Optional[List[Dict[str, Any]]] = None
    is_active: bool = True


class DoctorUpdate(BaseModel):
    specialty: Optional[str] = None
    qualification: Optional[str] = None
    bio: Optional[str] = None
    clinic_address: Optional[str] = None
    contact_phone: Optional[str] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    is_active: Optional[bool] = None


class DoctorAvailabilityBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Sunday, 1=Monday, ..., 6=Saturday")
    start_time: str = Field(..., description="HH:MM or HH:MM:SS format")
    end_time: str = Field(..., description="HH:MM or HH:MM:SS format")
    is_active: bool = True


class DoctorAvailabilityCreate(DoctorAvailabilityBase):
    pass


class DoctorAvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_active: Optional[bool] = None


class DoctorAvailabilityResponse(BaseModel):
    id: str
    doctor_id: str
    day_of_week: int
    day_name: Optional[str] = None
    start_time: str
    end_time: str
    is_active: bool
