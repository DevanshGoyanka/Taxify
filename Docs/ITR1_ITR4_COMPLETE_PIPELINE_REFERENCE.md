# ITR-1 & ITR-4 Complete Pipeline Reference — Verified Against Current Code

**Date:** 2026-09-01
**Method:** Every claim in this document was independently verified by reading the actual
current source files (frontend and backend), not by trusting any other markdown doc's
self-reported status. Where an existing doc's claim turned out to be stale or inaccurate,
that is called out explicitly in §0. All file:line citations were confirmed against the code
as it exists today.
**Purpose:** This is the ground-truth reference for how a production-ready form (ITR-1,
ITR-4) actually works end to end — imports through final JSON generation, every route,
every persistence point. ITR-2 and ITR-3 implementation planning (`Docs/ERI_UAT_EXPANSION_PLAN.md`)
must follow this exact pattern, not the pattern described in older, now-stale docs.

---

## 0. Corrections to existing documentation

Three prior docs were checked against current code and found to contain stale or inaccurate
claims. Do not trust them for current architecture without re-verifying — they're kept for
historical record, not as a live reference:

| Doc | Claim | Reality |
|---|---|---|
| `Docs/ITR1_DATA_FLOW_AUDIT.md` (2026-08-17) | Documents a flat-blob-only architecture as "the" ITR-1 flow — `legacyAdapter.ts`, `legacySerializer.ts`, `composeLegacyPayload`, `_compute_tax_summary_impl` as the live path | **Entirely superseded.** `legacyAdapter.ts`/`legacySerializer.ts` are deleted (confirmed absent from disk). The live frontend flow goes exclusively through the `/v2/*` canonical `ReturnDraft` pipeline (§3). This doc predates the ITR-1 simplification + ITR4_V2 migration and describes dead architecture. |
| `Docs/ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` Phase 7 "Files to DELETE" bullet | Lists `app/engine/filing_gateway.py` (entire file) as deleted | **Contradicted by the same phase's own "Implemented"/"Deferred follow-ups" text**, which explicitly says the file was *not* fully deleted — only the ITR-4-specific functions (`_build_itr4_official_json`, `_build_itr4_input_from_flat`, `_itr4_builder_kwargs`) were removed. `generate_filing_artifact` and `_build_itr1_input_from_flat` remain in the file (now 636 lines, down from 1442). The doc's own later text is correct; only the early "planned deletion" bullet is misleading if read in isolation. |
| Same doc, Phase 7 deferred note | Claims the legacy `client_itr.py` `generate-cbdt-json` endpoint is "the live path for ITR-1/2/3 callers still on the flat-blob flow" through the legacy gateway | **Stale.** That endpoint (`client_itr.py:174,228`) was already repointed to call `filing_gateway_v2.generate_cbdt_json` directly — it bypasses `filing_gateway.py` entirely. It's also not called by the current frontend at all (§2). |
| Same doc | Lists `frontend/src/api/itrCompute.ts` and `frontend/src/api/itr2Mapper.ts` as deleted in Phase 7 | **Not deleted** — both files still exist on disk. They are, however, confirmed dead (imported by nothing outside themselves), so the *intent* was achieved even though the files remain. |
| `app/engine/draft_to_itr1_input.py` module docstring | Claims `_build_itr1_input_from_flat` was "deleted in Phase 7" | **False as of current code** — it's still defined at `app/engine/filing_gateway.py:424`, just orphaned (unreachable from any live route — see §4). |

---

## 1. Executive summary

For a client filing **ITR-1 or ITR-4 through the shipped frontend today**, the entire
load → compute → save → validate → generate-CBDT-JSON → Direct-Submit flow runs exclusively
through one canonical pipeline:

