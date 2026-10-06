# CareFlow AI — AI-Powered Clinical Workflow & Documentation Assistant

CareFlow AI is an AI-powered clinical workflow and documentation assistant built for final-year B.Tech CSE presentation. The application will eventually feature appointment management, speech-to-text recording, RAG over synthetic medical records, AI SOAP note generation with human-in-the-loop approval, and machine learning no-show prediction.

---

## 📌 Current Development Status
**Step 2 — Authentication & Database Foundation**

The core authentication infrastructure and PostgreSQL database schema are established. The application integrates Supabase Auth for identity, enforces Row Level Security (RLS) policies at the database layer, provides protected React routes, and validates Bearer JWT tokens in FastAPI backend endpoints.

---

## 🗄️ Database Schema & RLS Architecture
The PostgreSQL database schema is defined in [`docs/database/schema.sql`](file:///c:/Users/LENOVO/OneDrive/Desktop/project3/docs/database/schema.sql) (and mirrored at [`backend/database/schema.sql`](file:///c:/Users/LENOVO/OneDrive/Desktop/project3/backend/database/schema.sql)).

### 1. Enum Types
- `user_role`: `('patient', 'doctor', 'admin')`

### 2. Core Tables
- `public.profiles`: Links to `auth.users(id)`. Stores `full_name`, `role`, `phone`, timestamps.
- `public.patients`: Foreign key to `profiles(id)`. Stores patient DOB, gender, record timestamp.
- `public.doctors`: Foreign key to `profiles(id)`. Stores specialty, qualification, bio, active status.

### 3. Server-Side Registration Trigger
`public.handle_new_user()` runs `AFTER INSERT ON auth.users`:
- Creates profile row with **mandatory default role = `patient`**.
- Creates patient record row.
- **Security Rule**: Role selection is strictly prohibited in the client UI.

### 4. Row Level Security (RLS) Policies
- `profiles`: Users can read their own profile. Profile updates enforce that users **cannot modify their own role**.
- `patients`: Patients can read and update only their own patient record (`auth.uid() = profile_id`).
- `doctors`: Authenticated users can view active doctors (`is_active = true`).

---

## 🔐 Authentication & Authorization Flow

```
Browser (React + Vite)
  ↓ [Email / Password Sign-In or Sign-Up]
Supabase Auth Service
  ↓ [Returns JWT Access Token]
React AuthContext (State & Protected Routes)
  ↓ [API Request with Authorization: Bearer <JWT>]
FastAPI Backend (security.py)
  ↓ [JWT Validation & Claim Verification]
Protected API Route (/api/me) -> Returns Authenticated User Identity
```

---

## 🛠️ Tech Stack (Step 2)
- **Frontend**: React 18, Vite 5, JavaScript, Tailwind CSS 3, React Router DOM 6, `@supabase/supabase-js`, Axios, Lucide React Icons
- **Backend**: Python 3.14, FastAPI, Uvicorn, Pydantic v2, PyJWT, Cryptography, Pytest, HTTPX

---

## 📂 Project Structure

```
careflow-ai/
│
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components (ProtectedRoute, StatusBadge)
│   │   ├── context/          # AuthContext provider & useAuth hook
│   │   ├── lib/              # Supabase client initializer (supabase.js)
│   │   ├── pages/            # Page views (Home, Login, Register)
│   │   ├── layouts/          # MainLayout shell with auth header & logout
│   │   ├── services/         # Axios API client with JWT Bearer interceptor
│   │   ├── hooks/            # Custom hooks (useBackendHealth)
│   │   └── utils/            # Helper utilities and constants
│   ├── package.json          # Frontend dependencies (@supabase/supabase-js, etc.)
│   └── vite.config.js        # Vite configuration
│
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point & CORS
│   │   ├── api/              # API routers (health.py, auth.py)
│   │   ├── core/             # Config (config.py) & JWT Security (security.py)
│   │   ├── schemas/          # Data schemas (health.py, user.py)
│   │   ├── services/         # Service layer directory
│   │   └── utils/            # Utilities directory
│   ├── database/
│   │   └── schema.sql        # Reproducible SQL schema & RLS policies
│   ├── tests/                # Pytest test suite (test_health.py, test_auth.py)
│   └── requirements.txt      # Python dependencies (PyJWT, cryptography, etc.)
│
├── docs/                     # Documentation & database schema
├── .gitignore                # Git ignore rules
├── .env.example              # Example environment variables
└── README.md                 # Project documentation
```

---

## ⚙️ Required Environment Variables

### Root / Frontend `.env`:
```ini
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
VITE_API_BASE_URL=http://localhost:8000
```

### Backend `.env`:
```ini
PROJECT_NAME="CareFlow AI"
ENVIRONMENT="development"
PORT=8000
CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_ANON_KEY="your-supabase-publishable-key"
SUPABASE_JWT_SECRET="your-supabase-jwt-secret"
```

---

## 🚀 Local Setup Instructions

### Prerequisites
- **Node.js**: v18.0+
- **Python**: v3.10+
- **Supabase Project** (or local Supabase emulator)

---

### 1. Database Setup in Supabase
1. Open your Supabase Project Dashboard -> **SQL Editor**.
2. Copy the contents of [`docs/database/schema.sql`](file:///c:/Users/LENOVO/OneDrive/Desktop/project3/docs/database/schema.sql).
3. Click **Run** to create enums, tables, functions, triggers, indexes, and RLS policies.

---

### 2. Backend Setup

1. Navigate to `backend`:
   ```bash
   cd backend
   ```
2. Activate virtual environment:
   - **Windows**: `.\venv\Scripts\Activate.ps1`
   - **macOS/Linux**: `source venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run unit test suite:
   ```bash
   pytest
   ```
5. Start FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

Backend server runs at `http://localhost:8000`.

---

### 3. Frontend Setup

1. Navigate to `frontend`:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start Vite development server:
   ```bash
   npm run dev
   ```

Frontend application runs at `http://localhost:5173`.

---

## 🧪 Testing Authentication & Endpoints

### 1. Frontend Route Testing
- Visit `http://localhost:5173/` -> Automatically redirects to `/login` if unauthenticated.
- Visit `http://localhost:5173/register` -> Register a new patient account (Full Name, Email, Password).
- Sign in with credentials -> Redirects to authenticated Home dashboard (`/`).
- Click **Sign Out** -> Clears session and redirects back to `/login`.

### 2. Backend JWT Protected Endpoint Testing
- **Unauthenticated**:
  ```bash
  curl -X GET http://localhost:8000/api/me
  # Response: HTTP 401 Unauthorized
  ```
- **Authenticated with Bearer Token**:
  ```bash
  curl -X GET http://localhost:8000/api/me \
       -H "Authorization: Bearer <SUPABASE_JWT_ACCESS_TOKEN>"
  # Response: HTTP 200 OK
  # {"id": "...", "email": "...", "full_name": "...", "role": "patient", "authenticated": true}
  ```
