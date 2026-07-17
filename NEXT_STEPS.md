# Next Steps — Backend & Frontend Integration

## Status: Backend Complete ✅

All backend phases are done. This document tracks what the frontend developer needs to implement and what remains on the backend side.

---

## Phase 4 — Frontend Integration (In Progress)

### What the frontend needs to implement

#### 4.1 API Client (`src/api/client.ts`)
- Base URL from `REACT_APP_API_URL` env variable (default `http://localhost:8000`)
- Axios (or fetch) wrapper that:
  - Attaches `Authorization: Bearer <token>` header automatically from localStorage
  - On 401 response → clears token and redirects to `/login`
  - Converts all error responses (`{ error, message, status_code }`) into user-visible toasts/alerts

#### 4.2 Auth Flow
- **Signup page** (`/signup`) → calls `POST /auth/signup` → stores token in localStorage → redirect to dashboard
- **Login page** (`/login`) → calls `POST /auth/login` → stores token → redirect to dashboard
- **App load check** → calls `GET /me` on startup:
  - If 200 → user is logged in, show dashboard
  - If 401 → clear stored token, redirect to `/login`
- **Logout** → clear localStorage token → redirect to `/login` (no backend call needed)

#### 4.3 ITR-1 Compute Form (`/itr1`)
- Multi-step form capturing all `ITR1Input` fields (salary, house property, other sources, deductions)
- On submit → `POST /itr1/compute` → display breakdown (taxable income, slab tax, rebate, cess, total)
- "Save this return" button → `POST /returns/save` with `itr_type: "ITR1"`, raw input, and result

**Required ITR1Input enum values:**
| Field | Valid values |
|---|---|
| `age_bracket` | `"below_60"` / `"60_to_80"` / `"above_80"` |
| `tax_regime` | `"old"` / `"new"` |
| `property_type` | `"S"` (self-occupied) / `"L"` (let-out) / `"D"` (deemed let-out) |

#### 4.4 ITR-4 Compute Form (`/itr4`)
- Same pattern as ITR-1 plus presumptive income section
- `presumptive_scheme`: `"none"` / `"44AD"` / `"44ADA"` / `"44AE"`
- Show/hide sub-form based on selected scheme

#### 4.5 Returns History (`/returns`)
- `GET /returns` → display list (itr_type, created_at)
- Click on a row → `GET /returns/{id}` → show full breakdown

---

## Phase 5 — Remaining Backend Work

### 5.1 pytest suite (priority: high)
Create `tests/test_api.py` using FastAPI `TestClient` with an in-memory SQLite database.

Tests to cover:
- `POST /auth/signup` — success (201), duplicate email (400)
- `POST /auth/login` — success (200), wrong password (401), unknown email (401)
- `GET /me` — valid token (200), no token (403), bad token (401)
- `POST /itr1/compute` — valid payload (200), invalid enum (422), unauthenticated (403)
- `POST /itr4/compute` — 44AD scheme (200), 44ADA scheme (200)
- `POST /returns/save` — success (201), bad itr_type (400)
- `GET /returns` — empty list (200), populated list (200), isolation between users
- `GET /returns/{id}` — own record (200), other user's record (403), missing id (404)

### 5.2 Error handler coverage (nice to have)
- Verify 422 unified shape via test
- Verify 500 unified shape via test

### 5.3 Production hardening (before deploy)
- [ ] Replace SQLite with PostgreSQL (change `DATABASE_URL` only — SQLAlchemy is DB-agnostic)
- [ ] Add `SECRET_KEY` rotation strategy
- [ ] Pin `requirements.txt` to exact versions (`pip freeze > requirements.txt`)
- [ ] Run behind a reverse proxy (nginx) with HTTPS
- [ ] Set `FRONTEND_URL` to the production domain in the server's env

---

## Endpoint Quick Reference (hand to frontend developer)

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/health` | No | — | `{ status }` |
| POST | `/auth/signup` | No | `{ email, password }` | `{ access_token, token_type }` |
| POST | `/auth/login` | No | `{ email, password }` | `{ access_token, token_type }` |
| GET | `/me` | Bearer | — | `{ id, email }` |
| POST | `/itr1/compute` | Bearer | ITR1Input JSON | Tax breakdown (13 fields) |
| POST | `/itr4/compute` | Bearer | ITR4Input JSON | Tax breakdown (14 fields) |
| POST | `/returns/save` | Bearer | `{ itr_type, input_data, computed_result }` | `{ id }` |
| GET | `/returns` | Bearer | — | `[{ id, itr_type, created_at }]` |
| GET | `/returns/{id}` | Bearer | — | `{ id, itr_type, input_data, computed_result, created_at }` |

**All errors:** `{ "error": true, "message": "...", "status_code": N }`

**Docs UI:** `http://localhost:8000/docs`

---

## Git Branch Strategy

```
main          ← production-ready code only
dev           ← integration branch
phase-3-api   ← merged ✅ (DB + Auth + Endpoints)
phase-4-fe    ← frontend integration (current)
phase-5-tests ← pytest API suite
```