```
ITRComputationPage.tsx
  → itrV2.ts / filingSubmitApi.ts (frontend API clients)
    → /v2/clients/{id}/itr/{year}/*  (client_itr_v2.py)
    → /v2/tax-summary/compute        (tax_v2.py)
    → /api/v1/filing/*               (filing.py)
      → app.engine.filing_gateway_v2  (compute_canonical_itr{1,4}, generate_cbdt_json)
        → app.engine.draft_to_itr{1,4}_input  (the ONE canonical mapper per form)
          → app.engine.calculators.itr{1,4}   (pure tax computation)
          → app.engine.validators.itr{1,4}    (CBDT Category A/B/D rules)
          → app.engine.itd.itr{1,4}           (official CBDT JSON builder)
            → app.eri.digest                  (the ONE canonical Digest computation)
      → app.eri.type3.json_exporter → app.engine.filing_orchestrator → (same v2 call above)
        → app.filing_automation.worker → app.filing_automation.uploader (Playwright, Type-3 portal upload)
```

There is a large amount of **dead code still present in the repository** — an entire legacy
router (`client_itr.py`), a legacy compute function (`tax.py::_compute_tax_summary_impl`),
a legacy CBDT builder path (`filing_gateway.py::generate_filing_artifact` for ITR-1), and
~15 backend routes with zero frontend callers. None of it executes during normal use. It's
catalogued in §2 so it isn't mistaken for live architecture, and is a candidate for a future
cleanup pass — not touched by this document or by the ITR-2/3 work it informs.

**`app/engine/filing_gateway.py` (legacy gateway) is confirmed unreachable for ITR-1 and
ITR-4** in the running application. Its only live caller is `filing_orchestrator.py`'s
ITR-2/ITR-3 branch — and that branch is *also* currently unreachable in practice, because
every live route that calls into the orchestrator normalizes `itr_type` to ITR-1/ITR-4 only
before the call (§4, §5). ITR-2/ITR-3 today run through a **third, entirely separate**
path — `app/routers/tax.py::_compute_itr2_from_flat_payload` (flat frontend payload,
non-`ReturnDraft`) — which is itself distinct from both the v2 canonical pipeline and the
legacy `filing_gateway.py`.

---

## 2. Complete API route inventory

Routers mounted in `app/main.py` (in order): `auth`, `itr`, `clients`, `client_itr`
(legacy), `client_itr_v2`, `integration`, `pan`, `tax`, `tax_v2`, `dashboard`, `automation`,
`filing`. Plus `GET /health` and `GET /me` defined directly in `main.py`.

