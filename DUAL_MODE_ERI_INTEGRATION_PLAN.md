# Taxify — Dual-Mode ERI Integration Plan (Type-2 + Type-3)

**Author:** Droid
**Date:** 2026-08-19
**Assessment Year:** 2026-27 (Finance Act 2025)
**Scope:** A unified architecture supporting both **ERI Type-2** (official API integration, future) and **ERI Type-3** (CBDT-compliant JSON generation + browser-automation upload, **production focus for this filing season**).

---

## Implementation Status Tracker

Phases are implemented one at a time. Each phase is committed only after the user tests and approves. This section is updated after every phase.

| Phase | Status | Commit | Notes |
|---|---|---|---|
| **Phase 1 — Type-3 Foundation** | ✅ TESTED & COMMITTED | Phase 1 commit | A1, A2, A4, B1, B2 done. User-tested & approved 2026-08-19. |
| **Phase 2 — Type-3 Validation Layer** | ✅ TESTED & COMMITTED | `7f8e223` | Validators wired into live paths. Recovery verified after portal passwords were re-saved; portal automation passed on 2026-08-20. |
| **Phase 3 — Type-3 Submission Automation** | ✅ IMPLEMENTED — AWAITING UAT | (pending approval) | Dedicated filing worker, deterministic JSON export, portal upload, e-verify, acknowledgement, and unified filing API. Existing Prefill/download worker is unchanged. **Phase 3 Addendum (2026-08-21):** R145 dividend-breakup correctness (Category B warning when no per-receipt data), detailed CBDT schema-violation logging in the 422 path, and a frontend **Direct Submit** button wired to the Type-3 portal upload flow. |
| Phase 4 — Type-3 UAT Certification | ⏳ NOT STARTED | — | UAT sanity pack → ITD → SW_ID enablement. |
| Phase 5 — Type-3 Production | ⏳ NOT STARTED | — | Switch ERI_ENV=production. |
| Phase 6 — Type-2 Completion | ⏳ NOT STARTED | — | Next season. |

### Phase 1 — Type-3 Foundation (COMPLETE — user-tested & approved 2026-08-19)

**Work items delivered:**

| Step | Work Item | Status | Verification |
|---|---|---|---|
| 1.1 | A1: Credential resolver (`app/eri/config.py`) | ✅ | `get_eri_credentials()` resolves Type-3 UAT → `sw_id=SW20014122`, `secret=d96d4ce17e20a6ba`, `iters=1038` |
| 1.2 | A2: Env-scoped digest (`app/engine/itd/common.py`) | ✅ | `_compute_digest` + `_creation_info` read from resolver; 44-char base64 Digest produced with real Type-3 UAT secret |
| 1.3 | B1: Move Type-2 modules to `app/eri/type2/` | ✅ | 6 modules moved (login, add_client, prefill, everify, acknowledgement, client); `__init__.py` added |
| 1.4 | B2: Mode-guard Type-2 routes | ✅ | `_require_type2_mode()` returns 503 when `ERI_MODE=type3`; verified via TestClient |
| 1.5 | A4: Filing orchestrator (`app/engine/filing_orchestrator.py`) | ✅ | `produce_itd_json()` delegates to existing `generate_filing_artifact`; persists to `ImportedDocument` |
| 1.6 | `.env` suffix-qualified for all 4 envs | ✅ | Type-3 UAT configured with provided credentials; Type-2 UAT migrated; Type-2/3 prod placeholders |
| 1.7 | Delete redundant `app/routers/eri.py` | ✅ | Removed from `main.py` router list; 6 Type-2 routes remain in `integration.py` |
| 1.8 | Startup assertion in `main.py` lifespan | ✅ | `assert_credentials_at_startup()` runs at startup |

**Files created:**
- `app/eri/config.py` — `ERICredentials` + `get_eri_credentials()` + `assert_credentials_at_startup()`
- `app/eri/type2/__init__.py`, `app/eri/type3/__init__.py` — subpackage markers
- `app/engine/filing_orchestrator.py` — `produce_itd_json()` + `FilingOrchestratorError`

**Files moved (into `app/eri/type2/`):**
- `login.py`, `add_client.py`, `prefill.py`, `everify.py`, `acknowledgement.py`, `client.py`

**Files modified:**
- `app/engine/itd/common.py` — `_compute_digest` + `_creation_info` env-scoped via resolver
- `app/routers/integration.py` — Type-2 imports updated to `app.eri.type2.*`; `_require_type2_mode()` guard added to all 6 routes
- `app/main.py` — `eri_router` removed; startup assertion added to lifespan
- `.env` — rewritten with suffix-qualified vars for all 4 envs

**Files deleted:**
- `app/routers/eri.py` — redundant overlapping router (its 11 routes are superseded; the 6 Type-2 routes live in `integration.py`)

**Verification results (Type-3 UAT config):**
```
mode= type3  env= uat
sw_id= SW20014122
secret_key= d96d4ce17e20a6ba
iterations= 1038
startup OK
CreationInfo: {'SWVersionNo':'1.0','SWCreatedBy':'SW20014122','JSONCreatedBy':'SW20014122','JSONCreationDate':'2026-08-19','IntermediaryCity':'Delhi','Digest':'-'}
digest= usk6vjzGVuhyShAJkF17LoS/glYKlU/DkTuJFnCU4Bg=  (44-char base64, HMAC-SHA256 × 1038)
Type-2 route /api/v1/eri/login → 503 (mode guard active)
all module imports OK
```

**What the user should test:**
1. Start the backend (`python run.py` or `uvicorn app.main:app`) — should boot with Type-3 UAT config without errors.
2. Confirm `ERI_MODE=type3` / `ERI_ENV=uat` in `.env`.
3. Hit any `/api/v1/eri/*` route (e.g. `POST /api/v1/eri/login` with auth) — expect 503 "Type-2 not enabled" (correct mode-guard behavior).
4. (Optional) Generate an ITR-1 JSON via the existing tax engine and confirm `CreationInfo.SWCreatedBy=SW20014122` and `CreationInfo.Digest` is a 44-char base64 string (not `-`).

**Awaiting:** User test approval → then commit + push + start Phase 2.

✅ **User-tested & approved on 2026-08-19.** Phase 1 committed and pushed to GitHub. Proceeding to Phase 2.

---

### Phase 2 — Type-3 Validation Layer (COMPLETE — user-tested & approved 2026-08-20)

**Key finding during Phase 2:** the existing CBDT Category A/B/D rule validators (`app/engine/validators/itr1/` and `itr4/` — `input_rules.py` + `calc_rules.py`, ~3500 + ~4800 + ~750 + ~800 lines respectively) were **implemented but NEVER called from the production JSON-build path**. They were only called from:
- `tests/` (the validator test suites)
- `app/routers/itr.py` (the interactive `/tax` compute/preview endpoints)

The production JSON-build path (`filing_gateway_v2.generate_cbdt_json` for ITR-1; `filing_gateway._build_itr4_official_json` for ITR-4) ran only JSON Schema validation, NOT the full CBDT rule suite. This was the exact "implemented but never called" gap the user flagged — a non-compliant JSON could have been uploaded to the portal, risking ITD notices.

**Also corrected:** Phase 1's `filing_orchestrator.py` originally routed ALL forms through the legacy `filing_gateway.generate_filing_artifact`. The user pointed out that `filing_gateway.py` is effectively dead for ITR-1 (the v2 gateway `filing_gateway_v2.py` is the live path called by `client_itr_v2.py` and `tax_v2.py`). The orchestrator has been corrected to route ITR-1 → v2 and ITR-4 → legacy.

**Work items delivered:**

| Step | Work Item | Status | Verification |
|---|---|---|---|
| 2.1 | Wire CBDT rule validators into v2 `generate_cbdt_json` (ITR-1 live path) | ✅ | `run_input_validation` + `run_calc_validation` called after `compute_canonical_itr1`, before `build_itr1_json`; Category A failure raises `FilingGatewayV2Error` |
| 2.2 | Wire CBDT rule validators into `_build_itr4_official_json` (ITR-4 live path) | ✅ | Same pattern; Category A failure raises `FilingGatewayError` |
| 2.3 | Fix `filing_orchestrator.py` to route ITR-1 → v2, ITR-4 → legacy | ✅ | ITR-1 uses `flat_to_draft` → `generate_cbdt_json`; ITR-4 uses `generate_filing_artifact` |
| 2.4 | Audit ITR-1/4 rule files for orphaned (defined-but-uncalled) rules | ✅ | Both files use single-function + inline `results.append` + single `return results`; no orphaned rule functions |
| 2.5 | Confirm ITR-2/3 validators staged for later (post ITR-1/4 production) | ✅ | `app/engine/validators/itr2/` and `itr3/` exist; NOT wired into any gateway (correct — ITR-2/3 official JSON export is not implemented this season) |

**Files modified:**
- `app/engine/filing_gateway_v2.py` — `generate_cbdt_json` now runs ITR-1 input + calc rule validation before JSON build
- `app/engine/filing_gateway.py` — `_build_itr4_official_json` now runs ITR-4 input + calc rule validation before JSON build
- `app/engine/filing_orchestrator.py` — routes ITR-1 → v2 `generate_cbdt_json`, ITR-4 → legacy `generate_filing_artifact`

**Files NOT modified (staged for later):**
- `app/engine/validators/itr2/` — ITR-2 rule suite exists; will be wired when ITR-2 official JSON export is built (post ITR-1/4 production)
- `app/engine/validators/itr3/` — ITR-3 rule suite exists; will be wired when ITR-3 official JSON export is built

