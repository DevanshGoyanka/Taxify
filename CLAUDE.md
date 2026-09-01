# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Taxify — an Indian Income Tax Return (ITR) filing platform. FastAPI backend (Python) +
React/TypeScript frontend (Vite). Computes ITR-1 through ITR-4 for AY 2026-27, generates
CBDT-compliant ITD JSON, drives Playwright-based ITD portal automation, and integrates with
the ITD e-Return Intermediary (ERI) API (Type-2 and Type-3 modes). Handles real taxpayer PII
and live ERI credentials — see `SECURITY.md` before touching auth, credentials, or the digest
computation.

`master` on GitHub is a stale default branch — all work happens on `main`
(`git clone -b main ...`).

## Commands

Backend setup (Python 3.10, Windows and Linux both supported):
```bash
python3.10 -m venv .venv
./.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
```

Run the backend — **use `run.py`, not `uvicorn app.main:app` directly**:
```bash
python run.py                    # :8000
```
On Windows, plain `uvicorn` (or `--reload`) forces `WindowsSelectorEventLoopPolicy`, which
cannot spawn subprocesses — Playwright then fails with `NotImplementedError` the moment any
portal automation runs. `run.py` sets `WindowsProactorEventLoopPolicy` before importing uvicorn
and passes `loop="none"` so uvicorn can't override it; `app/main.py` sets the same policy at
module scope as a second line of defense for callers that bypass `run.py`. On Linux the default
loop already supports subprocesses, so the deployed systemd unit calls uvicorn directly.
`app/automation/browser.py`'s `BrowserManager` additionally runs Playwright on its own
dedicated Proactor-loop thread (`dispatch()`), independent of whatever loop the calling
request handler is on.

Frontend:
```bash
cd frontend && npm ci
npm run dev             # :3000
npm run build            # tsc -b && vite build — must pass before any PR
npm run lint
npm test                 # vitest run
```

Tests:
```bash
pytest                                   # full suite
pytest tests/test_itr1_calculator.py -v  # one file
```
`conftest.py` at the repo root loads `.env` before any test imports app code — ERI credential
resolution fails without it. **The suite is not green**: baseline is ~177 failures / 13
collection errors predating current work. Treat a red run as the known state, not something
your change caused, but confirm your own area isn't newly broken.

Before pushing, check for undeclared imports (most Python imports here are lazy/inside
functions, so a missing package fails in production, not at startup):
```bash
./.venv/bin/python - <<'PY'
import ast, pathlib, sys
mods = set()
for root in (pathlib.Path("app"), pathlib.Path("ais_extractor")):
    for f in root.rglob("*.py"):
        try: tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError: continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names: mods.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods.add(n.module.split(".")[0])
for m in sorted(mods - set(sys.stdlib_module_names) - {"app","ais_extractor","tests","scripts"}):
    try: __import__(m)
    except Exception: print("MISSING:", m)
PY
```

## Architecture

### Three-layer compute pipeline (per ITR form)

Every ITR form (1/2/3/4) follows the same pattern:

```
Input (Pydantic)         Calculator (dataclass)         ITD Builder (CBDT JSON)
app/schemas/itr*.py  →   app/engine/calculators/itr*.py  →  app/engine/itd/itr*.py
```

1. **Schema** (`app/schemas/`): Pydantic v2 models. All monetary fields are `Decimal` — never
   float. ITR-2's schema is the shared type library; ITR-3 imports capital-gains/loss/foreign
   types from it.
2. **Calculator** (`app/engine/calculators/`): pure functions — heads of income → CYLA/BFLA
   loss set-off → Chapter VI-A deductions → taxable income (rounded to nearest ₹10) → slab tax
   → special-rate tax (112A/111A/VDA/lottery) → rebate 87A → surcharge (with marginal relief)
   → cess → 234A/B/C interest + 234F late fee → credits → payable/refund. Shared arithmetic
   (slabs, rebate, surcharge, cess, interest, rounding) lives in `app/engine/common/`; shared
   constants (slabs, deduction caps, CII table) in `app/engine/constants.py`.
