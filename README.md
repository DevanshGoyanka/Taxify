# Taxify — Indian Income Tax Filing Application

A full-stack application for computing, managing, and filing Indian ITR-1 through ITR-4 tax returns. Built with FastAPI, SQLAlchemy, and React + TypeScript.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| API Framework | FastAPI |
| Validation | Pydantic v2 |
| Database | SQLite (via SQLAlchemy ORM) |
| Auth | JWT (HS256, 24h expiry) + bcrypt password hashing |
| Numeric Precision | `decimal.Decimal` for all monetary values |
| Testing | pytest |
| Frontend | React + TypeScript + Vite (in `frontend/`) |
| Browser Automation | Playwright (in `app/automation/`) |
| ERI Integration | ITD e-Filing ERI API (in `app/eri/`, wired via `app/routers/eri.py`) |

---

## Project Structure

```
.
├── app/
│   ├── main.py                     # FastAPI app — CORS, error handlers, router wiring, /me, /health
│   ├── vault.py                    # CLI utility — PAN/DOB validation, AIS decryption, CSV import
│   ├── auth/
│   │   ├── security.py             # hash_password, verify_password, create/decode JWT
│   │   └── dependencies.py         # get_current_user FastAPI dependency
│   ├── db/
│   │   ├── database.py             # SQLAlchemy engine + SessionLocal + get_db()
│   │   ├── models.py               # ORM models: User, SavedReturn, Client, ClientITR
│   │   └── init_db.py              # create_tables() — called on startup
│   ├── engine/
│   │   ├── constants.py            # Tax slabs, surcharge rates, deduction limits (AY 2026-27)
│   │   ├── validators.py           # Unified validation engine (field, cross-field, arithmetic)
│   │   ├── common/                 # Shared tax engine: slabs, surcharge, rebate, cess, rounding
│   │   ├── calculators/            # itr1.py, itr2.py, itr3.py, itr4.py — core compute logic
│   │   ├── schedules/              # Income & deduction schedules (salary, HP, CG, business, etc.)
│   │   └── itd/                    # CBDT-compliant ITD JSON builders per form
│   ├── routers/
│   │   ├── auth.py                 # POST /auth/signup, POST /auth/login
│   │   ├── itr.py                  # POST /itr{1,3,4}/compute, /returns/save, /returns (CRUD)
│   │   ├── clients.py              # /clients CRUD + PAN analysis + ITR classification
│   │   ├── client_itr.py           # /clients/{id}/itr/{year} save/load/validate/download
│   │   ├── integration.py          # Form 16, AIS, TIS, 26AS import + prefill + ERI routes
│   │   ├── pan.py                  # /pan/{pan}/validate, /pan/{pan}/analyze
│   │   ├── tax.py                  # /tax-summary/compute, /business-income/*, /capital-gains/*
│   │   ├── dashboard.py            # /dashboard/stats
│   │   └── eri.py                  # /eri/* — login, add-client, prefill, e-verify, acknowledgement
│   ├── schemas/
│   │   ├── auth.py                 # SignupRequest, LoginRequest, TokenResponse, UserResponse
│   │   ├── clients.py              # ClientCreate, ClientUpdate, ClientResponse
│   │   ├── itr1.py                 # ITR1Input (full Pydantic schema)
│   │   ├── itr2.py                 # ITR2Input (full Pydantic schema — no public compute endpoint yet)
│   │   ├── itr3.py                 # ITR3Input (full Pydantic schema)
│   │   ├── itr4.py                 # ITR4Input (presumptive schemes)
│   │   ├── itr_responses.py        # ITR1/3/4ComputeResponse, ReturnDetail, etc.
│   │   ├── eri.py                  # ERI request schemas
│   │   └── security/
│   │       └── portal_crypto.py    # Encrypt/decrypt income-tax portal passwords
│   ├── eri/                        # ERI (e-Return Intermediary) ITD API client
│   │   ├── login.py                # ERI login/logout session management
│   │   ├── client.py               # Low-level ERI HTTP client
│   │   ├── envelope.py             # XML envelope construction + password encryption
│   │   ├── add_client.py           # Add taxpayer, validate OTP, register + validate
│   │   ├── prefill.py              # Prefill data from ITD
│   │   ├── everify.py              # E-verify via EVC/OTP
│   │   ├── acknowledgement.py      # Download ITR acknowledgement PDF
│   │   └── exceptions.py           # ERI-specific error types
│   ├── services/
│   │   ├── prefill_service.py      # Prefill orchestration logic
│   │   └── submission_service.py   # ITR submission orchestration
│   └── automation/                 # ⚠ Standalone Playwright-based portal automation (NOT wired to API)
│       ├── browser.py              # Playwright browser launcher
│       ├── auth.py                 # Portal login automation
│       ├── downloader.py           # Core PDF downloader
│       ├── downloader_168.py       # Form 168 downloader
│       ├── downloader_26as.py      # 26AS PDF downloader
│       ├── downloader_ais_tis.py   # AIS/TIS PDF downloader
│       ├── pdf_unlocker.py         # PDF password removal
│       ├── ais_converter.py        # AIS PDF → JSON
│       ├── as26_converter.py       # 26AS PDF → structured data
│       ├── ais_json_decryptor.py   # AIS encrypted JSON decryption
│       ├── ais_structure_report.py # AIS structural analysis
│       ├── emailer.py              # Email PDFs to clients
│       └── errors.py               # Automation error types
├── ais_extractor/                  # ⚠ Standalone AIS PDF extraction tool (NOT wired to API)
│   ├── extractor.py                # State-machine AIS PDF parser
│   ├── as26_extractor.py           # 26AS PDF parser
│   ├── tis_extractor.py            # TIS PDF parser
│   └── reconciliation.py           # AIS ↔ 26AS reconciliation
├── schemas/                        # Standalone/older schema copies (used by CLI tools)
│   ├── itr1_input.py
│   ├── itr4_input.py
│   └── __init__.py
├── frontend/                       # React + TypeScript frontend (Vite)
│   └── src/
│       ├── api/                    # Axios-based API client modules (auth, clients, itr, dashboard, etc.)
│       ├── pages/                  # 18 page components (Dashboard, Clients, ITRComputation, Filing, etc.)
│       ├── components/             # Shared UI + form components (EmployerEntryManager, CapitalGains, etc.)
│       ├── contexts/               # React contexts
│       ├── hooks/                  # Custom React hooks
│       ├── services/               # Frontend service layer
│       ├── types/                  # TypeScript type definitions
│       └── utils/                  # Frontend utilities
├── tests/
│   ├── test_auth.py                # Auth endpoint tests
│   ├── test_itr1_calculator.py     # ITR-1 engine unit tests
│   ├── test_itr4_calculator.py     # ITR-4 engine unit tests
│   ├── test_itr1_schemas.py        # ITR-1 Pydantic schema validation
│   ├── test_itr4_schemas.py        # ITR-4 Pydantic schema validation
│   ├── test_eri_routers.py         # ERI router tests
│   ├── test_eri_envelope.py        # ERI envelope construction tests
│   ├── test_integration_routers.py # Integration router tests
│   ├── test_amt.py                 # AMT computation tests
│   ├── test_bfla.py                # Brought-forward loss tests
│   ├── test_cyla.py                # Current-year loss tests
│   └── __init__.py
├── API_Testing/                    # ERI API testing scripts, DSC signing tools, keystores
├── Docs/
│   └── ec2-proxy-decision.md       # EC2 proxy architecture decision for ITD connectivity
├── .env                            # SECRET_KEY, FRONTEND_URL, ERI_* credentials (not committed)
├── .gitignore
├── requirements.txt
├── NEXT_STEPS.md                   # Phase 4–5 remaining work + frontend integration checklist
├── ARCHITECTURE.md                 # Full architecture reference (1,800+ lines)
├── frontend_integration_audit.md   # Complete field-level pipeline map (1,300+ lines)
├── REMAINING_ITEMS_TO_IMPLEMENT.md # CBDT rule gaps per ITR form
├── itr_schedule_audit.md           # ITR schedule implementation audit
├── CBDT_Implementation_Audit_Report_AY2026-27*.md  # CBDT compliance audit reports
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
# Copy .env values from an existing setup — there is no .env.example template
# Required: SECRET_KEY (any 64-char random string)
# Optional for ERI: ERI_CLIENT_ID, ERI_CLIENT_SECRET, ERI_USER_ID, ERI_PASSWORD, etc.

# 3. Start the API (tables created automatically on first run)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # starts at http://localhost:5173
```