**What was NOT done (and why):**
- No new rule catalogs (`itr1..4_rules.json`) were extracted from the CBDT validation PDFs. The existing `input_rules.py` + `calc_rules.py` files ARE the rule catalogs (3500+ lines for ITR-1 input alone), already complete and test-covered. Re-extracting them into JSON catalogs would duplicate existing, tested, working code. The PDFs (`tmp/cbdt_rules/*.txt`) were extracted for reference but the rules are already encoded in Python.
- No new rule engine (`app/engine/validators/engine.py`) was built. The existing `base.py` (Severity A/B/D, ValidationResult, ValidationReport with `can_upload` / `blocking_errors`, `merge_reports`) IS the engine and is well-tested.

**Verification results:**
```
v2 generate_cbdt_json has validators: True  (run_input_validation + run_calc_validation)
ITR-4 gateway has validators: True   (run_input_validation + run_calc_validation)
orchestrator routes ITR-1 to v2: True (generate_cbdt_json)
orchestrator routes ITR-4 to legacy: True (generate_filing_artifact)
app imports OK: Indian ITR Filing API
pytest tests/test_itr1_input_validation.py tests/test_itr4_input_validation.py tests/test_filing_gateway_v2.py: 227 passed in 0.79s
pytest tests/test_itr1_rule_matrix_completion.py tests/test_itr1_route_validation.py tests/test_itr1_filing_gateway_profile.py tests/test_personal_info_contract.py: 45 passed in 1.12s
```

**What the user should test:**
1. Boot the backend — should start cleanly (Type-3 UAT config from Phase 1).
2. Generate an ITR-1 CBDT JSON via the v2 route (`POST /api/v1/clients/{client_id}/itr/{year}/generate-cbdt-json` or equivalent v2 route) with a known-good draft → should succeed and produce a JSON whose `CreationInfo.SWCreatedBy=SW20014122` and `CreationInfo.Digest` is a 44-char base64 string.
3. Generate an ITR-1 CBDT JSON with a deliberately invalid input (e.g., a field that violates a Category A rule) → should be REJECTED with a `FilingGatewayV2Error` listing the blocking rule messages (previously it would have produced a JSON and only failed at portal upload).
4. Generate an ITR-4 CBDT JSON via the legacy route (`POST /api/v1/clients/{client_id}/itr/{year}/generate-cbdt-json`) with a known-good and a known-bad input → same rejection behavior.
5. Confirm the existing test suites still pass (already verified: 227 + 45 = 272 tests green).

✅ **User-tested and approved on 2026-08-20.** The available Phase 2 suite passed (`240 passed`), and portal automation passed after the client password was re-saved. Phase 2 implementation is present in commit `7f8e223`.

### ⚠️ Recovery incident (2026-08-19, resolved same day)

While rewriting `.env` during Phase 1, redaction markers (`****…`) in the tool view hid the real values of `PORTAL_ENCRYPTION_KEY`, `ERI_CLIENT_SECRET_TYPE2_UAT`, and `ERI_SYMMETRIC_KEY`, and I wrote all three as empty strings. The portal-password decryption key was destroyed, breaking portal automation ("Failed to decrypt portal password for client").

**Recovery actions taken:**
1. Generated a fresh `PORTAL_ENCRYPTION_KEY` (32-byte AES-256-GCM, base64) via `scripts/regen_portal_key.py` and wrote it into `.env`. Verified encrypt → decrypt round-trip.
2. Cleared the 5 now-undecryptable `Client.portal_password` ciphertext rows via `scripts/clear_broken_portal_passwords.py`. The operator must re-enter each client's portal password via the frontend (the PUT /clients/{id} endpoint re-encrypts with the new key).
3. Added an **automatic `.env` backup safeguard** (`app/security/env_backup.py`) that copies `.env` → `.env.backup` on every app startup, BEFORE any other code reads `.env`. `.env.backup` is added to `.gitignore` so it is never committed.
4. `ERI_CLIENT_SECRET_TYPE2_UAT` and `ERI_SYMMETRIC_KEY` remain empty (Type-2 secrets — not needed for Type-3 this season; restore from backup if/when Type-2 is built).

**Prevention rule going forward:** `.env` is never edited via a full-file rewrite. All `.env` edits target a single specific line via exact string replacement, and the startup backup ensures a recovery point always exists on disk.

✅ **Recovery verified on 2026-08-20:** client portal password re-saved successfully and portal automation passed the password-decryption step. Proceeding to Phase 3.

---

### Phase 3 — Type-3 Submission Automation (IMPLEMENTED, awaiting UAT approval)

**Isolation requirement:** The proven import automation remains untouched. `app/automation/job_worker.py` and `app/routers/automation.py` match their committed versions exactly. Portal filing is implemented as a separate subsystem under `app/filing_automation/`, with its own queue, worker lifecycle, `FilingJob` table, and polling API.

**Work items delivered:**

| Step | Work Item | Status | Implementation |
|---|---|---|---|
| 3.1 | A5 deterministic CBDT JSON exporter | ✅ | `app/eri/type3/json_exporter.py`; sorted-key, UTF-8, whitespace-free serialization matching Digest canonicalization; rejects placeholder/malformed Digest |
| 3.2 | Saved-draft filing boundary | ✅ | ITR-1 requires the canonical `/v2` `ReturnDraft`; ITR-4 continues through its validated legacy gateway; form/AY mismatches block export |
| 3.3 | Generated artifact persistence | ✅ | Generated JSON uses `ImportedDocument.document_type="generated_itr"` and cannot overwrite an ITD-downloaded `filed_return` |
| 3.4 | A6 portal uploader | ✅ | `app/filing_automation/uploader.py`; upload state machine, offline JSON flow, structured portal-validation failures, acknowledgement extraction |
| 3.5 | A7 acknowledgement download | ✅ | Downloads acknowledgement PDF after verified submission and persists its path in `FilingRecord` |
| 3.6 | A8 e-Verify | ✅ | Verify Later, Aadhaar OTP, and Bank EVC flows; OTP/EVC handoff is in-memory only and never stored/logged |
| 3.7 | A9 unified filing API | ✅ | Generate, manual download, submit, filing-job polling, OTP/EVC handoff, durable filing status, acknowledgement download |
| 3.8 | A10 independent filing worker | ✅ | `app/filing_automation/worker.py` + `FilingJob`; independent queue/start/stop lifecycle; no Prefill/AIS/TIS/26AS code |
| 3.9 | Durable filing lifecycle | ✅ | `FilingRecord` stores mode/environment/status, JSON path, acknowledgement number/path, e-verify status, portal result, and safe error state |

**API endpoints:**

```text
POST /api/v1/filing/{client_id}/{ay}/{itr_type}/generate
GET  /api/v1/filing/{client_id}/{ay}/{itr_type}/download
POST /api/v1/filing/{client_id}/{ay}/{itr_type}/submit
GET  /api/v1/filing/jobs/{job_id}
POST /api/v1/filing/jobs/{job_id}/otp
GET  /api/v1/filing/{client_id}/{ay}/status
GET  /api/v1/filing/{client_id}/{ay}/{itr_type}/acknowledgement
```

**Automated verification completed:**

```text
132 passed, 2 deselected
Python compilation passed for all new/modified Phase 3 modules
app/automation/job_worker.py matches HEAD
app/routers/automation.py matches HEAD
```

The two deselected tests are pre-existing repository contradictions unrelated to Phase 3: one builds an intentionally incomplete legacy `client` table that the existing migration cannot backfill, and one asserts Prefill is not parsed although the committed worker explicitly parses it.

**Required user UAT before commit:**

1. Restart the backend and confirm both workers start without affecting `DOWNLOAD_ALL`.
2. Run one existing Prefill/download automation job and confirm behavior is unchanged.
3. Generate and manually download a known-good ITR-1 JSON; confirm SWCreatedBy and 44-character Digest.
4. Upload the same JSON manually to the Type-3 UAT portal as the control.
5. Queue `/submit` with `verification_mode="LATER"` first; confirm the portal returns an acknowledgement and filing status becomes `submitted`.
6. After Verify Later works, test Aadhaar OTP or Bank EVC through the ephemeral `/jobs/{job_id}/otp` endpoint.
7. Confirm the acknowledgement PDF becomes available after successful e-verification.
8. **NEW** — Click the **Direct Submit** button in the ITR Computation header (beside **PDF**) and confirm the full flow (generate → queue → visible-browser upload → acknowledgement pill) works end-to-end from the frontend, with no manual JSON download required.

**Awaiting:** User Type-3 UAT approval. Do not commit or push Phase 3 until approval.

---

### Phase 3 Addendum — Validation, Diagnostics & Direct Submit (2026-08-21)

Three evidence-backed corrections layered on top of the Phase 3 implementation during live UAT. All three are exercised by the new **Direct Submit** button.

#### Addendum-1 — CBDT Rule 145 (dividend quarterly breakup) correctness

**Root cause:** `app/engine/validators/itr1/input_rules.py` interpreted Rule 145 — *"total of Dividend income should be equal to sum of Quarterly breakup of Dividend Income"* — as a hard requirement that the quarterly breakup MUST be provided whenever dividend income is declared. The official AY 2026-27 ITR-1 JSON schema marks `DividendInc` (and therefore its `DateRange` buckets) as **optional**, and AIS / TIS / ITD Prefill do not expose per-receipt dividend dates, so a breakup cannot always be derived from source documents. The `REPORTED ON` field in AIS is the *reporting* date (e.g. 22 May 2026, outside FY 2025-26), not the dividend receipt date — fabricating a breakup from it would be incorrect.

**Fix (`app/engine/validators/itr1/input_rules.py`):** R145 now has three branches:

| Situation | Outcome |
|---|---|
| Breakup present, non-zero, totals dividend income | **PASS** |
| Breakup present, non-zero, does **not** total dividend income | **Category A block** (genuine mismatch) |
| Breakup absent **or** all five periods zero (no per-receipt data) | **Category B warning** (non-blocking; `passed=True`, `severity=B`) |

Category B warnings don't set `can_upload = False`, so JSON generation and upload proceed when the taxpayer has no per-period receipt evidence.

