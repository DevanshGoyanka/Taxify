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
   delegated to `app/eri/digest.py` (the single canonical Digest computation), which implements
   the ERI onboarding SOP exactly: iterated HMAC-SHA256 (keyed with the active `(ERI_MODE,
   ERI_ENV)` credential bundle's secret + iteration count, not a bare hash) over the sorted,
   whitespace-free JSON with `Digest` replaced by the placeholder `"-"`, then Base64-encoded.
   The total HMAC operation count is `iterations + 1`, **not** `iterations` — confirmed live
   against ITD's Type-2 UAT `validateItr` (an `iterations`-only digest was rejected with
   `Digest_Invalid`; `iterations + 1` was accepted). This was a real, previously-undetected
   off-by-one that made every digest this engine ever computed wrong, for every form and both
   ERI modes, until fixed 2026-09-04 — see `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §15 before
   touching this iteration count again; static cross-referencing against the SOP PDF alone (what
   originally "confirmed" the old, wrong count) does not prove correctness, only a live call does.
   Once the digest check itself passes, four independent `app/engine/itd/itr4.py` builder bugs —
   found by iterating live `validateItr` calls against ITD's Type-2 UAT, not by spec-reading —
   are common enough to hit on almost any real ITR-4 return: `ScheduleBP.PersumptiveInc44AE.
   IncChargeableUnderBus` must equal the 44AD+44ADA+44AE sum even with no 44AE business; the
   Form 10-IEA regime cascade (`FilingStatus`, Sl. No. A23) must default to `"N"` (not the
   schema-legal `"NA"`) and answer only one of its two mutually exclusive sub-branches at a time;
   `Schedule80C` must be omitted entirely (not an empty placeholder) when unclaimed, like every
   sibling deduction schedule; and `PersonalInfo.AlternateAddress`/`SecondaryAdd` must always be
   present, defaulting to the primary address when no distinct secondary address exists. See
   `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §16 for the full live-call evidence per bug.

Full verified end-to-end architecture reference (every route, the canonical pipeline,
Type-3 submission, DB persistence): `Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md`. ITR-2/
ITR-3's build-out onto the same complete-preparation contract is tracked phase-by-phase,
including a "Delivered" note per completed phase, in
`Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` — read that first for their current status.
ITR-2's pipeline is architecturally wired (that plan's Phases 1-7 delivered) but not yet
production-ready on correctness grounds — `Docs/ITR2_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`
is the living audit-fix-reaudit document tracking this separately (mirroring how the ITR-1/4
audit docs got those two forms production-ready), currently mid-cycle
(`C:\Users\Devansh\.claude\plans\zippy-juggling-sprout.md`). Its Schedule CG fix pass (2026-09-04)
is a useful precedent before touching `app/engine/itd/itr2.py`'s Schedule CG serializer again: a
finding described as "missing detail" turned out on re-verification to be a schema-blocking
wrong-field-name bug for land/building rows specifically (no test had ever exercised that path),
plus a genuine section 112(1)(a) indexed-cost-primacy defect found and deliberately left
documented-but-unfixed rather than rushed — don't assume a "missing mapping"-shaped finding in
this file is only a completeness gap without checking the exact schema field names/types first.

### v2 canonical pipeline (`ReturnDraft`)

The production compute/filing path for the frontend's single multi-form editor. One
canonical `ReturnDraft` (`app/schemas/return_draft.py`) covers every form. ITR-1 and ITR-4
use the complete-preparation lifecycle:

```
ReturnDraft → form-specific preparation
            → complete typed input → input validation
            → calculator → calculation validation
            → summary and CBDT JSON from the prepared input
            → official schema validation
```

Preparation includes the filing profile and eligibility, property profile, bank accounts,
verification and representative details, and optional TRP data. `app/engine/filing_gateway_v2.py`
is the single dispatch point: `compute_canonical(draft)` and `generate_cbdt_json(draft)` switch
on `draft.form` to the per-form preparers and serializers. JSON generation reuses the prepared
typed input; it must not perform late `model_copy(update={...})` enrichment or reconstruct
filing data from `ReturnDraft`. ITR-2/ITR-3 migration status is governed by the production
plan above; do not infer their readiness from this ITR-1/ITR-4 contract.

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

`filing.py`'s `POST /api/v1/filing/{client}/{ay}/{form}/submit` dispatches on the active
`ERI_MODE`: Type-3 queues a `FilingJob` for the existing Playwright automation worker (async,
polled via `GET /jobs/{job_id}`); Type-2 calls `_submit_via_type2_api()` synchronously (ordinary
HTTPS `validateItr`/`submitItr` calls, no job queue) and returns the ARN directly in the
response. Both branches share the same `produce_itd_json()` JSON-generation call — there is one
JSON-generation path for both modes, not two that could drift. Type-2's e-verification is
deliberately a separate step (`/api/v1/eri/generate-evc` + `/verify-evc`), since it needs the
taxpayer's live OTP consent, which can't happen inside the synchronous submit call.

### Browser automation