Backend must be running on port 8000. `frontend/` is pre-configured to point to `http://localhost:8000`.

---

## API Reference

All **error** responses share a unified shape regardless of status code:
```json
{ "error": true, "message": "Human readable message", "status_code": 401 }
```

**Interactive docs:** `http://localhost:8000/docs`

### Core Auth & User

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/health` | No | — | `{ status: "ok" }` |
| `POST` | `/auth/signup` | No | `{ email, password }` | `{ access_token, token_type }` |
| `POST` | `/auth/login` | No | `{ email, password }` | `{ access_token, token_type }` |
| `GET` | `/me` | **Bearer** | — | `{ id, email }` |

### ITR Computation & Returns

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `POST` | `/itr1/compute` | **Bearer** | `ITR1Input` | `ITR1ComputeResponse` |
| `POST` | `/itr3/compute` | **Bearer** | `ITR3Input` | `ITR3ComputeResponse` |
| `POST` | `/itr4/compute` | **Bearer** | `ITR4Input` | `ITR4ComputeResponse` |
| `POST` | `/returns/save` | **Bearer** | `{ itr_type, input_data, computed_result }` | `{ id }` |
| `GET` | `/returns` | **Bearer** | — | `[{ id, itr_type, created_at }]` |
| `GET` | `/returns/{id}` | **Bearer** | — | `{ id, itr_type, input_data, computed_result, created_at }` |

> **Note:** ITR-2 schema (`app/schemas/itr2.py`) and calculator (`app/engine/calculators/itr2.py`) exist but no public compute endpoint is wired yet. Only ITR-1, ITR-3, and ITR-4 have `/itrN/compute` endpoints.

### Client Management

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/clients` | **Bearer** | — | `[ClientResponse]` |
| `POST` | `/clients` | **Bearer** | `ClientCreate` | `ClientResponse` |
| `GET` | `/clients/{id}` | **Bearer** | — | `ClientResponse` |
| `PUT` | `/clients/{id}` | **Bearer** | `ClientUpdate` | `ClientResponse` |
| `DELETE` | `/clients/{id}` | **Bearer** | — | `{ message: "Client deleted successfully." }` |
| `GET` | `/clients/{id}/years` | **Bearer** | — | `[str]` (list of assessment years) |
| `GET` | `/clients/{id}/pan-analysis` | **Bearer** | — | PAN entity type + eligibility |
| `POST` | `/clients/{id}/itr-classification` | **Bearer** | `{ hasBusinessIncome, ... }` | `{ recommendedForm, reason }` |