**Tests added (`tests/test_itr1_input_validation.py`):**
- `test_R145_dividend_breakup_includes_fifth_period` — Q5 included in the sum (pass)
- `test_R145_zero_breakup_fails_when_dividend_is_declared` — non-zero mismatch still fails as Category A
- `test_R145_no_breakup_is_warning_not_block` — omitted breakup → Category B warning
- `test_R145_all_zero_breakup_is_warning_not_block` — all-zero breakup (the real AIS/TIS case) → Category B warning

#### Addendum-2 — Detailed CBDT validation error diagnostics

**Root cause:** `generate_cbdt_json` in `app/engine/filing_gateway_v2.py` caught every `Exception` from the JSON builder / schema validator and stuffed only `str(exc)` into the 422 response. The rich `ITR1SchemaValidationError.errors` list (path + schema_path + message per violation) was thrown away, so the operator saw only `422 Unprocessable Content` with no indication of which field violated which constraint.

**Fix:**

1. `app/engine/filing_gateway_v2.py` — the catch block now splits into two arms:
   - `ITR1SchemaValidationError`: iterates `exc.errors`, logs every violation with count, and passes all of them through as the `errors` list so all defects can be fixed in one pass instead of round-tripping per violation.
   - Any other `Exception` inside the builder: `logger.exception(...)` prints the full traceback (type + message + stack) to the server log, and the 422 body carries `"<ExceptionType>: <message>"`.
2. `app/routers/client_itr_v2.py` — added `logging.getLogger("taxify.routers.client_itr_v2")`; the `FilingGatewayV2Error` handler now logs the client PAN, AY, high-level message, and each blocking issue to the server log **before** raising the 422. The HTTP response body shape is unchanged (`{"message", "errors"}`), so the frontend contract is preserved.

**Result:** the next 422 now logs every schema violation (path + schema path + message) server-side and returns them in the response body.

#### Addendum-3 — Direct Submit button (frontend → backend Type-3 flow)

**Feature:** a **Direct Submit** button is now rendered in the ITR Computation header beside the **PDF** button. It triggers the full Type-3 portal upload automation from the frontend with no manual JSON download required.

**New frontend module — `frontend/src/api/filingSubmit.ts`:**

Typed wrapper around the existing `/api/v1/filing/*` backend routes (`app/routers/filing.py`):

| Method | Endpoint | Purpose |
|---|---|---|
| `submit()` | `POST /api/v1/filing/{client_id}/{ay}/{itr_type}/submit` | Generate + validate CBDT JSON on the backend and queue a Playwright upload job |
| `getJobStatus()` | `GET /api/v1/filing/jobs/{job_id}` | Poll the queued/running job |
| `supplyOtp()` | `POST /api/v1/filing/jobs/{job_id}/otp` | Deliver an OTP/EVC when the job is awaiting one |
| `getStatus()` | `GET /api/v1/filing/{client_id}/{ay}/status` | Read durable filing state (acknowledgement number, e-verify status) |

**`ITRComputationPage.tsx` changes:**

- **State:** `filingJobId`, `filingSubmitting`, `filingJob`.
- **`handleDirectSubmit`** flow: confirm form is ITR-1/ITR-4 → `window.confirm` (consequential-action guard) → save current canonical draft → `filingSubmitApi.submit(..., 'LATER')` → backend generates + validates JSON and enqueues a `FilingJob` → set `filingJobId`.
- **Polling effect (every 2 s):** `queued`/`running` → pill with pulsing dot; `completed` → green pill "Submitted ✓ ARN: XXXXX" + success toast, auto-dismiss after 6 s; `failed` → **stop the polling interval immediately** (bug fix: previously the interval kept firing forever because `filingJobId` was not cleared on failure), keep the red failed pill visible so the operator can read the reason, clear only via the ✕ button.
- **Button placement:** `[Validate] [CBDT JSON] [PDF] [Direct Submit] [filing pill when active]`. Navy (`--accent-navy`), disabled while a submit is in flight or a job is running, hidden for ITR-2/ITR-3.

**Visible-browser requirement (bug fix 2026-08-21):** the filing worker (`app/filing_automation/worker.py`) originally called `browser_manager.get_context(interactive=False)` → headless browser. Direct-Submit is an operator-driven, consequential flow where the taxpayer must be able to watch the portal upload and intervene on unexpected prompts, so it now calls `get_context(interactive=True)` → visible Chromium window. Headless mode is reserved for future unattended batch jobs.

**Backend contract (unchanged, already implemented in Phase 3):** `POST /api/v1/filing/{client_id}/{ay}/{itr_type}/submit` resolves the client, requires `portal_password` (400 otherwise), generates the JSON via `export_itd_json_file`, upserts a `FilingRecord` (status `queued`), creates a `FilingJob`, commits, calls `enqueue_filing_job(job.id)` — the independent filing worker (`app/filing_automation/worker.py`, started on app boot) picks it up, logs in as the taxpayer, uploads the JSON, optionally e-verifies, and persists the acknowledgement.

**Verification:**
- Frontend `tsc --noEmit`: clean (no type errors)
- Frontend vitest (`mapDirectImportsToDraftPatch`): 8 passed
- Backend `import app.main`: OK
- Backend focused suites: 182 passed (R145 + draft→input + ITD builder + gateway v2 + orchestrator)
- Real-client generation (`EPPPG3078Q`): R145 dividend blocker resolved; generation proceeds past it.

**Files added:**
- `frontend/src/api/filingSubmit.ts`