**Legend:** CALLED = a live frontend code path hits this route today. DEAD = the route is
registered and functional but no current frontend code calls it (a stray test or script
caller doesn't count as "live" for this table — noted separately where relevant).

| Router | Method | Path | Status | Notes |
|---|---|---|---|---|
| `itr.py` | POST | `/itr1/compute`, `/itr2/compute`, `/itr3/compute`, `/itr4/compute` | **DEAD** | `itrCompute.ts` wraps these but is imported nowhere |
| `itr.py` | POST | `/itr1/compute-json`, `/itr2/compute-json`, `/itr3/compute-json`, `/itr4/compute-json` | **DEAD** | superseded by `/v2/.../generate-cbdt-json` |
| `itr.py` | POST/GET | `/returns/save`, `/returns`, `/returns/{id}` | **DEAD** | same unused `itrCompute.ts` module |
| `client_itr.py` (legacy) | GET/PUT/POST/GET | all 5 routes under `/clients/{id}/itr/{year}` | **DEAD** | fully superseded by `client_itr_v2.py`; only live consumers are `tests/test_integration_routers.py` (direct function calls) and `scripts/audit_itr1_rule_matrix.py` (text-scans the file, not a runtime call) |
| `client_itr_v2.py` | GET | `/v2/clients/{id}/itr/{year}` | **CALLED** | page load |
| `client_itr_v2.py` | PUT | `/v2/clients/{id}/itr/{year}` | **CALLED** | save |
| `client_itr_v2.py` | POST | `/v2/clients/{id}/itr/{year}/generate-cbdt-json` | **CALLED** | Generate CBDT JSON button |
| `client_itr_v2.py` | GET | `/v2/clients/{id}/itr/{year}/download` | **DEAD** | defined, unused |
| `client_itr_v2.py` | GET | `/v2/clients/{id}/itr/{year}/download-pdf` | **CALLED** | PDF button |
| `tax.py` | POST | `/tax-summary/compute` (+ alias `/api/tax/compute`) | **DEAD as HTTP route** | function still called *internally* by legacy `client_itr.py:125` |
| `tax.py` | POST | `/business-income/*`, `/capital-gains/*` | **DEAD** | standalone calculators, no frontend caller (their would-be caller `capitalGainsCalculationService.ts` is itself unused) |
| `tax_v2.py` | POST | `/v2/tax-summary/compute` | **CALLED** | every keystroke (debounced) + Validate |
| `tax_v2.py` | POST | `/v2/imports/parse-reconcile` | **DEAD** | despite its own docstring's claim of being the live import path, nothing calls it |
| `filing.py` | POST | `/api/v1/filing/{id}/{ay}/{itr}/generate` | **DEAD** | preview-only variant, unused |
| `filing.py` | GET | `/api/v1/filing/{id}/{ay}/{itr}/download` | **DEAD** | manual-download variant, unused |
| `filing.py` | POST | `/api/v1/filing/{id}/{ay}/{itr}/submit` | **CALLED** | Direct Submit button |
| `filing.py` | GET | `/api/v1/filing/jobs/{job_id}` | **CALLED** | polling loop |
| `filing.py` | POST | `/api/v1/filing/jobs/{job_id}/otp` | defined, **not wired into Direct Submit** | Direct Submit hardcodes `verification_mode=LATER`; this endpoint backs a not-yet-connected Aadhaar-OTP/Bank-EVC UI path |
| `filing.py` | GET | `/api/v1/filing/{id}/{ay}/status` | **CALLED** | durable status read |
| `filing.py` | GET | `/api/v1/filing/{id}/{ay}/{itr}/acknowledgement` | **DEAD** | superseded by the `/fetch` variant |
| `filing.py` | POST | `/api/v1/filing/{id}/{ay}/{itr}/acknowledgement/fetch` | **CALLED** | Fetch Acknowledgement button |
| `automation.py` | POST | `/clients/{id}/automation/import` | **CALLED** | AIS/TIS/26AS portal download |
| `automation.py` | POST | `/clients/{id}/automation/login` | **CALLED** | standalone portal login |
| `automation.py` | GET | `/automation/jobs/{job_id}` | **CALLED** | job polling |
| `automation.py` | GET | `/automation/jobs` | **DEAD** | list-all, unused |
| `integration.py` (import subset) | POST | form16/AIS/TIS/26AS/prefill import routes | **CALLED** | all live, see full table in agent transcript |
| `integration.py` | POST/GET | `/integration/reconciliation`, `/integration/reconciliation/client/{id}` | **DEAD** | second one also has a real bug — calls `resolve_owned_client` with arguments in the wrong order |
| `clients.py`, `dashboard.py`, `pan.py`, `auth.py` | — | standard CRUD/auth | **mostly CALLED** | `restore`, `getYears`, `pan-analysis`(client-scoped), and plain `/pan/{pan}/validate` are DEAD; everything else used |

**Key structural finding:** there is no longer a "legacy ITR API module" the frontend falls
back to — `frontend/src/api/itrV2.ts` and `frontend/src/api/filingSubmit.ts` are the *only*
ITR-1/ITR-4 API clients `ITRComputationPage.tsx` imports. `itrCompute.ts` and `itr2Mapper.ts`
exist on disk but have zero external importers.

---

## 3. ITR-1: verified end-to-end trace

### 3.1 Frontend (`frontend/src/pages/ITRComputationPage.tsx`)

| Action | Frontend call | Backend route |
|---|---|---|
| Page load | `returnRepository.get()` → `itrV2.get()` (`api/itrV2.ts:59-64`) | `GET /v2/clients/{id}/itr/{year}` |
| Compute (debounced 500ms) | `itrV2.compute()` (`itrV2.ts:76-79`) | `POST /v2/tax-summary/compute` |
| Save | `returnRepository.save()` → `itrV2.put()` | `PUT /v2/clients/{id}/itr/{year}` |
| Validate | `handleValidate`: frontend field checks → save (PUT) → `itrV2.compute()` again, reads `errors`/`warnings` off the response | *no separate validate route* — validation **is** the compute call |
| Generate CBDT JSON | save (PUT) → `itrV2.generate()` (`itrV2.ts:82-96`) | `POST /v2/clients/{id}/itr/{year}/generate-cbdt-json` |
| Direct Submit | save (PUT) → `filingSubmitApi.submit(..., 'LATER')` | `POST /api/v1/filing/{id}/{ay}/{itr}/submit` |

The response of the `GET` load is a full `ReturnDraft` JSON, validated client-side via
`assertCanonicalDraft` which requires a `schemaVersion` key
(`frontend/src/domain/returns/canonicalRepository.ts:71-79`).

### 3.2 Backend call chain

**Compute** (`POST /v2/tax-summary/compute`):
1. `compute_tax_summary_v2` (`app/routers/tax_v2.py:24-54`) → `filing_gateway_v2.compute_canonical(draft)`.
2. `compute_canonical` (`filing_gateway_v2.py:1185-1210`) dispatches on `draft.form == "ITR-1"` → `compute_canonical_itr1(draft)` (`:313-381`).
3. `compute_canonical_itr1` rejects drafts with pending reconciliation discrepancies or
   `OUT_OF_SCOPE_TAXABLE` evidence still unresolved (`:337-359`), then calls
   `draft_to_itr1_input(draft)` (`app/engine/draft_to_itr1_input.py:1089`) — the **single
   canonical mapper**, `ReturnDraft → ITR1Input + breakdown`.
4. `compute_itr1(typed_input)` (`app/engine/calculators/itr1.py:213`) — pure tax computation, `ITR1Result`.
5. Wrapped into `ITR1PipelineResult` with a `summary` (`filing_gateway_v2.py:200-311`) — this is what the frontend receives.

**Generate CBDT JSON** (`POST /v2/clients/{id}/itr/{year}/generate-cbdt-json`):
1. `generate_client_cbdt_json_v2` (`client_itr_v2.py:196-294`) → `filing_gateway_v2.generate_cbdt_json(draft)` (`:1213-1255`) → `_generate_cbdt_json_itr1` (`:1258-1315`) for ITR-1.
2. Re-runs `compute_canonical_itr1` (step 2-4 above), then builds `filing_profile` / `property_profiles` / `tax_return_preparer` (`_filing_profile`, `_property_profiles`, `_itr1_tax_return_preparer` — all in `filing_gateway_v2.py`).
3. **CBDT validators**: `app.engine.validators.itr1.run_input_validation(typed_input)` then `run_calc_validation(typed_input, computation)` (`validators/itr1/runner.py:21,27`) — Category A/B/D rules; blocks with structured errors if `can_upload` is false.
4. `build_itr1_json(pipeline.computation, typed_input)` (`app/engine/itd/itr1.py:1536`) — assembles the official CBDT JSON.
5. `validate_itr1_json(official_json)` (`app/engine/itd/itr1_schema.py`) — validates against the official CBDT JSON Schema.
6. Inside the builder, `itr1["CreationInfo"]["Digest"] = _compute_digest(wrapped)` (`itd/itr1.py:2022`) → `app/engine/itd/common.py:63` → `app/eri/digest.py::compute_digest` (`:137`) — the single canonical Digest computation (env-scoped, see `Docs/ERI_UAT_EXPANSION_PLAN.md`).

### 3.3 Persistence

Single table `client_itr` (`app/db/models.py:126-147`), column `form_data: Text`. The live
v2 save path writes `draft.model_dump_json()` — the full canonical `ReturnDraft`, including
`schemaVersion`. Nothing in the shipped UI ever writes the old flat-blob shape to this
column anymore, even though the column itself doesn't enforce a schema.

---

## 4. ITR-4: verified end-to-end trace + `filing_gateway.py` reachability

Identical shape to ITR-1 (§3), with these ITR-4-specific facts confirmed:

| Action | Frontend call | Backend route | Handler |
|---|---|---|---|
| Compute | `itrV2.compute()` | `POST /v2/tax-summary/compute` | `compute_canonical_itr4` (`filing_gateway_v2.py`, imports `calculators.itr4.compute`) |
| Generate CBDT JSON | `itrV2.generate()` | `POST /v2/clients/{id}/itr/{year}/generate-cbdt-json` | `_generate_cbdt_json_itr4`, imports `itd.itr4.build_itr4_json` |
| Direct Submit | `filingSubmitApi.submit()` | `POST /api/v1/filing/{id}/{ay}/{itr}/submit` | routes through `filing_orchestrator.produce_itd_json`, `form in {"ITR-1","ITR-4"}` branch only |

**`app/engine/filing_gateway.py` is confirmed unreachable for a normal ITR-4 flow.** Its own
ITR-4 branch (`filing_gateway.py:197-208`) doesn't even attempt computation any more — it
immediately raises `FilingGatewayError("ITR-4 official CBDT JSON is generated by the v2
canonical pipeline...")`. The functions that *would* build a legacy ITR-4 JSON
(`_build_itr4_official_json`, `_build_itr4_input_from_flat`, `_itr4_builder_kwargs`) no
longer exist in the file at all (confirmed by grep — zero matches) — they were genuinely
deleted in Phase 7, unlike the ITR-1 functions (§0).

**Full reachability chain for `filing_gateway.py`'s remaining ITR-1 code**
(`generate_filing_artifact`, `_build_itr1_official_json`, `_build_itr1_input_from_flat`,
`_validate_itr1_cross_fields`):
- Its only non-test caller is `app/engine/filing_orchestrator.py:142`, inside the `else`
  branch that only executes `if form not in {"ITR-1", "ITR-4"}` (`filing_orchestrator.py:95`).
- Every live router that calls into `produce_itd_json` (`filing.py`, `json_exporter.py`)
  normalizes `itr_type` to ITR-1/ITR-4 *before* the call, via `_normalize_form()`
  (`filing.py:52-61`), rejecting anything else with a 422.
- **Net effect: the legacy-gateway branch inside `filing_orchestrator.py` cannot be reached
  by any live route today, for any form** — not just ITR-1/ITR-4. ITR-2/ITR-3 support isn't
  actually wired to it either; nothing currently drives an ITR-2/ITR-3 request into
  `produce_itd_json` at all. ITR-2/ITR-3 today run through a **third, unrelated path**:
  `app/routers/tax.py::_compute_itr2_from_flat_payload` (a flat, non-`ReturnDraft` payload
  mapper), which is what actually backs the currently-shipped (non-Direct-Submit-capable)
  ITR-2 UI flow.
- Test-only callers (kept intentionally as regression coverage per the plan doc, confirmed
  accurate): `tests/test_112a_unification.py`, `tests/test_integration_routers.py`,
  `tests/test_itr1_filing_gateway_profile.py`, `tests/test_itr1_golden_suite.py`.

**Implication for ITR-2/ITR-3 planning:** the legacy `filing_gateway.py` is *not* a live
fallback path to build on for ITR-2/ITR-3, despite `filing_orchestrator.py`'s branch
suggesting otherwise. It is fully dead code with no live caller. Building ITR-2/ITR-3
support means extending `filing_gateway_v2.py`'s dispatch (adding
`compute_canonical_itr2`/`_generate_cbdt_json_itr2` etc.), mirroring exactly what was done
for ITR-4 — never routing through `filing_gateway.py`.