### Client ITR Data

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/clients/{id}/itr/{year}` | **Bearer** | — | Saved ITR form JSON |
| `PUT` | `/clients/{id}/itr/{year}` | **Bearer** | Form data JSON | `{ message, itr_type }` |
| `POST` | `/clients/{id}/itr/{year}/validate` | **Bearer** | Form data JSON | `{ valid, errors, warnings }` |
| `GET` | `/clients/{id}/itr/{year}/download` | **Bearer** | — | File download (CBDT JSON Utility format) |
| `GET` | `/clients/{id}/itr/{year}/download-pdf` | **Bearer** | — | File download (PDF — stub implementation) |

### PAN & Tax Engine

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/pan/{pan}/validate` | No | — | `{ pan, valid, message }` |
| `GET` | `/pan/{pan}/analyze` | No | — | PAN entity type breakdown |
| `POST` | `/tax-summary/compute` | **Bearer** | Form data JSON | Full tax breakdown (salary, deductions, slab tax, cess, etc.) |
| `POST` | `/api/tax/compute` | **Bearer** | Form data JSON | (Alias for `/tax-summary/compute`) |
| `POST` | `/business-income/calculate` | No | `BusinessIncomeRequest` | `BusinessIncomeResponse` |
| `POST` | `/business-income/validate` | No | `BusinessIncomeRequest` | `BusinessValidationResponse` |
| `POST` | `/capital-gains/calculate` | No | `CapitalGainsRequest` | `CapitalGainsResponse` |
| `POST` | `/capital-gains/calculate-batch` | No | `{ transactions: [...] }` | `{ transactions, summary }` |

