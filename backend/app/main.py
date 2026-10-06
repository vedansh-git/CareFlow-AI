from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.doctors import router as doctors_router
from app.api.appointments import router as appointments_router
from app.api.rag import router as rag_router
from app.api.assistant import router as assistant_router
from app.api.documents import router as documents_router
from app.api.clinical_notes import router as clinical_notes_router
from app.api.agent import router as agent_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CareFlow AI - Clinical Workflow & Documentation Assistant API",
    version="0.1.0",
)

# Configure CORS middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
def read_root():
    return {"message": "CareFlow AI API is running"}


# Include API routers
app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])
app.include_router(doctors_router, prefix=settings.API_V1_STR, tags=["Doctors"])
app.include_router(appointments_router, prefix=settings.API_V1_STR, tags=["Appointments"])
app.include_router(rag_router, prefix=f"{settings.API_V1_STR}/rag", tags=["RAG"])
app.include_router(assistant_router, prefix=f"{settings.API_V1_STR}/assistant", tags=["Assistant"])
app.include_router(documents_router, prefix=f"{settings.API_V1_STR}/documents", tags=["Documents"])
app.include_router(clinical_notes_router, prefix=f"{settings.API_V1_STR}/clinical-notes", tags=["Clinical Documentation"])
app.include_router(agent_router, prefix=settings.API_V1_STR, tags=["Appointment Agent"])