---

## 5. Type-3 Direct Submit: full pipeline + persistence

### 5.1 Frontend

`handleDirectSubmit` (`ITRComputationPage.tsx:689-735`): guard to ITR-1/ITR-4 → confirm
dialog → save draft → `filingSubmitApi.submit(clientId, ay, itrForm, 'LATER')` → 2-second
poll loop via `filingSubmitApi.getJobStatus` until `completed`/`failed`. Verification mode
is **hardcoded to `LATER`** for this button — the OTP-supply endpoint
(`/api/v1/filing/jobs/{job_id}/otp`) exists and works, but isn't wired into this call
sequence (it backs a not-yet-built Aadhaar-OTP/Bank-EVC UI path).

### 5.2 Backend: `submit_via_portal` (`app/routers/filing.py:169-247`)

1. Reject if `ERI_MODE != "type3"` (501).
2. Resolve client (ownership-scoped), require `client.portal_password` set.
3. `export_itd_json_file(...)` (`app/eri/type3/json_exporter.py:37-83`) → loads the saved
   draft (requiring `schemaVersion` for ITR-1) → `produce_itd_json(...)`
   (`filing_orchestrator.py:42-170`) → for ITR-1/ITR-4, calls `filing_gateway_v2.generate_cbdt_json`
   (the exact same v2 chain as §3/§4) → writes the deterministic JSON file atomically.