### Portal Integrations

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `POST` | `/integration/form16/extract` | **Bearer** | multipart `file` | Extracted salary + TDS details |
| `POST` | `/integration/ais-json/import` | **Bearer** | multipart `file` + form params | Parsed AISData |
| `POST` | `/api/v1/imports/ais` | **Bearer** | multipart `file` + form params | (Alias for AIS import) |
| `POST` | `/integration/tis/import` | **Bearer** | multipart `file` | Parsed TISData |
| `POST` | `/integration/26as/import` | **Bearer** | multipart `file` | Parsed Form26ASData (with real parser fallback to mock) |
| `POST` | `/integration/prefill/import` | **Bearer** | multipart `file` | `{ status: "imported" }` |
| `POST` | `/integration/autopopulate/form16` | **Bearer** | `{ form16Data, formData }` | Merged form data |
| `POST` | `/integration/autopopulate/ais` | **Bearer** | `{ aisData, formData }` | Merged form data |
| `POST` | `/prefill/autoPopulateAll` | **Bearer** | `{ aisData, form26ASData, tisData }` | Populated form fields |
| `POST` | `/prefill/autopopulate` | **Bearer** | `{ prefillData, formData }` | Merged form data |
| `POST` | `/integration/reconciliation` | **Bearer** | `{ ... }` | `{ hasDiscrepancies, items }` |

### ERI (e-Return Intermediary) — ITD Portal Integration

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `POST` | `/api/v1/eri/login` | **Bearer** | — | `{ success, authToken, transactionId }` |
| `POST` | `/api/v1/eri/logout` | **Bearer** + `authToken` header | — | `{ success, message }` |
| `POST` | `/api/v1/eri/add-client` | **Bearer** + `authToken` header | `ERIAddClientRequest` | Add-client response |
| `POST` | `/api/v1/eri/validate-client-otp` | **Bearer** + `authToken` header | `ERIValidateClientOtpRequest` | Validation response |
| `POST` | `/api/v1/eri/register-client` | **Bearer** + `authToken` header | `ERIRegisterClientRequest` | Registration response |
| `POST` | `/api/v1/eri/validate-reg-otp` | **Bearer** + `authToken` header | `ERIValidateRegOtpRequest` | Validation response |
| `POST` | `/eri/login` | **Bearer** | `ERILoginRequest` | ERI login (uses `.env` credentials) |
| `POST` | `/eri/logout` | **Bearer** | `ERILogoutRequest` | ERI session logout |
| `POST` | `/eri/client/add` | **Bearer** + token | `ERIAddClientRequest` | Add client |
| `POST` | `/eri/client/validate-otp` | **Bearer** + token | `ERIValidateClientOtpRequest` | Validate client OTP |
| `POST` | `/eri/client/register` | **Bearer** + token | `ERIRegisterClientRequest` | Register taxpayer |
| `POST` | `/eri/client/register/validate-otp` | **Bearer** + token | `ERIValidateRegOtpRequest` | Validate registration |
| `POST` | `/eri/prefill/request-otp` | **Bearer** + token | `ERIPrefillOtpRequest` | Request prefill OTP |
| `POST` | `/eri/prefill/data` | **Bearer** + token | `ERIPrefillDataRequest` | Get prefill data |
| `POST` | `/eri/everify/update-mode` | **Bearer** + token | `ERIUpdateVerModeRequest` | Update verification mode |
| `POST` | `/eri/everify/generate-evc` | **Bearer** + token | `ERIGenerateEvcRequest` | Generate EVC |
| `POST` | `/eri/everify/verify-evc` | **Bearer** + token | `ERIVerifyEvcRequest` | Verify EVC |
| `POST` | `/eri/acknowledgement` | **Bearer** + token | `ERIAcknowledgementRequest` | PDF download |

