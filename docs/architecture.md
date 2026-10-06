# CareFlow AI — System Architecture & Blueprint

## System Overview
CareFlow AI is an AI-Powered Clinical Workflow & Documentation Assistant designed for modern healthcare environments. It streamlines doctor consultations, automates SOAP note generation, provides intelligent patient record search via RAG, and predicts appointment no-shows using machine learning.

---

## High-Level Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                    │
│        (UI Shell, Status Badges, Router, Axios Client)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / CORS API Requests
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python FastAPI Backend                    │
│    (Core Config, Health Routes, Modular API Controllers)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Future Phase Integration)
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ Supabase DB   │      │ AI Provider / │      │  ML No-Show   │
│ & pgvector    │      │ MCP Tools     │      │   Predictor   │
└───────────────┘      └───────────────┘      └───────────────┘
```

---

## Directory Blueprint
- `frontend/`: React + Vite web application containing UI layouts, components, custom hooks, and API services.
- `backend/`: FastAPI web server containing modular routes, configuration management, schemas, and test suite.
- `docs/`: System documentation and architectural blueprints.

---

## Development Milestones
1. **Step 1 — Project Foundation (Completed)**: Core technical scaffolding, backend health route, frontend status integration, environment configs, CORS setup.
2. **Step 2 — Database & Data Layer**: Supabase setup & schema migrations (Appointments, Patient Records, Consultations).
3. **Step 3 — Doctor & Patient Workflows**: Appointment scheduling and clinical management.
4. **Step 4 — AI & RAG Engine**: Clinical documentation assistant, speech-to-text, SOAP note generation with human-in-the-loop validation.
5. **Step 5 — ML Predictive Module**: Appointment no-show prediction model integration.