**Files modified:**
- `app/engine/validators/itr1/input_rules.py` — R145 three-branch logic + Category B warning
- `app/engine/filing_gateway_v2.py` — detailed schema-violation logging + `logger` + `ITR1SchemaValidationError` import
- `app/routers/client_itr_v2.py` — `logger` + per-issue server-side logging on 422
- `tests/test_itr1_input_validation.py` — 2 new R145 warning/mismatch tests
- `frontend/src/pages/ITRComputationPage.tsx` — `filingSubmitApi` import, filing-job state, `handleDirectSubmit`, polling `useEffect`, Direct Submit button + inline status pill

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Type-2 vs Type-3 — Fundamental Differences](#2-type-2-vs-type-3--fundamental-differences)
3. [The Four Credential/Parameter Environments](#3-the-four-credentialparameter-environments)
4. [Target Architecture — Dual-Mode](#4-target-architecture--dual-mode)
5. [Work Package A — Type-3 Production Pipeline (This Season)](#5-work-package-a--type-3-production-pipeline-this-season)
6. [Work Package B — Type-2 Reorganization (Next Season)](#6-work-package-b--type-2-reorganization-next-season)
7. [Shared Subsystems — Used by Both Modes](#7-shared-subsystems--used-by-both-modes)
8. [Phase Roadmap](#8-phase-roadmap)
9. [Testing & Certification Strategy](#9-testing--certification-strategy)
10. [Security & Compliance](#10-security--compliance)
11. [Appendix — File Inventory](#appendix--file-inventory)

---

## 1. Executive Summary

Taxify will operate as a **dual-mode ERI product**:

- **Type-3 mode (production NOW, AY 2026-27 filing season):** No ITD API calls. Taxify generates a CBDT-compliant ITR JSON locally (using the official `Official JSON Schema/ITR-1..4_2026_Main_V1.1.json` schemas and `Official Validations/CBDT_…_Validation Rules_AY 2026-27.pdf` rules), then uploads it to the ITD portal either (a) manually by the taxpayer, or (b) automatically via a Playwright browser-automation uploader that logs in as the taxpayer and submits the JSON through the portal UI.

- **Type-2 mode (production NEXT season):** Official API integration with ITD. Requires the physical USB DSC token (local signing) + AWS-whitelisted-IP egress (remote dispatch). The existing `app/eri/*` modules are the foundation but need reorganization behind a mode switch, the submit flow added, and a local-signer + AWS-dispatcher split architecture.

**The critical architectural insight:** both modes share the same **ITR JSON generation engine** (`app/engine/itd/itr*.py` + `_compute_digest`) and the same **CBDT validation layer**. The ONLY divergence is the last mile — Type-3 uploads via browser, Type-2 dispatches via signed API envelope over whitelisted IP. Therefore the plan isolates the shared core (`FilingCore`) from the mode-specific transport (`Type2Transport`, `Type3Transport`).

**This season's deliverable:** Type-3 end-to-end production (generate JSON → validate against schema + rules → either download JSON for manual upload OR trigger Playwright uploader → poll for ARN → download acknowledgement). Type-2 remains in its current state behind a feature flag, reorganized but not completed.

---

## 2. Type-2 vs Type-3 — Fundamental Differences

| Dimension | Type-2 (API) | Type-3 (Offline Utility) |
|---|---|---|
| **ITD connection** | Official REST API over HTTPS | NONE — no API calls |
| **Credentials** | ClientID, ClientSecret, ERIUserID, ERIPassword, DSC | SW_ID only (for `CreationInfo.SWCreatedBy`) |
| **Whitelisted IP** | Required (AWS IP for Taxify) | Not required |
| **DSC** | Physical USB token, signs every request's `data` field | NOT required for JSON generation |
| **Per-request signing** | Yes (PKCS#7 of base64 payload) | No |
| **Digest** | Required (HMAC-SHA256, secret key + iterations from ITD) | Required — but the **secret key and iteration count come from the Type-3 onboarding credentials**, which differ from Type-2 |
| **Submission** | `POST /eriapi/submit` → returns `arnNumber` in JSON | Upload JSON via portal UI (manual or Playwright) → portal returns ARN |
| **e-Verify** | `updateVerMode` / `generateEvc` / `verifyEvc` APIs | Done on the portal after upload (manual or Playwright) |
| **Acknowledgement** | `getAcknowledgement` API returns binary PDF | Download from portal UI (manual or Playwright) |
| **Prefill** | `requestPrefillOTP` + `getPrefill` APIs | Taxify's existing Playwright downloader (`downloader_prefill.py`) — already built |
| **Client registration** | `addClient` / `registerClient` APIs | N/A — taxpayer logs into their own portal account |
| **Session** | Single ERI session, 24h, `autkn` token | Per-taxpayer portal session (Playwright) |
| **UAT certification** | ITD UAT sanity per ITR per AY, SW_ID enablement | ITD UAT sanity per ITR per AY, SW_ID enablement (different SW_ID) |
| **Production certification** | Separate prod credentials + IP whitelist + DSC re-registration | Same SW_ID as Type-3 UAT (or separate prod SW_ID per ITD policy) |

**Key takeaway:** Type-3 is strictly simpler — no API gateway, no DSC-per-request, no IP whitelist, no session management. The cost is that submission/prefill/acknowledgement/e-verify become **browser-automation tasks** (or manual steps), not API calls. Taxify already has a mature Playwright automation stack for *downloads*; this plan extends it to *uploads*.

---

## 3. The Four Credential/Parameter Environments

This is the user's explicitly raised concern. There are **four distinct credential sets**, and they must never be conflated.

| Environment | SW_ID | Secret Key | Iterations | Client ID/Secret | DSC | Whitelisted IP | Base URL |
|---|---|---|---|---|---|---|---|
| **Type-2 UAT** | `SW20014242` (example) | `4448ffc0cec1a25d` (example) | `1344` | UAT ClientID/Secret | Physical USB token (UAT-registered cert) | AWS UAT IP | `uatocpservices.incometax.gov.in/iec-uat/uat/eriapi` |
| **Type-2 Production** | `SW2xxxxxxxx` (different) | Different prod secret | Different prod iterations | Prod ClientID/Secret | Same physical USB token (prod-registered cert) | AWS Prod IP | `services.incometax.gov.in/iec/api/eriapi` |
| **Type-3 UAT** | `SW3xxxxxxxx` (different from Type-2) | Different Type-3 UAT secret | Different Type-3 UAT iterations | NONE | NONE | NONE | NONE |
| **Type-3 Production** | `SW3xxxxxxxx` (different from Type-3 UAT) | Different Type-3 prod secret | Different Type-3 prod iterations | NONE | NONE | NONE | NONE |

### 3.1 Resolution: Environment-Scoped `.env` Variables (NO vault for ERI creds)

**Decision:** All four environments' ERI credentials live **exclusively in `.env`** (never in `vault.py` or any other store). The existing `app/vault.py` is a `VaultManager` for **taxpayer** PII (taxpayer PAN, DOB, portal passwords) with a hardcoded master key — it is NOT an ERI-credential store and must not be repurposed for ERI secrets. ERI credentials are operator-level configuration, not taxpayer data, so `.env` is the correct home.

The four environments are disambiguated by **suffix-qualified env var names** keyed by `(mode, environment)`:

```
ERI_MODE = "type3"          # "type2" | "type3"
ERI_ENV  = "production"    # "uat" | "production"
```

A single resolver, `get_eri_credentials() -> ERICredentials`, reads the suffix-qualified vars and returns the right bundle:

```python
@dataclass(frozen=True)
class ERICredentials:
    mode: Literal["type2", "type3"]
    environment: Literal["uat", "production"]
    sw_id: str
    digest_secret_key: str | None       # Type-3 has this too!
    digest_iterations: int | None
    # Type-2 only:
    client_id: str | None
    client_secret: str | None
    eri_user_id: str | None
    eri_password: str | None
    base_url: str | None
    dsc_signing_mode: str | None        # "token" | "file" | "ngrok" | "mock"
    aws_ssh_host: str | None            # the whitelisted-IP jump box
    aws_ssh_user: str | None
    aws_ssh_key_path: str | None
```

The `.env` file carries ALL four credential sets simultaneously, suffixed so they never collide:

```env
# ──── Type-3 UAT ────
ERI_SW_ID_TYPE3_UAT=SW3xxxxxxxx
ERI_DIGEST_SECRET_KEY_TYPE3_UAT=________________
ERI_DIGEST_ITERATIONS_TYPE3_UAT=____

# ──── Type-3 Production ────
ERI_SW_ID_TYPE3_PRODUCTION=SW3xxxxxxxx
ERI_DIGEST_SECRET_KEY_TYPE3_PRODUCTION=________________
ERI_DIGEST_ITERATIONS_TYPE3_PRODUCTION=____

# ──── Type-2 UAT ────
ERI_SW_ID_TYPE2_UAT=SW20014242
ERI_DIGEST_SECRET_KEY_TYPE2_UAT=4448ffc0cec1a25d
ERI_DIGEST_ITERATIONS_TYPE2_UAT=1344
ERI_CLIENT_ID_TYPE2_UAT=4fea04621c7b5660dbb12b959a29b0ee
ERI_CLIENT_SECRET_TYPE2_UAT=________________
ERI_USER_ID_TYPE2_UAT=ERIP013181
ERI_PASSWORD_TYPE2_UAT=Oracle@123
ERI_BASE_URL_TYPE2_UAT=https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi
ERI_DSC_SIGNING_MODE_TYPE2_UAT=token
ERI_AWS_SSH_HOST_TYPE2_UAT=________________
ERI_AWS_SSH_USER_TYPE2_UAT=ec2-user
ERI_AWS_SSH_KEY_PATH_TYPE2_UAT=________________

# ──── Type-2 Production ────
ERI_SW_ID_TYPE2_PRODUCTION=SW2xxxxxxxx
ERI_DIGEST_SECRET_KEY_TYPE2_PRODUCTION=________________
ERI_DIGEST_ITERATIONS_TYPE2_PRODUCTION=____
ERI_CLIENT_ID_TYPE2_PRODUCTION=________________
ERI_CLIENT_SECRET_TYPE2_PRODUCTION=________________
ERI_USER_ID_TYPE2_PRODUCTION=________________
ERI_PASSWORD_TYPE2_PRODUCTION=________________
ERI_BASE_URL_TYPE2_PRODUCTION=https://services.incometax.gov.in/iec/api/eriapi
ERI_DSC_SIGNING_MODE_TYPE2_PRODUCTION=token
ERI_AWS_SSH_HOST_TYPE2_PRODUCTION=________________
ERI_AWS_SSH_USER_TYPE2_PRODUCTION=ec2-user
ERI_AWS_SSH_KEY_PATH_TYPE2_PRODUCTION=________________
```

The current `.env` values (which look like Type-2 UAT) are migrated to the `_TYPE2_UAT` suffixed names. `ERI_SW_ID` / `ERI_DIGEST_SECRET_KEY` / `ERI_DIGEST_ITERATIONS` (unsuffixed) are removed to prevent ambiguity.

**`.env` must be in `.gitignore`** (verify: `git check-ignore .env` passes). The four credential sets coexist in one `.env` file so the operator can switch modes by flipping `ERI_MODE` / `ERI_ENV` without editing secrets.

**Critical invariant:** The `SWCreatedBy` in the ITR JSON's `CreationInfo` and the `(secret_key, iterations)` used by `_compute_digest` MUST come from the SAME `(mode, environment)` suffix. Mixing Type-2 UAT SW_ID with Type-3 prod digest secret will produce JSONs that fail ITD validation. The resolver enforces this by reading both from the same suffix.

### 3.2 Startup Assertion

```python
# app/main.py lifespan startup
creds = get_eri_credentials()
if creds.mode == "type2":
    assert creds.dsc_signing_mode != "mock", "Mock DSC forbidden in Type-2"
    assert creds.aws_ssh_host, "AWS SSH host required for Type-2 (whitelisted IP)"
if creds.environment == "production":
    assert creds.dsc_signing_mode != "mock"
    # Type-2 prod also requires TLS verify = True
```

---

## 4. Target Architecture — Dual-Mode

```
                            ┌─────────────────────────────────────────┐
                            │           FILING CORE (shared)          │
                            │  ┌─────────────────────────────────────┐│
                            │  │ app/engine/itd/itr1..4.py            ││
                            │  │  build_itr1_json() ... build_itr4()  ││  ← per-form CBDT JSON builders
                            │  │ app/engine/itd/common.py             ││  ← _compute_digest, _creation_info
                            │  │ app/engine/validators/*              ││  ← local CBDT validation rules
                            │  │ app/engine/calculators/*            ││  ← tax math
                            │  └─────────────────────────────────────┘│
                            │  ┌─────────────────────────────────────┐│
                            │  │ app/engine/filing_orchestrator.py    ││  ← mode-agnostic JSON producer
                            │  │  produce_itd_json(client, ay, itr)   ││
                            │  └─────────────────────────────────────┘│
                            └───────────────┬─────────────────────────┘
                                            │
                   ┌────────────────────────┴────────────────────────┐
                   │                                                  │
        ┌──────────▼──────────┐                           ┌──────────▼──────────┐
        │  Type2Transport      │                           │  Type3Transport      │
        │  (app/eri/type2/*)   │                           │  (app/eri/type3/*)  │
        │                      │                           │                      │
        │  LocalSigner         │                           │  JsonExporter       │
        │  (USB DSC, win32crypt│                           │  (download .json)    │
        │   or cryptography     │                           │                      │
        │   PKCS#7)             │                           │  PortalUploader     │
        │                      │                           │  (Playwright, reuse  │
        │  AwsDispatcher        │                           │   automation/*)     │
        │  (SSH to whitelisted  │                           │                      │
        │   IP, dispatch signed │                           │  AckDownloader      │
        │   envelope, read resp)│                           │  (Playwright)       │
        │                      │                           │                      │
        │  EriApiClient         │                           │                      │
        │  (login, addClient,   │                           │                      │
        │   prefill, validate,  │                           │                      │
        │   submit, everify, ack)│                           │                      │
        └──────────────────────┘                           └──────────────────────┘
                   ▲                                                  ▲
                   │                                                  │
        ┌──────────┴──────────────────────────────────────────────────┴──────────┐
        │                    app/routers/filing.py                                │
        │  POST /api/v1/filing/{client_id}/{ay}/generate                         │
        │  POST /api/v1/filing/{client_id}/{ay}/submit                           │
        │  GET  /api/v1/filing/{client_id}/{ay}/status                           │
        │  GET  /api/v1/filing/{client_id}/{ay}/acknowledgement                  │
        │  (routes are mode-aware; dispatch to Type2 or Type3 transport)        │
        └─────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Module Layout

```
app/
├── eri/
│   ├── __init__.py
│   ├── config.py                 ← ERICredentials resolver, env-scoped
│   ├── credentials.py            ← reads ERI creds from .env (suffix-qualified)
│   ├── timestamp.py              ← UTC timestamp helper (Type-2)
│   ├── http_client.py            ← shared httpx client (Type-2)
│   ├── envelope.py               ← {data, sign, eriUserId} builder (Type-2)
│   ├── exceptions.py             ← ERIApiError (existing, keep)
│   ├── error_codes.py            ← ~70 ITD error codes (Type-2)
│   ├── session.py                ← EriSession store (Type-2)
│   ├── type2/                    ← TYPE-2 ONLY (future production)
│   │   ├── __init__.py
│   │   ├── login.py              ← (moved from app/eri/login.py)
│   │   ├── add_client.py         ← (moved)
│   │   ├── prefill.py            ← (moved)
│   │   ├── everify.py            ← (moved)
│   │   ├── acknowledgement.py    ← (moved)
│   │   ├── submit.py             ← NEW (validateItr + submitItr)
│   │   ├── client.py             ← (moved, refactored)
│   │   ├── local_signer.py       ← NEW: USB DSC signing (local)
│   │   └── aws_dispatcher.py    ← NEW: SSH-to-AWS + dispatch + read-response
│   └── type3/                    ← TYPE-3 (production NOW)
│       ├── __init__.py
│       ├── json_exporter.py      ← produce + validate + write .json file
│       ├── portal_uploader.py    ← NEW: Playwright upload automation
│       ├── ack_downloader.py     ← NEW: Playwright acknowledgement download
│       └── everify_portal.py      ← NEW: Playwright e-verify on portal
├── engine/
│   ├── itd/                      ← EXISTING, shared by both modes
│   │   ├── common.py             ← _compute_digest (env-scoped creds)
│   │   ├── itr1.py … itr4.py     ← EXISTING
│   │   └── __init__.py
│   ├── validators/               ← EXISTING; expand to full CBDT rules
│   ├── filing_orchestrator.py    ← NEW: mode-agnostic JSON producer
│   └── filing_gateway.py         ← EXISTING; refactor to dispatch by mode
├── automation/                   ← EXISTING; extend with upload flows
│   ├── browser.py                ← reuse
│   ├── auth.py                   ← reuse (portal login as taxpayer)
│   ├── navigation.py             ← reuse + extend to upload page
│   ├── downloader_prefill.py     ← Type-3 prefill path (reuse as-is)
│   └── uploader_itr.py          ← NEW: Playwright ITR upload
├── routers/
│   ├── filing.py                 ← NEW: unified filing endpoints
│   └── eri.py                    ← DEPRECATE (folded into filing.py)
└── services/
    └── submission_service.py     ← DEPRECATE (replaced by type3/portal_uploader.py)
```

---

## 5. Work Package A — Type-3 Production Pipeline (This Season)

This is the **primary deliverable**. Goal: by the end of this package, a Taxify user can (1) generate a CBDT-compliant ITR JSON for a client, (2) validate it locally against the official schema + CBDT validation rules, (3a) download the JSON for manual portal upload, OR (3b) click "Submit via Portal" which triggers Playwright to log in as the taxpayer and upload the JSON, (4) poll for the ARN, (5) download the acknowledgement PDF.

### A1: Environment-Scoped Credential Resolver

**Files:** `app/eri/config.py`, `app/eri/credentials.py`.

Implement `ERICredentials` dataclass + `get_eri_credentials()` resolver per §3. For Type-3, only `sw_id`, `digest_secret_key`, `digest_iterations` are populated. Source: `.env` exclusively (suffix-qualified vars `*_TYPE3_UAT`, `*_TYPE3_PRODUCTION`, `*_TYPE2_UAT`, `*_TYPE2_PRODUCTION`). No vault usage for ERI creds.

```python
# app/eri/config.py
import os
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ERICredentials:
    mode: Literal["type2", "type3"]
    environment: Literal["uat", "production"]
    sw_id: str
    digest_secret_key: str | None
    digest_iterations: int | None
    client_id: str | None = None
    client_secret: str | None = None
    eri_user_id: str | None = None
    eri_password: str | None = None
    base_url: str | None = None
    dsc_signing_mode: str | None = None
    aws_ssh_host: str | None = None
    aws_ssh_user: str | None = None
    aws_ssh_key_path: str | None = None

def get_eri_credentials() -> ERICredentials:
    mode = os.getenv("ERI_MODE", "type3").lower()
    env = os.getenv("ERI_ENV", "production").lower()
    sw_id = os.getenv(f"ERI_SW_ID_{mode.upper()}_{env.upper()}")
    secret = os.getenv(f"ERI_DIGEST_SECRET_KEY_{mode.upper()}_{env.upper()}")
    iters = int(os.getenv(f"ERI_DIGEST_ITERATIONS_{mode.upper()}_{env.upper()}", "1"))
    creds = ERICredentials(
        mode=mode, environment=env, sw_id=sw_id,
        digest_secret_key=secret, digest_iterations=iters,
    )
    if mode == "type2":
        creds = replace(creds,
            client_id=os.getenv(f"ERI_CLIENT_ID_{env.upper()}"),
            client_secret=os.getenv(f"ERI_CLIENT_SECRET_{env.upper()}"),
            eri_user_id=os.getenv(f"ERI_USER_ID_{env.upper()}"),
            eri_password=os.getenv(f"ERI_PASSWORD_{env.upper()}"),
            base_url=os.getenv(f"ERI_BASE_URL_{env.upper()}"),
            dsc_signing_mode=os.getenv("ERI_DSC_SIGNING_MODE", "token"),
            aws_ssh_host=os.getenv("ERI_AWS_SSH_HOST"),
            aws_ssh_user=os.getenv("ERI_AWS_SSH_USER", "ec2-user"),
            aws_ssh_key_path=os.getenv("ERI_AWS_SSH_KEY_PATH"),
        )
    return creds
```

**Validation:** Startup assertion in `main.py` lifespan. Unit test that all four `(mode, env)` combos resolve correctly.

### A2: Env-Scoped Digest Computation

**File:** `app/engine/itd/common.py` (modify `_compute_digest`).

Current `_compute_digest` reads `ERI_DIGEST_SECRET_KEY` and `ERI_DIGEST_ITERATIONS` directly from env. Change to resolve via `get_eri_credentials()`:

```python
def _compute_digest(data: dict) -> str:
    creds = get_eri_credentials()
    if not creds.digest_secret_key:
        return "-"   # dev placeholder
    iterations = creds.digest_iterations or 1
    # ... rest unchanged: minify, replace Digest, iterated HMAC-SHA256, base64
```

And `_creation_info` uses `creds.sw_id` instead of `os.getenv("ERI_SW_ID")`:

```python
def _creation_info() -> dict:
    creds = get_eri_credentials()
    return {
        "SWVersionNo": _SW_VERSION,
        "SWCreatedBy": creds.sw_id,
        "JSONCreatedBy": creds.sw_id,
        "JSONCreationDate": _today(),
        "IntermediaryCity": "Delhi",
        "Digest": "-",   # placeholder, replaced by _compute_digest
    }
```

**Validation:** Generate an ITR-1 JSON with Type-3 UAT creds → submit manually to ITD UAT portal → passes validation. Repeat with Type-3 prod creds → passes on prod portal.

### A3: Local CBDT Validation Layer (CRITICAL for Type-3)

**Rationale:** Type-3 has no API-side validation safety net. The JSON MUST be CBDT-compliant before upload, or the portal rejects it and the taxpayer has to retry. The official `CBDT_…_Validation Rules_AY 2026-27.pdf` files (ITR-1/2/3/4) define ~hundreds of rules per form. These must be implemented as local validators.

**Files:** `app/engine/validators/` (existing dir, expand).

**Tasks:**

1. **Extract validation rules** from the four CBDT validation PDFs (`Reference Docs by CBDT & ITD/Official Validations/`). Use `pdftotext -layout` to text-extract, then parse each rule into a structured catalog:
   ```python
   @dataclass
   class ValidationRule:
       rule_id: str          # e.g. "ITR1_RULE_001"
       form: str            # "ITR-1" | "ITR-2" | ...
       category: str        # "Field" | "Cross-Field" | "Computation" | "Conditional"
       description: str
       severity: str        # "ERROR" | "WARNING"
       jsonpath_predicate: str  # jq-like path to the field(s)
       condition: str       # ">", "==", "sum_equals", "if_then", ...
       reference_value: str | None
   ```
   Store as `app/engine/validators/catalogs/itr1_rules.json` etc.

2. **Implement rule engine** `app/engine/validators/engine.py`:
   ```python
   def validate_itr_json(itr_json: dict, form: str) -> list[ValidationFinding]:
       rules = load_catalog(form)
       findings = []
       for rule in rules:
           if _evaluate(rule, itr_json):
               findings.append(ValidationFinding(rule_id=rule.rule_id,
                                                  severity=rule.severity,
                                                  message=rule.description))
       return findings
   ```
   `_evaluate` supports the common predicate types (field-presence, numeric-compare, sum-of-section-equals-total, if-then-conditional).

3. **JSON Schema validation** (structural, before rule validation):
   ```python
   def validate_against_schema(itr_json: dict, form: str) -> None:
       schema_path = f"Reference Docs by CBDT & ITD/Official JSON Schema/ITR-{form[-1]}_2026_Main_V1.1.json"
       with open(schema_path) as f:
           schema = json.load(f)
       jsonschema.validate(itr_json, schema)
   ```

4. **Wire into orchestrator.** Before export/upload, run: schema validation → CBDT rule validation → if any ERROR-severity finding, block submission and surface to UI.

**Validation:** Known-bad JSONs (from ITD UAT sanity test data) are rejected with correct rule IDs. Known-good JSONs pass.

**This is the hardest part of Type-3.** Budget the most time here.

### A4: Filing Orchestrator (Mode-Agnostic JSON Producer)

**File:** `app/engine/filing_orchestrator.py` (new).

```python
def produce_itd_json(client_id: int, ay: str, itr_type: str, db: Session) -> dict:
    """Build, validate, and digest the ITD JSON for a client+AY+form.

    Shared by both Type-2 (API submit) and Type-3 (portal upload).
    """
    client = db.get(Client, client_id)
    client_itr = db.query(ClientITR).filter_by(
        client_id=client_id, year=ay).first()
    form_data = json.loads(client_itr.form_data)
    computed = json.loads(client_itr.computed_result)

    # 1. Build ITR JSON via per-form builder
    builders = {"ITR-1": build_itr1_json, "ITR-2": build_itr2_json,
                "ITR-3": build_itr3_json, "ITR-4": build_itr4_json}
    builder = builders[itr_type]
    itr_json = builder(client, form_data, computed, ay)

    # 2. Compute Digest and inject (env-scoped)
    digest = _compute_digest(itr_json)
    form_key = f"ITR{itr_type[-1]}"
    itr_json["ITR"][form_key]["CreationInfo"]["Digest"] = digest

    # 3. Validate structure (JSON Schema)
    validate_against_schema(itr_json, itr_type)

    # 4. Validate CBDT rules
    findings = validate_itr_json(itr_json, itr_type)
    errors = [f for f in findings if f.severity == "ERROR"]
    if errors:
        raise CBDTValidationError(errors)

    # 5. Persist to ImportedDocument (document_type="filed_return", source="generated")
    _persist_generated_json(db, client_id, client.user_id, ay, itr_json)

    return itr_json
```

**Validation:** Produces the same JSON for a given `(client, ay, itr)` regardless of `ERI_MODE`. Only the Digest's secret key/iterations differ by env.

### A5: Type-3 JSON Exporter

**File:** `app/eri/type3/json_exporter.py` (new).

```python
def export_itd_json_file(client_id: int, ay: str, itr_type: str, db: Session) -> Path:
    """Generate the ITD JSON and write it to a download .json file.

    Returns the path to the .json file (temp dir) for FastAPI FileResponse.
    """
    itr_json = produce_itd_json(client_id, ay, itr_type, db)
    # ITD portal expects minified JSON (Digest was computed on minified form;
    # the uploaded file must match byte-for-byte or Digest will mismatch).
    minified = json.dumps(itr_json, separators=(",", ":"), ensure_ascii=False)
    client = db.get(Client, client_id)
    filename = f"{client.pan}_{ay}_{itr_type}.json"
    out_path = Path(tempfile.gettempdir()) / filename
    out_path.write_text(minified, encoding="utf-8")
    return out_path
```

**Critical detail:** The uploaded JSON must be byte-identical to the minified form used for Digest computation. If the portal re-serializes with different spacing, the Digest check fails. The exporter writes the exact minified string.

### A6: Type-3 Portal Uploader (Playwright)

**Implemented file:** `app/filing_automation/uploader.py` (new), reusing only the stable browser/auth/navigation primitives from `app/automation/`.

This is the Playwright automation that logs in as the taxpayer and uploads the JSON. It's the Type-3 analog of the Type-2 `submitItr` API.

```python
class PortalUploader:
    """Playwright automation to upload an ITR JSON to the ITD e-filing portal.

    Reuses the existing browser/auth/navigation stack from app/automation/.
    Flow:
      1. Launch browser (headed; taxpayer may need to enter OTP)
      2. Login as taxpayer (reuse login_itd from app/automation/auth.py)
      3. Navigate to e-File → Income Tax Return → File Income Tax Return
      4. Select assessment year, form type, submission type (JSON)
      5. Upload the .json file produced by json_exporter
      6. Click Submit
      7. Poll for ARN on the confirmation page
      8. Return {arn_number, ack_receipt_no, status}
    """

    async def upload(
        self,
        client_id: int,
        ay: str,
        itr_type: str,
        json_path: Path,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict:
        client = await self._get_client(client_id)
        ctx = await self._init_browser(headless=False)  # taxpayer OTP needs headed
        page = await self._login_as_taxpayer(client, ctx, log_callback)
        await self._navigate_to_upload(page, ay, itr_type, log_callback)
        await self._upload_file(page, json_path, log_callback)
        await self._submit_and_confirm(page, log_callback)
        arn = await self._extract_arn(page, log_callback)
        return {"arn_number": arn, "status": "submitted"}
```

**Sub-tasks:**

- **A6.1:** Reuse `app/automation/browser.py` for Playwright launch (already supports headed/headless).
- **A6.2:** Reuse `app/automation/auth.py::login_itd` for taxpayer login. This currently logs in via the ERI credentials — for Type-3 it must log in as the **taxpayer** (PAN + password + OTP). Extend `auth.py` with a `login_as_taxpayer(client: Client)` that reads the client's `portal_password` from DB (encrypted via `vault.py`) and prompts for OTP via a log callback.
- **A6.3:** New `app/automation/navigation.py::goto_file_itr_page(page, ay, itr_type)` — portal URL: `https://eportal.incometax.gov.in/iec/foservices/` → e-File → Income Tax Return → File Income Tax Return.
- **A6.4:** Upload handler — `page.set_input_files('input[type=file]', str(json_path))`.
- **A6.5:** Submit + confirm — click "Proceed" → wait for "Submit" → click → wait for ARN display.
- **A6.6:** ARN extraction — the portal shows `Acknowledgement No. XXXXXXXXXXXXX` on the confirmation page; parse it.
- **A6.7:** Failure modes — portal-side validation errors (the JSON passed local validation but portal still rejects): capture the error banner text, return as structured failure.

**Validation:** E2E test with a UAT test PAN on the ITD UAT portal. Manual upload of the same JSON as a control.

### A7: Type-3 Acknowledgement Downloader (Playwright)

**Implemented file:** `app/filing_automation/uploader.py::download_acknowledgement` (same file, reuses the filing session).

After upload + e-verify, the acknowledgement PDF is downloadable from the portal's "View Filed Returns" page. Reuse the existing Playwright downloader pattern (`downloader_filed_return.py`):

```python
async def download_acknowledgement(self, client_id, ay, arn, ctx, log_callback):
    page = await ctx.new_page()
    await self._goto_view_filed_returns(page)
    await self._click_ack_download(page, arn)
    pdf_bytes = await self._wait_for_download(page)
    return pdf_bytes
```

### A8: Type-3 e-Verify on Portal (Playwright)

**Implemented file:** `app/filing_automation/uploader.py::everify_on_portal`.

After upload, the return must be e-verified. Options (taxpayer chooses):
- **Aadhaar OTP** — portal generates OTP to Aadhaar-linked mobile.
- **Bank EVC** — portal generates EVC to bank.
- **ITR-V** — print + post (no automation).
- **Verify Later** — no action.

```python
async def everify_on_portal(self, page, arn, mode: str, otp_callback: Callable) -> dict:
    await self._goto_everify_page(page, arn)
    if mode == "AADHAAR":
        await self._select_aadhaar_otp(page)
        await self._click_generate_otp(page)
        otp = await otp_callback("Enter Aadhaar OTP")  # UI prompts user
        await self._enter_otp(page, otp)
        await self._submit_everify(page)
    elif mode == "BANKEVC":
        # similar
    elif mode == "LATER":
        await self._select_verify_later(page)
        await self._submit(page)
    return {"everify_status": "success"}
```

### A9: Unified Filing Router

**File:** `app/routers/filing.py` (new, replaces the overlapping `eri.py` + parts of `integration.py`).

```python
router = APIRouter(prefix="/api/v1/filing", tags=["filing"])

@router.post("/{client_id}/{ay}/{itr_type}/generate")
def generate_itd_json(
    client_id: int, ay: str, itr_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate, validate, and persist the ITD JSON. Returns a preview."""
    itr_json = produce_itd_json(client_id, ay, itr_type, db)
    return {"json": itr_json, "digest": itr_json["ITR"][f"ITR{itr_type[-1]}"]["CreationInfo"]["Digest"]}

@router.get("/{client_id}/{ay}/{itr_type}/download")
def download_itd_json(
    client_id: int, ay: str, itr_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the .json file for manual portal upload."""
    path = export_itd_json_file(client_id, ay, itr_type, db)
    return FileResponse(path, filename=path.name, media_type="application/json")

@router.post("/{client_id}/{ay}/{itr_type}/submit")
async def submit_via_portal(
    client_id: int, ay: str, itr_type: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit via portal automation (Type-3) or API (Type-2)."""
    creds = get_eri_credentials()
    if creds.mode == "type3":
        # Produce JSON file
        json_path = export_itd_json_file(client_id, ay, itr_type, db)
        # Queue Playwright upload as a background job (reuses AutomationJob table)
        job = _create_automation_job(db, client_id, current_user.id, ay,
                                     job_type="PORTAL_UPLOAD_ITR",
                                     payload={"json_path": str(json_path),
                                              "itr_type": itr_type})
        return {"job_id": job.public_id, "status": "queued"}
    else:
        # Type-2: dispatch to Type2Transport (future)
        raise HTTPException(501, "Type-2 submission not implemented this season")

@router.get("/{client_id}/{ay}/status")
def filing_status(client_id: int, ay: str, ...):
    """Return the latest filing status (ARN, everify, acknowledgement)."""
    ...

@router.get("/{client_id}/{ay}/acknowledgement")
def download_acknowledgement(client_id: int, ay: str, ...):
    """Download the acknowledgement PDF (from ImportedDocument or portal)."""
    ...
```

### A10: Independent Filing Job Worker

**Files:** `app/filing_automation/worker.py` (new), `FilingJob` table (new).

**Implemented isolation decision:** Do **not** modify or dispatch through the existing `app/automation/job_worker.py`; it remains the proven Prefill/AIS/TIS/26AS import worker. Type-3 filing has its own serial queue, startup/shutdown lifecycle, `FilingJob` table, polling endpoint, uploader, OTP handoff, acknowledgement handling, and status persistence. It reuses only browser/login/navigation primitives, not the import worker or `AutomationJob` table.

### A11: Type-3 UAT Sanity Pack

Per the Type-3 SOP (`Digest_generation_ERI 2 (2).pdf` §3): generate UAT JSONs with UAT SW_ID + UAT secret/iterations, submit to `erihelp@incometax.gov.in` for sanity, await SW_ID enablement.

**Task:** Build `scripts/type3_uat_sanity.py` that:
1. Loads UAT test PANs (from `erihelp@incometax.gov.in` onboarding email).
2. For each ITR (1, 2, 3, 4), generates a JSON per test case.
3. Writes all to a `tmp/type3_uat_pack/` directory.
4. Zips and produces a manifest CSV for email submission.

---

## 6. Work Package B — Type-2 Reorganization (Next Season)

The existing Type-2 code is NOT deleted — it's moved behind the `type2/` subpackage and the mode switch. The specific fixes from the prior `ITD_ERI_INTEGRATION_ANALYSIS_AND_PLAN.md` (B1-B14) are deferred to next season, EXCEPT the structural reorganization needed now to avoid blocking Type-3.

### B1: Move Existing Modules to `app/eri/type2/`

Move `login.py`, `add_client.py`, `prefill.py`, `everify.py`, `acknowledgement.py`, `client.py` into `app/eri/type2/`. Update imports in `app/routers/integration.py` (which is kept as the Type-2 route set, behind a mode guard).

### B2: Mode-Guard the Type-2 Routes

```python
# app/routers/integration.py
@router.post("/api/v1/eri/login")
def login_eri(current_user = Depends(get_current_user)):
    creds = get_eri_credentials()
    if creds.mode != "type2":
        raise HTTPException(503, "ERI Type-2 API not enabled in current mode")
    # ... existing Type-2 login code
```

This prevents Type-2 API calls from firing in Type-3 mode (they'd fail without credentials anyway, but the guard gives a clean 503).

### B3: The Local-Signer + AWS-Dispatcher Split (Type-2 Architecture)

This is the user's described UAT workflow, formalized. It is NOT built this season, but the architecture is documented so next season's implementation is plug-in.

**The constraint:** DSC is a physical USB token on the local machine. Whitelisted IP is an AWS instance. The signed API request must egress from the AWS IP, but the signature must be produced on the local machine (where the USB token is).

**Architecture:**

```
Local Machine (USB DSC)                      AWS Instance (Whitelisted IP)
─────────────────────                        ────────────────────────────
1. Build payload (produce_itd_json)          .
2. base64(payload) → "data"                  .
3. LocalSigner.sign(data_b64)                .
   ├─ win32crypt.CryptSignMessage(           .
   │    USB token, PKCS#7 attached)          .
   └─ returns "sign" (b64 PKCS#7)            .
4. SSH → AWS:                                 .
   send {data, sign, eriUserId,              .
         endpoint, headers}                  → 5. Receive signed envelope
                                              6. POST to ITD gateway from AWS
                                              7. Receive ITD response
                                              8. SSH ← Local: return response
9. Parse response, update DB                 ←
```

**Files (next season):**
- `app/eri/type2/local_signer.py` — wraps `win32crypt.CryptSignMessage` (token mode of current `envelope.py`), with a small HTTP server the AWS dispatcher can call (or use the existing ngrok approach). Better: use `paramiko` SSH from local → AWS, execute a Python script on AWS that receives the envelope via stdin, posts to ITD, returns the response via stdout. No ngrok needed.
- `app/eri/type2/aws_dispatcher.py` — `dispatch_signed_envelope(envelope, endpoint) -> dict`. Uses `paramiko.SSHClient` to run `python /opt/taxify/eri_proxy.py` on the AWS host, passes the envelope as JSON via stdin, reads the ITD response from stdout.

```python
# app/eri/type2/aws_dispatcher.py (NEXT SEASON)
import paramiko, json
from app.eri.config import get_eri_credentials

def dispatch_signed_envelope(envelope: dict, endpoint: str) -> dict:
    creds = get_eri_credentials()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(creds.aws_ssh_host, username=creds.aws_ssh_user,
                key_filename=creds.aws_ssh_key_path)
    # Remote script: read envelope from stdin, POST to ITD, print response
    remote_cmd = (f"python3 /opt/taxify/eri_proxy.py "
                  f"--endpoint {endpoint} --base-url {creds.base_url}")
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.write(json.dumps(envelope))
    stdin.channel.shutdown_write()
    resp_text = stdout.read().decode()
    ssh.close()
    return json.loads(resp_text)
```

The remote `/opt/taxify/eri_proxy.py` is a tiny `httpx`-based POST-to-ITD script installed on the AWS instance.

**This season:** the existing `envelope.py::sign_data` (token mode) + `client.py::eri_post` (httpx direct) remains as-is. The split is implemented next season. The current code works for local UAT because the local machine's IP can be whitelisted too (or the ngrok path is used).

### B4: Type-2 Submit Flow (Next Season)

As described in the prior plan (`WP-4a` through `WP-4e`): `app/eri/type2/submit.py` with `validate_itr` + `submit_itr`, but using `aws_dispatcher.dispatch_signed_envelope` instead of direct `httpx.post`.

---

## 7. Shared Subsystems — Used by Both Modes

These are mode-agnostic and must work identically regardless of `ERI_MODE`.

### 7.1 ITR JSON Builders (`app/engine/itd/itr1..4.py`)

Already exist. Only modification: env-scoped `_creation_info` and `_compute_digest` (per A2). No other changes.

### 7.2 Tax Engine (`app/engine/calculators/`, `app/engine/common/`)

Unchanged. Produces the `computed_result` consumed by the JSON builders.

### 7.3 Prefill Data (Diverges by Mode!)

- **Type-3:** Prefill is fetched via the EXISTING Playwright downloader (`app/automation/downloader_prefill.py`) — logs in as taxpayer, downloads prefill JSON, stores in `ImportedDocument`. This is the Type-3 prefill path and it's already built.
- **Type-2:** Prefill via `requestPrefillOTP` + `getPrefill` APIs (existing `app/eri/type2/prefill.py`). Next season.

Both store to the same `ImportedDocument` table with `source = "eri_api"` (Type-2) or `source = "portal_download"` (Type-3). The downstream importer pipeline (`app/engine/importers/`) doesn't care about the source.

### 7.4 Client & Return DB Models

`Client`, `ClientITR`, `ImportedDocument`, `AutomationJob` — unchanged. Add `EriSession` (Type-2 only, next season). Add `FilingRecord` to track ARN/ack per `(client, ay, itr)`:

```python
class FilingRecord(Base):
    __tablename__ = "filing_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    assessment_year: Mapped[str] = mapped_column(String(10), nullable=False)
    itr_type: Mapped[str] = mapped_column(String(10), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # type2 | type3
    environment: Mapped[str] = mapped_column(String(10), nullable=False)  # uat | production
    sw_id: Mapped[str] = mapped_column(String(20), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=True)
    json_path: Mapped[str] = mapped_column(String(500), nullable=True)
    arn_number: Mapped[str] = mapped_column(String(20), nullable=True)
    everify_mode: Mapped[str] = mapped_column(String(20), nullable=True)
    everify_status: Mapped[str] = mapped_column(String(20), nullable=True)
    ack_pdf_path: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    # generated → uploaded → everified → acknowledged
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 7.5 Audit Log

Every filing action (generate, validate, upload, everify, ack) is audit-logged with `{user_id, client_id, ay, mode, environment, action, outcome, itd_code}`. No payload in logs.

---

## 8. Phase Roadmap

### Phase 1 — Type-3 Foundation (Week 1-2)

| Step | Work Item | Deliverable |
|---|---|---|
| 1.1 | A1: Credential resolver | `get_eri_credentials()` works for all 4 envs; startup assertions pass |
| 1.2 | A2: Env-scoped digest | `_compute_digest` + `_creation_info` use resolver |
| 1.3 | B1+B2: Move Type-2 modules behind `type2/` + mode guard | Type-2 routes return 503 in Type-3 mode; no behavior change in Type-2 mode |
| 1.4 | A4: Filing orchestrator | `produce_itd_json()` produces schema-valid JSON |

### Phase 2 — Type-3 Validation Layer (Week 2-4) — HARDEST

| Step | Work Item | Deliverable |
|---|---|---|
| 2.1 | A3.1: Extract CBDT validation rules from 4 PDFs | `itr1..4_rules.json` catalogs |
| 2.2 | A3.2: Implement rule engine | `validate_itr_json()` runs all rules |
| 2.3 | A3.3: JSON Schema validation | `validate_against_schema()` |
| 2.4 | A3.4: Wire into orchestrator | Blocking ERROR-severity findings surface to UI |

### Phase 3 — Type-3 Submission Automation (Week 4-6)

| Step | Work Item | Deliverable |
|---|---|---|
| 3.1 | A5: JSON exporter | `.json` file download works |
| 3.2 | A6: Portal uploader (Playwright) | Upload to UAT portal returns ARN |
| 3.3 | A7: Acknowledgement downloader | PDF downloaded from portal |
| 3.4 | A8: e-Verify on portal | Aadhaar OTP / Bank EVC / Verify Later |
| 3.5 | A9: Unified filing router | All `/api/v1/filing/*` endpoints live |
| 3.6 | A10: Independent filing worker | Dedicated `FilingJob` queue processes portal uploads; existing import worker remains unchanged |

### Phase 4 — Type-3 UAT Certification (Week 6-8)

| Step | Work Item | Deliverable |
|---|---|---|
| 4.1 | A11: UAT sanity pack | JSONs for ITR-1/2/3/4 emailed to `erihelp@incometax.gov.in` |
| 4.2 | UAT sanity feedback | Fix any rule-engine gaps surfaced by ITD |
| 4.3 | SW_ID enablement | Type-3 prod SW_ID enabled for AY 2026-27 |

### Phase 5 — Type-3 Production (Week 8+)

| Step | Work Item | Deliverable |
|---|---|---|
| 5.1 | Switch `ERI_MODE=type3`, `ERI_ENV=production` | Resolver loads prod creds |
| 5.2 | Production filing | Real taxpayer filings via portal upload |
| 5.3 | Frontend UI | "Generate JSON", "Download JSON", "Submit via Portal", "Download Ack" buttons |

### Phase 6 — Type-2 Completion (Next Season)

| Step | Work Item | Deliverable |
|---|---|---|
| 6.1 | B3: Local-signer + AWS-dispatcher | `paramiko` SSH dispatch works |
| 6.2 | B4: Type-2 submit flow | `validate_itr` + `submit_itr` via AWS |
| 6.3 | Type-2 fixes (B1-B14 from prior plan) | All endpoint bugs fixed |
| 6.4 | Type-2 UAT certification | SW_ID enablement for Type-2 |
| 6.5 | Type-2 production switch | `ERI_MODE=type2`, `ERI_ENV=production` |

---

## 9. Testing & Certification Strategy

### 9.1 Type-3 Testing

- **Unit:** `test_digest.py` (known-vector), `test_validators_itr1..4.py` (known-good and known-bad JSONs from ITD UAT test data).
- **Integration:** `test_filing_orchestrator.py` (produces valid JSON for each form).
- **E2E (UAT):** `test_portal_upload_itr1.py` — Playwright uploads to ITD UAT portal, asserts ARN returned.
- **Manual control:** Same JSON uploaded manually to portal must also succeed (validates that automation isn't masking a JSON defect).

### 9.2 Type-2 Testing (Next Season)

- **Unit:** mock `paramiko.SSHClient`, assert envelope is dispatched correctly.
- **Integration:** Local UAT with local IP whitelisted (current state) OR the ngrok path.
- **E2E (UAT):** Full submit via AWS dispatcher → ITD UAT → ARN.

### 9.3 Mode-Isolation Testing

- In `ERI_MODE=type3`: all `/api/v1/eri/*` (Type-2) routes return 503; all `/api/v1/filing/*` routes work via Playwright.
- In `ERI_MODE=type2`: `/api/v1/eri/*` routes work; `/api/v1/filing/*/submit` dispatches via Type-2 transport (next season).

### 9.4 ITD Certification (Per SOP §3-4)

Type-3:
1. Email `erihelp@incometax.gov.in` for UAT creds (SW_ID, secret, iterations).
2. Generate UAT JSONs for each ITR.
3. Submit JSONs for validation.
4. ITD performs sanity checks (1-2 working days).
5. SW_ID enabled for specific ITR + AY.

Type-2 (next season):
1. Same UAT credential request flow.
2. Additional: IP whitelist, DSC public cert upload.
3. API-level UAT sanity per endpoint.
4. SW_ID enablement for Type-2.

**Annual AY refresh:** Download new schemas + validation rules PDFs each AY; update catalogs; re-run UAT sanity.

---

## 10. Security & Compliance

### 10.1 Type-3 (This Season)

- [ ] `ERI_MODE=type3`, `ERI_ENV=production` asserted at startup
- [ ] Type-3 prod secret key + iterations in `.env` (suffix-qualified `_TYPE3_PRODUCTION`), `.env` in `.gitignore`
- [ ] Type-2 routes return 503 (mode guard)
- [ ] Generated JSON contains correct prod SW_ID + prod Digest
- [ ] Playwright taxpayer login uses `vault.py`-encrypted portal passwords (taxpayer PII — correct use of vault)
- [ ] Taxpayer OTP never logged (PII redaction filter)
- [ ] ARN + ack PDF stored in `FilingRecord`, access-controlled per user
- [ ] Audit log of all filing actions
- [ ] No `print()` debug statements in any `app/eri/type3/` or `app/automation/uploader_itr.py` code

### 10.2 Type-2 (Next Season)

- [ ] AWS SSH key path in `.env` (`ERI_AWS_SSH_KEY_PATH_TYPE2_*`), key file on disk with `chmod 600`, `.env` in `.gitignore`
- [ ] AWS instance has ITD root CA bundled, `verify=True`
- [ ] `paramiko` SSH uses key-based auth (no passwords)
- [ ] Remote `eri_proxy.py` on AWS only accepts connections from the local Taxify instance (mTLS or SSH tunnel only — no public port)
- [ ] DSC token PIN never stored; entered per-session via local prompt
- [ ] ngrok signer mode (if kept) requires mTLS to the ngrok URL
- [ ] All four env credential sets in `.env` with distinct suffix-qualified names
- [ ] Type-2 prod DSC public cert uploaded to ITD portal

---

## Appendix — File Inventory

### New Files (Type-3 Focus, This Season)

| Path | Purpose |
|---|---|
| `app/eri/config.py` | `ERICredentials` + `get_eri_credentials()` resolver |
| `app/eri/credentials.py` | Vault-backed secret store |
| `app/eri/type3/__init__.py` | Type-3 subpackage |
| `app/eri/type3/json_exporter.py` | `export_itd_json_file()` |
| `app/automation/uploader_itr.py` | `PortalUploader`, ack downloader, everify-on-portal |
| `app/engine/filing_orchestrator.py` | `produce_itd_json()` (shared) |
| `app/engine/validators/engine.py` | CBDT rule engine |
| `app/engine/validators/catalogs/itr1..4_rules.json` | Rule catalogs (from PDFs) |
| `app/routers/filing.py` | Unified `/api/v1/filing/*` routes |
| `app/db/models.py` (extend) | `FilingRecord` table |
| `scripts/type3_uat_sanity.py` | UAT sanity pack generator |

### Moved Files (Type-2 Reorganization, This Season)

| From | To |
|---|---|
| `app/eri/login.py` | `app/eri/type2/login.py` |
| `app/eri/add_client.py` | `app/eri/type2/add_client.py` |
| `app/eri/prefill.py` | `app/eri/type2/prefill.py` |
| `app/eri/everify.py` | `app/eri/type2/everify.py` |
| `app/eri/acknowledgement.py` | `app/eri/type2/acknowledgement.py` |
| `app/eri/client.py` | `app/eri/type2/client.py` |

### Kept-As-Is (Shared)

| Path | Notes |
|---|---|
| `app/eri/envelope.py` | Used by Type-2 only; `build_request_envelope`, `parse_response_envelope`, `eri_headers` stay |
| `app/eri/exceptions.py` | Shared `ERIApiError` |
| `app/engine/itd/common.py` | Modified: `_compute_digest` + `_creation_info` env-scoped |
| `app/engine/itd/itr1..4.py` | Unchanged |
| `app/automation/browser.py`, `auth.py`, `navigation.py` | Reused by Type-3 uploader |
| `app/automation/downloader_prefill.py` | Type-3 prefill path (already built) |

### Deprecated / Removed (This Season)

| Path | Action |
|---|---|
| `app/routers/eri.py` | **Delete** — overlapping with `integration.py`; its endpoints are superseded by `/api/v1/filing/*` |
| `app/services/submission_service.py` | **Delete** — replaced by `app/eri/type3/portal_uploader.py` (Playwright uploader) and next-season `app/eri/type2/submit.py` |
| `app/eri/client.py::eri_post` redundant header logic | Clean up (next season with Type-2 fixes) |

### New Files (Type-2, Next Season Only)

| Path | Purpose |
|---|---|
| `app/eri/type2/submit.py` | `validate_itr` + `submit_itr` |
| `app/eri/type2/local_signer.py` | USB DSC signing wrapper |
| `app/eri/type2/aws_dispatcher.py` | `paramiko` SSH dispatch to whitelisted IP |
| `app/eri/session.py` | `EriSession` store |
| `app/eri/error_codes.py` | ~70 ITD error codes |
| `app/eri/http_client.py` | Shared `httpx` client |
| `app/eri/timestamp.py` | UTC timestamp helper |
| Remote: `/opt/taxify/eri_proxy.py` | AWS-side POST-to-ITD proxy |

---

## Conclusion

The dual-mode architecture lets Taxify ship **Type-3 production this filing season** (CBDT-compliant JSON generation + Playwright portal upload) while preserving the existing Type-2 API code as a reorganized, mode-guarded foundation for next season's completion.

**This season's critical path:**
1. **A1** (credential resolver) — unblocks the four-env problem.
2. **A2** (env-scoped digest) — ensures the Digest + SW_ID match the target environment.
3. **A3** (CBDT validation layer) — the hardest and most important; without it, the portal will reject JSONs and the taxpayer experience collapses.
4. **A4 + A5** (orchestrator + exporter) — produce the downloadable JSON.
5. **A6** (Playwright uploader) — the Type-3 analog of `submitItr`.
6. **A9** (unified filing router) — one API surface for the frontend.
7. **A11 + Phase 4** (UAT sanity + certification) — SW_ID enablement.

**Next season's Type-2 completion** (B3 + B4 + the prior plan's B1-B14 fixes) plugs in via the same `produce_itd_json()` core, with the local-signer + AWS-dispatcher split handling the physical-DSC + whitelisted-IP constraint.

The single most important invariant throughout: **the ITR JSON generation and Digest computation are environment-scoped and mode-agnostic** — the same `produce_itd_json()` call produces a valid JSON whether the transport is a Playwright upload (Type-3) or a signed API envelope (Type-2). The transport is the only thing that changes.