4. `upsert_filing_record(...)` — creates/updates a `FilingRecord` row (`status="queued"`).
5. Creates a `FilingJob` row (`status="queued"`), commits.
6. `enqueue_filing_job(job.id)` — `asyncio.Queue.put_nowait` on an **in-process, in-memory
   queue** (not DB-polled) owned by `app.filing_automation.worker`.
7. Returns `{job_id, filing_id, status: "queued"}`.

### 5.3 The independent filing worker (`app/filing_automation/worker.py`)

Started/stopped in `app/main.py`'s lifespan, as a task **entirely separate** from the
Prefill/AIS/TIS/26AS import worker (`app.automation.job_worker`) — confirmed by the module's
own docstring and by the two being wholly different tables/queues (`FilingJob` vs
`AutomationJob`, no FK relationship between them).

`_run_filing_job(job_id)`: loads the job + decrypts the client's portal password → opens a
**visible (headed) browser** (`interactive=True` — deliberate, so the operator can watch and
intervene) → taxpayer login via `app.automation.auth.login_itd` → hands off to
`PortalUploader.upload(...)` (`app/filing_automation/uploader.py`) → on success, updates
`FilingRecord.status` to `submitted` or `verified`, `FilingJob.status="completed"`; on
failure, both marked `failed` with a friendly error message; always logs out and closes the
browser context in `finally`.

