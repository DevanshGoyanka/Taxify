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

### Core Auth & User
| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/health` | No | — | `{ status: "ok" }` |
| `POST` | `/auth/signup` | No | `{ email, password }` | `{ access_token, token_type }` |
| `POST` | `/auth/login` | No | `{ email, password }` | `{ access_token, token_type }` |
| `GET` | `/me` | **Bearer** | — | `{ id, email }` |

### Client Management
| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/clients` | **Bearer** | — | `[ClientResponse]` |
| `POST` | `/clients` | **Bearer** | `ClientCreate` | `ClientResponse` |
| `GET` | `/clients/{id}` | **Bearer** | — | `ClientResponse` |
| `PUT` | `/clients/{id}` | **Bearer** | `ClientUpdate` | `ClientResponse` |
| `DELETE` | `/clients/{id}` | **Bearer** | — | `{ message: "Client deleted successfully." }` |
| `GET` | `/clients/{id}/years` | **Bearer** | — | `[str]` (list of assessment years) |
| `GET` | `/clients/{id}/pan-analysis` | **Bearer** | — | PAN entity type analysis details |
| `POST` | `/clients/{id}/itr-classification` | **Bearer** | `{ hasBusinessIncome, ... }` | `{ recommendedForm, reason }` |

### Client ITR Data
| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/clients/{id}/itr/{year}` | **Bearer** | — | Saved ITR form JSON |
| `PUT` | `/clients/{id}/itr/{year}` | **Bearer** | Form data JSON | `{ message: "ITR saved successfully", itr_type }` |
| `POST` | `/clients/{id}/itr/{year}/validate` | **Bearer** | Form data JSON | `{ valid, errors: [], warnings: [] }` |
| `GET` | `/clients/{id}/itr/{year}/download` | **Bearer** | — | File download (CBDT JSON Utility format) |
| `GET` | `/clients/{id}/itr/{year}/download-pdf` | **Bearer** | — | File download (PDF Computation report) |

### PAN & Tax Engine
| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/pan/{pan}/validate` | No | — | `{ pan, valid, message }` |
| `GET` | `/pan/{pan}/analyze` | No | — | PAN entity type breakdown |
| `POST` | `/tax-summary/compute` | **Bearer** | Form data JSON | Full tax breakdown (grossSalary, taxableIncome, cess, etc.) |
| `POST` | `/business-income/calculate` | No | `BusinessIncomeRequest` | `BusinessIncomeResponse` |
| `POST` | `/business-income/validate` | No | `BusinessIncomeRequest` | `BusinessValidationResponse` |
| `POST` | `/capital-gains/calculate` | No | `CapitalGainsRequest` | `CapitalGainsResponse` |
| `POST` | `/capital-gains/calculate-batch` | No | `{ transactions: [...] }` | `{ transactions, summary }` |

### Portal Integrations
| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `POST` | `/integration/form16/extract` | **Bearer** | multipart `file` | Extracted salary & TDS details |
| `POST` | `/integration/ais-json/import` | **Bearer** | multipart `file` | Parsed AISData |
| `POST` | `/integration/tis/import` | **Bearer** | multipart `file` | Parsed TISData |
| `POST` | `/integration/26as/import` | **Bearer** | multipart `file` | Parsed Form26ASData |
| `POST` | `/prefill/autoPopulateAll` | **Bearer** | `{ aisData, form26ASData, tisData }` | Populated form fields dictionary |

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

**`client`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | → user.id |
| pan | VARCHAR(10) | Unique, uppercase |
| name | VARCHAR(255) | |
| email | VARCHAR(255) | |
| mobile | VARCHAR(15) | |
| dob | VARCHAR(10) | YYYY-MM-DD |
| aadhaar | VARCHAR(12) | |
| created_at | DATETIME | |

**`client_itr`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| client_id | INTEGER FK | → client.id |
| year | VARCHAR(7) | Assessment Year (e.g. "2025-26") |
| itr_type | VARCHAR(10) | "ITR-1" or "ITR-4" |
| status | VARCHAR(50) | "Not Started", "In Progress", "Filed" |
| form_data | TEXT | JSON string of full form values |
| computed_result | TEXT | JSON string of tax computation results |
| created_at | DATETIME | |


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
