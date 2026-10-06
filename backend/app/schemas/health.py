from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "0.1.0"