**Code-accuracy flag (not from any doc — found during this audit):** the worker opens a DB
session, unconditionally closes it, then reuses that closed session object for several
`log_filing_action_by_id(db=db, ...)` calls later in the same function
(`worker.py:113,140-141,224-297`). Audit-log writes are best-effort and swallow exceptions,
so this can only silently degrade audit logging — it never affects `FilingRecord`/`FilingJob`
state (those use their own fresh sessions). Worth a dedicated look, not urgent.

### 5.4 The uploader (`app/filing_automation/uploader.py`, 1632 lines)

Navigates directly to the File-ITR page, selects AY/filing-type/section/form via the
portal's `mat-select` dropdowns, uploads the JSON via a hidden `input[type=file]`, scans for
known portal-rejection error text before and after submit, extracts the ARN via regex from
the confirmation page, then runs e-verify per the requested mode:
- `LATER` (what Direct Submit always uses) → clicks "Verify Later", returns `"pending"`.
  Acknowledgement download is **not** attempted on this path (only triggered when
  `everify == "verified"`).
- `AADHAAR`/`BANK_EVC` → drives the OTP/EVC flow via the `otp_callback`, returns `"verified"`
  → triggers an in-band acknowledgement PDF download.

OTP values are never logged — only the prompt string reaches `log(...)`; the OTP itself
lives only in an in-memory future (`uploader.py:_otp_waiters`).

### 5.5 Standalone acknowledgement fetch