`app/automation/browser.py`'s `BrowserManager` is a singleton owning one Playwright browser
instance, run on its own dedicated event-loop thread (see the Windows event-loop note above).
`--workers 1` is mandatory in deployment for this reason (`SECURITY.md`). Downloaders
(`downloader*.py`) pull AIS/TIS/26AS PDFs from the ITD portal; `pdf_unlocker.py`,
`ais_converter.py`, `as26_converter.py` turn them into structured data. `ais_extractor/` is a
separate, browser-free PDF-parsing tool (state-machine parser) used by the 26AS import
endpoint's parsing step.

### ERI integration

`app/eri/` is the low-level ITD e-Return Intermediary API client: `envelope.py` (request
envelope — `{data, sign, eriUserId}`, `data` a Base64 JSON payload, not XML — + DSC signing +
password encryption), `digest.py`, `config.py` (credential/mode resolution — Type-2 API
gateway vs Type-3 offline utility, switched by `(ERI_MODE, ERI_ENV)`, validated at startup via
`assert_credentials_at_startup()`). `app/eri/type2/` holds the Type-2 REST API modules —
`login.py`, `add_client.py`, `everify.py`, `acknowledgement.py`, `prefill.py`, `client.py`
(generic dispatcher), and `validate.py`/`submit.py` (validateItr/submitItr — identical request
shape, differ only in `serviceName` and URL suffix). Every Type-2 call carries a mandatory
`timeStamp` field (IST, `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`) inside the signed payload and must
egress from an IP ITD has whitelisted — this is still required for both UAT and production;
do not trust any doc claiming otherwise without checking
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §2/§12 first, which corrects two earlier wrong
claims to that effect (one in this file's own history, one in `Docs/AWS_FREE_TIER_DEPLOYMENT.md`).

`envelope.py::parse_response_envelope()` treats a truthy `arnNumber` in the response as
overriding proof of success, checked *before* the usual raise-on-`messages[].type=="ERROR"`
logic — confirmed live: `submitItr` for a genuinely-filed ITR-4 return (ARN 116997020040926,
2026-09-04) carried an `ADHAAR_NOTIN_PROFILE_2026_004` ERROR-typed message that was a warning,
not a rejection, and the pre-fix code discarded the ARN by raising on it. Do not read this as
"ERROR-typed messages are generally non-fatal" — they remain fatal everywhere an `arnNumber` is
absent (login, addClient, everify, prefill all still raise correctly). `everify.py`'s
`generate_evc()`/`verify_evc()` must not put `eriUserId` inside the signed payload — only
`build_request_envelope()`'s own envelope-level field is expected; an in-payload copy is
rejected live with `EF40000`. `acknowledgement.py::get_acknowledgement()` locates the PDF by its
own `%PDF-`/`%%EOF` byte markers rather than trusting `Content-Type`, because ITD's live
`getAcknowledgement` intermittently (not always) returns a raw Java-serialized object wrapping
the real PDF, mislabeled `application/json` — see
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §18 for the full live-call evidence behind all three.

DSC signing (`envelope.py::sign_data()`, `ERI_DSC_SIGNING_MODE`) is Windows-only for the
`"token"` mode (`win32crypt`, physical USB hardware token via legacy CryptoAPI
`AT_KEYEXCHANGE`) — verified end-to-end against a live ITD Type-2 UAT call: a **detached** CMS
(PKCS#7) `SignedData` structure with the **full certificate chain** embedded (leaf + every
issuer up to the root, walked through the Windows CA/Root/AuthRoot stores — the token itself
only holds the leaf cert). Do not reintroduce an *attached* signature or a leaf-only chain; both
were the original (wrong) implementation and are now documented as incorrect in
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §12. CMS authenticated attributes
(`contentType`/`signingTime`/`messageDigest`/CMS-algorithm-protection, which BouncyCastle adds
by default) are deliberately *not* included — adding them via `win32crypt.CryptSignMessage`'s
`AuthAttr` parameter segfaults against this specific hardware CSP, and a live login call
confirmed ITD's verifier does not require them. The Linux deployment runs Type-3, which needs
no DSC signing at all.

`prefill.py`'s two-step flow (`request_prefill_otp()` then `get_prefill_data()`) has three
non-obvious, live-call-verified quirks that contradict `API_Prefill_v1.1.pdf`'s own request
tables — don't "fix" these back to match the spec PDF without re-verifying against a live call
first (see `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §13.2 for the full trace): (1)
`requestPrefillOTP`'s `serviceName` really is `"EriPrefill"`, not the spec's claimed
`"EriGetPrefill"`; (2) `getPrefill` needs the two IDs `requestPrefillOTP` returns
(`smsTransactionId`/`emailTransactionId`) sent as separate fields, not the spec's single
`"transactionId"`; (3) a schema-validation mismatch against `PreFillSchemaJSON_V6.5.json` is
logged, not raised — ITD's live server routinely sends `null` for inapplicable optional form
sections (audit reports, ESOP, carried-forward losses, etc.) where the published schema
requires an object, and most real taxpayers will have many such sections.

Type-2 egress runs through a WireGuard tunnel to a dedicated AWS jump-box
(`ERI-UAT-Server`/`13.204.49.125`, whitelisted with ITD for both UAT and production — a
completely different AWS account from the one `Docs/AWS_FREE_TIER_DEPLOYMENT.md` provisions for
hosting Taxify itself, never conflate the two) so signing can stay in-process on the local
machine while the connection still appears to originate from the whitelisted IP. The tunnel is
scoped tightly on both ends — the local client's `AllowedIPs` and the jump-box's iptables rules
both restrict traffic to exactly `43.239.60.30` (ITD's gateway), with an explicit catch-all
`DROP` on the jump-box since its baseline `FORWARD` policy is `ACCEPT`; nothing else can transit
this tunnel, and nothing else on either machine is affected by it. Full setup details, what was
verified, and what wasn't (an actual Type-2 API call through the tunnel is still pending) are in
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §14.

### CBDT/ITD source material

`Reference Docs by CBDT & ITD/` holds the official source documents CBDT rule citations and
validators are extracted from: `Official JSON Schema/` (per-form schema JSON, what
`app/engine/itd/itr{N}_schema.py` validates against), `Official Validations/` (the per-form
Validation Rules PDFs `app/engine/validators/itr{N}/` is built from), and `Official ITR
FORMS/` (the plain ITR-1 through ITR-7/-U/-V form PDFs). No taxpayer PII in this folder —
distinct from the `*Test Data*`/`*Test Scenario Sheet*` xlsx files elsewhere in the repo,
which do carry real operator PII and are `.gitignore`d, never committed.

A form's Validation Rules PDF typically catalogs several hundred rules (ITR-2's has 790), but
most are *not* meaningful additions to `app/engine/validators/itr{N}/`: many are consistency
checks between a CBDT dropdown-UI's sub-fields and their own displayed totals, or calculator
*formula* behavior (rate/classification logic) rather than input-shape validation — this repo
constructs official JSON programmatically from typed fields rather than summing a raw
editable UI, and the calculator already applies statutory caps/formulas internally, so a large
fraction of the catalog is either already structurally guaranteed or belongs in the calculator,
not a pre-compute validator. Before adding a rule, check three things: (1) is the field it
checks actually user-suppliable and not already capped/computed by the engine — grep the
relevant `app/engine/schedules/` module for whether it even reads that field, since some
fields (e.g. `ITR2Input.cf_losses`, most of `ScheduleSIEntry.deductions`) are wired into the
schema but never consumed by the calculator at all; (2) does the Pydantic schema itself
already reject the bad state via a `@model_validator` — write the known-bad test case *first*,
because if it can't even construct, the rule is dead before it ships (found twice: a
zero-ownership-share HP rule, a 115BB deduction rule); (3) is there an existing rule elsewhere
in the same file already covering it via a different, less obvious path. `input_rules.py` is
for genuine pre-compute gates, not a transcription of the PDF. ITR-2's validator build-out is
tracked rule-by-rule (implemented vs. structurally-covered vs. genuinely out of scope, each
cited by its official rule number) in `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` §Phase 5.

The three official source-document types check *different* things, and passing one says nothing
about the others: `Official JSON Schema/` only verifies type/required/min-max/pattern/enum shape;
`Official Validations/` (the rules PDFs) verify business-rule consistency of already-computed
values; only `Official ITR FORMS/` (the plain gazetted form PDFs, Parts A–D) shows the actual
arithmetic sequence a value is supposed to go through (e.g. Part D's D1→D17-style tax-computation
chain) — a JSON field can be schema-valid and pass every rule in the Validation Rules PDF while
still holding the *wrong number*, if the ITD builder maps the wrong calculator field into it.
This class of bug is real and has happened: the official schema's own `description` for a JSON
field does not necessarily match what a same/similarly-named internal calculator variable holds
— `ITR{N}_TaxComputation.NetTaxLiability` is documented as "Balance Tax After Relief" (pre-
interest/fees) but was wired to the calculator's `net_tax_liability`, which is a *different,
larger* quantity (the fully-final total, interest and fees included) that only happens to share
the name. Always check the schema's `description` field for a JSON key before assuming a
similarly-named calculator field is the right source: the two vocabularies are independently
chosen and only coincidentally overlap.

When transcribing a Validation Rules PDF for a cross-reference audit, save the transcription as a
permanent file next to that form's validators (e.g.
`app/engine/validators/itr4/official_rules_reference.py`) rather than a scratch file, so a future
audit pass doesn't have to re-read the PDF from scratch. Rule IDs inside a form's validators
should be unique and namespaced by what they check: `input_rules.py`'s CBDT-numbered pre-compute
gates use `ITR{N}-R###` (tracking the PDF's own numbering where a clean 1:1 mapping exists);
`calc_rules.py`'s post-computation arithmetic/cross-schedule-consistency checks are *not*
CBDT-numbered rules and must not share that namespace — ITR-4's `calc_rules.py` uses
`ITR{N}-C###` for exactly this reason, after a duplicate-ID audit found ~90 accidental collisions
between the two files' independently-sequenced numbering.

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