> **Note:** There are two ERI route sets — `/api/v1/eri/*` (in `integration.py`) and `/eri/*` (in `eri.py`). Both are wired but serve overlapping functionality. This is a known duplication.

### Dashboard

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/dashboard/stats?ay=2025-26` | **Bearer** | — | `{ total, filed, inProgress, docPending, watchList, totalMismatches, totalNotices }` |

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
| ITR-1 | Salary, 1 house property, other sources, basic deductions (80C, 80CCD, 80D, 80E, 80TTA, 80TTB, 80G), LTCG 112A only |
| ITR-2 | All ITR-1 heads + full capital gains, VDA, foreign assets (FA), foreign income (FSI), clubbing (SPI/5A), AMT. Schema + calculator exist; **no public compute endpoint wired** |
| ITR-3 | Full business/profession income (PGBP), balance sheet, P&L, depreciation, GST schedule. Schema + calculator exist; `/itr3/compute` endpoint wired |
| ITR-4 | Presumptive taxation: 44AD (6%/8%), 44ADA (50%), 44AE (per-vehicle rates) + all ITR-1 heads |
| Old Regime slabs | Age-based: below 60 / 60–80 / above 80 |
| New Regime slabs | 4L / 8L / 12L / 16L / 20L / 24L bands (Finance Act 2025) |
| Standard deduction | Old: ₹50,000 · New: ₹75,000 |
| Section 87A rebate | Old: up to ₹12,500 (income ≤ ₹5L) · New: up to ₹60,000 with marginal relief |
| Surcharge | 10% / 15% / 25% / 37% (old) — capped at 25% (new) — with marginal relief |
| Section 80CCE cap | Combined 80C + 80CCC + 80CCD(1) capped at ₹1,50,000 |
| Section 80CCD(1B) | Additional NPS up to ₹50,000 (separate from 80CCE pool) |
| Rounding | `ROUND_HALF_EVEN` per slab; 288A/288B rounding on final figures |
| ITD JSON | All four forms have CBDT-compliant ITD JSON builders in `app/engine/itd/` |

**Three-layer compute pipeline:** Input schemas (Pydantic) → Calculator (dataclass result) → ITD JSON Builder (CBDT-compliant output)

---

## Database Schema

**`user`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | VARCHAR(255) | Unique, indexed |
| hashed_password | VARCHAR(255) | bcrypt hash |
| created_at | DATETIME | Server default (UTC) |

**`client`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | → user.id |
| pan | VARCHAR(10) | Indexed |
| name | VARCHAR(255) | |
| email | VARCHAR(255) | Nullable |
| mobile | VARCHAR(20) | Nullable |
| aadhaar | VARCHAR(20) | Nullable |
| dob | VARCHAR(10) | YYYY-MM-DD, nullable |
| portal_password | TEXT | Encrypted (Fernet), nullable |
| created_at | DATETIME | |
| updated_at | DATETIME | Auto-updated |

**`client_itr`**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| client_id | INTEGER FK | → client.id |
| year | VARCHAR(10) | Assessment Year (e.g. "2025-26") |
| itr_type | VARCHAR(10) | "ITR-1" or "ITR-4" |
| status | VARCHAR(50) | "Not Started", "In Progress", "Filed" |
| form_data | TEXT | JSON string of form values |
| computed_result | TEXT | JSON string of tax computation results |
| created_at | DATETIME | |
| updated_at | DATETIME | Auto-updated |

**`saved_return`** (legacy — used by `/returns/*` endpoints, not client-scoped)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | → user.id |
| itr_type | VARCHAR(10) | "ITR1" or "ITR4" |
| input_data | TEXT | JSON text |
| computed_result | TEXT | JSON text |
| created_at | DATETIME | |

---

## Automation & AIS Pipeline (Standalone Tools)

The `app/automation/` and `ais_extractor/` directories contain standalone tools that are **NOT wired into any FastAPI router**. They are designed to be run manually or via scheduled scripts:

- **`app/automation/`**: Playwright-based browser automation for downloading AIS, TIS, and 26AS PDFs from the income-tax portal, unlocking PDFs, converting them to JSON, and emailing results. Uses the credentials stored in the `client` table (`portal_password` column, encrypted).
- **`ais_extractor/`**: Pure-Python PDF parsing using a state-machine approach to extract structured data from AIS, TIS, and 26AS PDFs. No browser required. Has its own reconciliation logic for cross-checking AIS vs 26AS.

These modules are imported by the integration router's 26AS import endpoint (`/integration/26as/import`) for parsing, but the download-and-extract pipeline is not callable via the API.

---

## Environment Variables

**Backend** (`app/.env` — loaded by `python-dotenv` in `app/main.py`):

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Yes** | Random hex string for JWT signing |
| `FRONTEND_URL` | No | Default `http://localhost:3000` — CORS origin |
| `PORTAL_ENCRYPTION_KEY` | No | Fernet key for encrypting portal passwords in DB |

**ERI Integration** (all optional unless using ERI features):

| Variable | Description |
|---|---|
| `ERI_CLIENT_ID` | ERI client ID from ITD |
| `ERI_CLIENT_SECRET` | ERI client secret |
| `ERI_USER_ID` | ERI user ID |
| `ERI_PASSWORD` | ERI password |
| `ERI_SYMMETRIC_KEY` | Symmetric key for password encryption |
| `ERI_SW_ID` | Software ID |
| `ERI_SECRET_KEY` | Secret key |
| `ERI_ITERATION` | Iteration count |
| `ERI_DSC_SIGNING_MODE` | `token`, `file`, `mock`, or `ngrok` |
| `SIGNER_URL` | DSC signing service URL |
| `ERI_DSC_CERT_SUBJECT` | DSC certificate subject name |
| `ERI_BASE_URL` | ERI API base URL (defaults to UAT endpoint) |

Frontend (`frontend/` uses Vite's `VITE_API_BASE_URL` pointing to `http://localhost:8000`).

---

## Running Tests

```bash
pytest                                           # all tests
pytest tests/test_itr1_calculator.py -v          # specific file
pytest tests/test_itr4_calculator.py -v
pytest tests/test_auth.py -v
pytest tests/test_eri_routers.py -v
```

Test files cover: auth flow, ITR-1/ITR-4 calculator engines, Pydantic schema validation, ERI routers, ERI envelope construction, integration routers, AMT, loss set-off (BFLA/CYLA).

---

## Key Docs

| Doc | Purpose |
|---|---|
| `ARCHITECTURE.md` | Full architecture reference — 1,800+ lines covering every schedule, calculator, and ITD builder |
| `frontend_integration_audit.md` | Complete field-level pipeline map frontend → API → calculator → ITD JSON |
| `NEXT_STEPS.md` | Phase 4 (frontend) and Phase 5 (tests, production hardening) remaining work |
| `REMAINING_ITEMS_TO_IMPLEMENT.md` | CBDT rule gaps per ITR form (validation rules, schedules, field-level gaps) |
| `itr_schedule_audit.md` | ITR schedule implementation audit |
| `CBDT_Implementation_Audit_Report_AY2026-27*.md` | CBDT compliance audit reports |
| `Docs/ec2-proxy-decision.md` | EC2 proxy architecture for ITD connectivity |