3. **ITD Builder** (`app/engine/itd/`): assembles the calculator result into the exact nested
   CBDT JSON schema (`additionalProperties: false`), including the `CreationInfo.Digest` —
   SHA-256 over the sorted JSON, computed after all schedules are built.

Full field-by-field reference for all four forms: `Docs/ARCHITECTURE.md` (1800+ lines).
Frontend-to-ITD field mapping: `Docs/frontend_integration_audit.md`.

### Routers → engine wiring

`app/main.py` mounts: `auth`, `itr` (`/itr{1,3}/compute`, `/returns/*`), `clients`,
`client_itr` + `client_itr_v2`, `integration` (Form16/AIS/TIS/26AS import, prefill, legacy
`/api/v1/eri/*`), `pan`, `tax` + `tax_v2`, `dashboard`, `automation` (portal-download jobs),
`filing` (submission pipeline). ITR-4 compute and the newer `/eri/*` route set live elsewhere
per `README.md`'s API reference table — check there for the full endpoint list before assuming
a route doesn't exist. There are two overlapping ERI route sets (`/api/v1/eri/*` in
`integration.py`, `/eri/*` in `eri.py`) — known duplication, not a bug to "fix" incidentally.

Two background workers start in `app/main.py`'s lifespan and stop on shutdown:
`app/automation/job_worker.py` (portal-download jobs enqueued via `POST
/clients/{id}/automation/import`) and `app/filing_automation/worker.py` (submission pipeline).
Note: `README.md`'s claim that `app/automation/` is "NOT wired to any FastAPI router" is
stale — `app/routers/automation.py` and the job worker wire it in.

### Browser automation

`app/automation/browser.py`'s `BrowserManager` is a singleton owning one Playwright browser
instance, run on its own dedicated event-loop thread (see the Windows event-loop note above).
`--workers 1` is mandatory in deployment for this reason (`SECURITY.md`). Downloaders
(`downloader*.py`) pull AIS/TIS/26AS PDFs from the ITD portal; `pdf_unlocker.py`,
`ais_converter.py`, `as26_converter.py` turn them into structured data. `ais_extractor/` is a
separate, browser-free PDF-parsing tool (state-machine parser) used by the 26AS import
endpoint's parsing step.

### ERI integration

`app/eri/` is the low-level ITD e-Return Intermediary API client: `envelope.py` (XML envelope
+ password encryption), `digest.py`, `config.py` (credential/mode resolution — Type-2 API
gateway vs Type-3 offline utility, switched by env var, validated at startup via
`assert_credentials_at_startup()`). DSC signing is Windows-only (`win32crypt`); the Linux
deployment runs Type-3, which needs no DSC.

### Database

SQLite via SQLAlchemy (`app/db/`). Core tables: `user`, `client` (PAN, encrypted
`portal_password`), `client_itr` (per-client-per-year form data + computed result),
`saved_return` (legacy, non-client-scoped). Full column reference in `README.md`.

### Frontend

`frontend/src/`: `api/` (Axios clients), `pages/` (route-level components, e.g.
`ITRComputationPage.tsx`), `components/`, `contexts/`, `hooks/`, `services/`, `types/`,
`utils/`. React 19 + TypeScript + Vite, React Router.

## Conventions

- All monetary values are `decimal.Decimal` end-to-end — never float.
- `.editorconfig` is authoritative: 4 spaces (Python), 2 spaces (TS/JS/JSON/CSS), LF endings.
- Comments here explain *why*, especially CBDT/ITD rule citations — match that style, cite the
  section when a rule comes from a CBDT/ITD document.
- Never commit `.env`, `app.db`, DSC certs/keystores (`*.pfx`/`*.p12`/`*.jks`/`*.pem`). If one
  lands in git history, rotation is mandatory (`scripts/regen_portal_key.py` for
  `PORTAL_ENCRYPTION_KEY`, `scripts/clear_broken_portal_passwords.py` to follow up) — deleting
  the file doesn't remove it from history.
