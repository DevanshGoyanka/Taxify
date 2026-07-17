# Indian Income Tax Filing Tool — Backend API

A production-ready REST API for computing and saving Indian ITR-1 and ITR-4 tax returns, built with FastAPI, SQLAlchemy, and SQLite. Paired with a React + TypeScript frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API Framework | FastAPI |
| Validation | Pydantic v2 |
| Database | SQLite (via SQLAlchemy ORM) |
| Auth | JWT (HS256, 24h expiry) + bcrypt password hashing |
| Testing | pytest |
| Frontend | React + TypeScript + Vite (in `frontend/`) |

---

## Project Structure

```
.
├── app/
│   ├── main.py                  # FastAPI app — CORS, unified error handlers, router wiring, /me endpoint
│   ├── auth/
│   │   ├── security.py          # hash_password, verify_password, create/decode JWT
│   │   └── dependencies.py      # get_current_user FastAPI dependency
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine + SessionLocal + get_db()
│   │   ├── models.py            # ORM models: User, SavedReturn
│   │   └── init_db.py           # create_tables() — called on startup
│   ├── engine/
│   │   ├── calculator.py        # compute_itr1(), compute_itr4() — core tax logic
│   │   └── constants.py         # Tax slabs, surcharge rates, deduction limits (AY 2026-27)
│   ├── routers/
│   │   ├── auth.py              # POST /auth/signup, POST /auth/login
│   │   └── itr.py               # Compute + Returns CRUD endpoints
│   └── schemas/
│       ├── auth.py              # SignupRequest, LoginRequest, TokenResponse, UserResponse
│       ├── itr1.py              # ITR1Input (full Pydantic schema with all heads of income)
│       ├── itr4.py              # ITR4Input (presumptive income — 44AD / 44ADA / 44AE)
│       └── itr_responses.py     # ITR1ComputeResponse, ITR4ComputeResponse, ReturnDetail, etc.
├── frontend/                    # React + TypeScript frontend (Vite)
│   └── src/
│       ├── api/
│       │   ├── axiosInstance.ts # Axios client — auto-attaches Bearer token, handles 401
│       │   ├── auth.ts          # login(), register(), me() → maps to our backend shape
│       │   ├── tokenManager.ts  # localStorage JWT persistence (24h TTL)
│       │   └── itrCompute.ts    # computeItr1, computeItr4, saveReturn, listReturns, getReturn
│       ├── pages/               # LoginPage, RegisterPage, DashboardPage, ITRComputationPage, ...
│       └── components/          # ProtectedRoute, AppLayout, UI primitives
├── tests/
│   ├── test_itr1_calculator.py  # 12 unit tests for the ITR-1 engine
│   ├── test_itr4_calculator.py  # Unit tests for ITR-4 engine
│   ├── test_itr1_schemas.py     # Pydantic schema validation tests
│   └── test_itr4_schemas.py     # Pydantic schema validation tests
├── .env                         # SECRET_KEY, FRONTEND_URL (not committed — see .env.example)
├── .env.example                 # Template — copy to .env and fill in values
├── .gitignore
├── requirements.txt
├── NEXT_STEPS.md                # Phase 5 remaining work + frontend integration checklist
└── README.md
```

---

## Quick Start

### Backend

```bash
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
# Edit .env — set SECRET_KEY (any 64-char random string)

# 3. Start the API  (tables created automatically on first run)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # starts at http://localhost:5173
```

Backend must be running on port 8000. `frontend/.env` already points to it.

---

## API Reference

All **error** responses share a unified shape regardless of status code:
```json
{ "error": true, "message": "Human readable message", "status_code": 401 }
```

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/health` | No | — | `{ status: "ok" }` |
| `POST` | `/auth/signup` | No | `{ email, password }` | `{ access_token, token_type }` |
| `POST` | `/auth/login` | No | `{ email, password }` | `{ access_token, token_type }` |
| `GET` | `/me` | **Bearer** | — | `{ id, email }` |
| `POST` | `/itr1/compute` | **Bearer** | `ITR1Input` JSON | Tax breakdown — 13 fields |
| `POST` | `/itr4/compute` | **Bearer** | `ITR4Input` JSON | Tax breakdown — 14 fields |
| `POST` | `/returns/save` | **Bearer** | `{ itr_type, input_data, computed_result }` | `{ id }` |
| `GET` | `/returns` | **Bearer** | — | `[{ id, itr_type, created_at }]` |
| `GET` | `/returns/{id}` | **Bearer** | — | `{ id, itr_type, input_data, computed_result, created_at }` |

**Interactive docs:** `http://localhost:8000/docs`

### ITR-1 Enum values

| Field | Accepted values |
|---|---|
| `age_bracket` | `"below_60"` / `"60_to_80"` / `"above_80"` |
| `tax_regime` | `"old"` / `"new"` |
| `property_type` | `"S"` (self-occupied) / `"L"` (let-out) / `"D"` (deemed let-out) |

### ITR-4 Enum values

| Field | Accepted values |
|---|---|
| `presumptive_scheme` | `"none"` / `"44AD"` / `"44ADA"` / `"44AE"` |

---

## Tax Engine — AY 2026-27 (Finance Act 2025)

| Feature | Detail |
|---|---|
| Old Regime slabs | Age-based: below 60 / 60–80 / above 80 |
| New Regime slabs | 4L / 8L / 12L / 16L / 20L / 24L bands (Finance Act 2025) |
| Standard deduction | Old: ₹50,000 · New: ₹75,000 |
| Section 87A rebate | Old: up to ₹12,500 (income ≤ ₹5L) · New: up to ₹60,000 with marginal relief |
| Surcharge | 10% / 15% / 25% / 37% (old) — capped at 25% (new) — with marginal relief |
| Section 80CCE cap | Combined 80C + 80CCC + 80CCD(1) capped at ₹1,50,000 |
| Section 80CCD(1B) | Additional NPS up to ₹50,000 (separate from 80CCE pool) |
| Rounding | `ROUND_HALF_EVEN` per slab; 288A/288B rounding on final figures |
| ITR-4 presumptive | 44AD (6%/8%), 44ADA (50%), 44AE (per vehicle ₹1,000/₹7,500) |

---

## Database Schema

**`user`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | VARCHAR(255) | Unique, indexed |
| hashed_password | VARCHAR(255) | bcrypt hash — never plaintext |
| created_at | DATETIME | Server default (UTC) |

**`saved_return`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | → user.id, CASCADE DELETE |
| itr_type | VARCHAR(10) | `"ITR1"` or `"ITR4"` |
| input_data | TEXT | JSON blob of form inputs |
| computed_result | TEXT | JSON blob of engine output |
| created_at | DATETIME | Server default (UTC) |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | 64-char random hex for JWT signing |
| `FRONTEND_URL` | No | `http://localhost:3000` | CORS allowed origin (backend) |

Frontend (`frontend/.env`):

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |

---

## Running Tests

```bash
pytest                          # all tests
pytest tests/test_itr1_calculator.py -v   # specific file
```

---

## Auth Flow Summary

1. User registers → `POST /auth/signup` → receives JWT
2. User logs in → `POST /auth/login` → receives JWT
3. Frontend stores JWT in `localStorage` (key: `auth_token`)
4. All protected requests include `Authorization: Bearer <token>`
5. On app load → `GET /me` → validates token, returns `{ id, email }`
6. On 401 → frontend clears storage → redirects to `/login`
7. Logout → clear localStorage → redirect (no backend call needed)