A **second, independent** code path — `app/eri/type3/ack_downloader.py` — logs in fresh,
finds the filed return by assessment-year text match (no ARN needed up front), downloads the
PDF, and the router (`POST .../acknowledgement/fetch`) persists it onto `FilingRecord` and
streams it back. This is what the frontend's "Fetch Acknowledgement" button actually uses —
not the in-band path from §5.4, since Direct Submit's hardcoded `LATER` mode never reaches
that branch.

### 5.6 Database models (`app/db/models.py`)

| Table | Key columns | Status lifecycle |
|---|---|---|
| `filing_record` (unique on client+AY+form) | `eri_mode`, `eri_environment`, `status`, `json_path`, `acknowledgement_number`, `everify_status`, `acknowledgement_path`, `portal_result`, `error_message` | `generated` → `queued` → `running` → `submitted`/`verified` or `failed`; `acknowledged` set independently by the ack-fetch endpoint |
| `filing_job` | `filing_record_id` (FK), `verification_mode`, `json_path`, `status`, `current_step`, `progress_pct`, `result` | `queued` → `running` → `completed`/`failed` |
| `imported_document` (unique on client+AY+doc-type) | `document_type` (`"generated_itr"` for this flow), `source="generated"` | written once per generation by `filing_orchestrator._persist_generated_json` |
| `audit_log` | `action`, `outcome`, `itd_code`, `message` (hard-truncated to 1000 chars) | append-only; writes are best-effort and never break the filing flow |

`AutomationJob` (the import-worker's table) is confirmed structurally and operationally
separate — no FK to either filing table, driven by a different worker task.

---

## 6. What this means for ITR-2 / ITR-3 (the template to follow)

This is the exact shape any new form's production-readiness must match — not a plan for
ITR-2/3 yet (that's `Docs/ERI_UAT_EXPANSION_PLAN.md`'s job), just the checklist this audit
confirms every already-production form satisfies:

1. **One canonical mapper** per form: `ReturnDraft → FormInput`, living in its own
   `app/engine/draft_to_itr{N}_input.py`, importing shared-head helpers from
   `draft_to_itr1_input.py` rather than reimplementing them (confirmed convention:
   `draft_to_itr4_input.py` does exactly this).
2. **`filing_gateway_v2.py`'s dispatch extended**, never `filing_gateway.py` (confirmed
   dead/unreachable, §4) — add `compute_canonical_itr{N}` and `_generate_cbdt_json_itr{N}`
   following the ITR-4 pattern exactly.
3. **CBDT validators actually wired in** before JSON emission — `run_input_validation` +
   `run_calc_validation`, Category A blocking, called from `_generate_cbdt_json_itr{N}`.
4. **The frontend hits only `/v2/*` and `/api/v1/filing/*`** — no new legacy-style route, no
   new flat-blob mapper. `itrV2.ts` and `filingSubmit.ts` are the only API client modules a
   new form's frontend work should extend.
5. **Persistence via the single `ClientITR.form_data` column**, serialized `ReturnDraft`
   JSON with `schemaVersion` — no parallel table, no parallel shape.
6. **Digest and CreationInfo always via `app/eri/digest.py`** — no per-form reimplementation.
7. **Type-3 submission is form-agnostic already** — `filing.py`'s `_normalize_form` currently
   hard-restricts to ITR-1/ITR-4; extending it to ITR-2/3 is a one-line allowlist change once
   the v2 pipeline supports those forms, not new uploader/worker code.

**One open gap this audit surfaced that's separate from ITR-2/3 scope** (flagging so it
isn't lost, not fixing here): `filing_date`/`due_date` are never actually populated
anywhere in the v2 canonical pipeline for ITR-1 or ITR-4 today — confirmed absent from
`draft_to_itr1_input.py`'s `ITR1Input(...)` construction, `draft_to_itr4_input.py` sets
`filing_date` from the wrong source field (`personal.dateOfBirth`) with a stale "gateway
sets it" comment, and `filing_gateway_v2.py` has zero references to either field. Per the
calculator's own docstring, this means 234A/B/C/F interest is silently skipped on every
v2-generated JSON, and it's untested (`test_filing_gateway_v2.py` has zero references to
either field).
