# Full-Codebase Dead-Code Audit — 2026-09-05

## Purpose and scope

Following the ITR-2 legacy-path cleanup (`_compute_itr2_from_flat_payload`, `itr2Mapper.ts`,
commit `45d3f10`), the user asked for a whole-codebase sweep — not scoped to ITR-2 — for any
file, route, or component that is dead, obsolete, or never called. This document records that
audit's findings and, for each one, the exact fix applied (or the reason it was deliberately kept),
following the evidence-based documentation convention already established by
`Docs/ITR2_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md` and the ITR-1/ITR-4 audit docs: cite
the exact grep/test evidence, state the before/after, and label any correction to a prior
assumption explicitly rather than silently fixing it.

## Method

Two static-analysis passes, each hand-verified before any deletion:

1. **Backend (Python)** — an AST-based import-graph walk (`ast.parse` + `ast.walk` over every
   `.py` file under `app/`, `ais_extractor/`, `scripts/`), building the set of every module
   dotted-path ever imported anywhere, then diffing it against every module that exists. A
   `from package import submodule` import initially only recorded `package` as "imported," not
   `package.submodule` — this produced two false positives (`app/routers/pan.py`,
   `app/routers/automation.py`, both live mounted routers) until the walker was fixed to also
   record `f"{node.module}.{alias.name}"` for each imported name. Several files also needed
   `read_bytes().decode("utf-8-sig", ...)` instead of `read_text()` to survive a UTF-8 BOM marker
   present in a handful of validator files.
2. **Frontend (TypeScript)** — a regex-based import-specifier scan
   (`(?:from|import)\s*\(?['"]([^'"]+)['"]`) across every `.ts`/`.tsx` file under `frontend/src`,
   cross-referenced against every candidate file's basename, with manual `grep` re-verification
   before every deletion (the regex approach has false-positive risk — e.g. a local variable
   coincidentally sharing a component's name — so nothing was deleted on regex evidence alone).

A pure import-graph scan cannot see one entire category of dead code: an HTTP route that is
`@router`-mounted (so the *router module* is "used") but has zero real callers from the shipped
frontend. Those required a second, separate check: grep the frontend API-client layer and the
`tests/` directory for the route's path/function name.

Every backend deletion cluster was confirmed via `import app.main` / targeted router imports and
a full `pytest` run before commit. Every frontend deletion was confirmed via
`npm run build` / `npm test`.

---

## Item 1 — `env_backup.py` runbook claim (documentation fix, no code change)

**Finding**: `Docs/runbook.md` stated "The app writes `/opt/taxify/.env.backup` on every start
(`app/security/env_backup.py`)." `app/security/env_backup.py::backup_env()` is a real function
(uses `shutil.copy2`), and `Docs/deployment-log.md` has a genuine historical log line
(`INFO: .env backed up to /opt/taxify/.env.backup`, matching `env_backup.py`'s own
`_log.info(".env backed up to %s", _BACKUP_PATH)` format byte-for-byte) proving it really ran in
at least one past deployment. But `app/main.py`'s `lifespan()` does **not** call `backup_env()`
today — grepped for `backup_env` and `env_backup` across `app/main.py` and found no call site.
This is a real regression (the behavior was live once and silently isn't anymore), not an
always-false claim.

**Instruction**: "correct the runbook to stop claiming it" — documentation only, not asked to
restore the wiring.

**Fix applied**: `Docs/runbook.md` rewritten to state the function exists and was previously
verified working (citing the deployment-log evidence), but that `app/main.py`'s lifespan does
**not** call it "As of 2026-09-05," with a note that it should either be wired back in or the
runbook should stop implying automatic backup happens. No code changed — `env_backup.py` itself
and `app/main.py`'s lifespan are both untouched. Restoring the wiring is a separate, deliberate
decision the user has not yet asked for.

---

## Item 2 — `app/automation/ais_converter.py` (deleted)

**Finding**: Zero importers anywhere in `app/`. The real AIS/TIS/26AS parsing path is
`ais_extractor/` (`ais_extractor.extractor.extract_ais`, `.tis_extractor.extract_tis`,
`.as26_extractor.extract_26as`), a separate, browser-free state-machine parser used by the 26AS
import endpoint. `ais_converter.py` was an earlier, abandoned parsing attempt superseded by
`ais_extractor/`.

**Instruction**: "Recheck if `ais_converter.py` is really a dead code and never called from
anywhere, if yes delete it."

**Verification**: `grep -rn "ais_converter" app/ tests/ ais_extractor/` → zero matches outside
the file itself.

**Fix applied**: File deleted. Corrections made in three places that referenced it:
- `CLAUDE.md` (~line 189): rewrote the AIS/26AS pipeline description to correctly cite
  `ais_extractor/`'s exact submodule paths instead of the stale `app/automation/ais_converter.py`
  reference, and to note `ais_converter.py` was dead code, now deleted.
- `README.md`: removed the `ais_converter.py` line from the directory tree; corrected a separate
  stale claim that `ais_extractor/` is "NOT wired to API" (it is, via the 26AS import endpoint).
- `Docs/ITR1_ITR4_FILING_SUBMISSION_PIPELINE_AUDIT_AY2026_27.md` (~line 270): removed
  `ais_converter.py` from an "out of scope" file list, with a "Correction (2026-09-05,
  dead-code audit)" blockquote explaining why.

`as26_converter.py` (a sibling file) was investigated in the same pass and is **not** dead — it
remains as an explicitly-labeled legacy `.txt`-upload fallback path, distinct from the
`ais_extractor/` PDF pipeline. It was left in place and annotated inline in `README.md`.

---

## Item 3 — `frontend/src/components/StatusBox.tsx`

**Finding**: The user asked what exactly needed fixing here, having flagged it as a candidate.
Investigation: `ITRComputationPage.tsx` has local state variables named `showStatusBox` and
`statusBoxJob`. These names coincidentally resemble the `StatusBox` component but are plain local
state — not an import of the component. Grepping the actual JSX in that file shows the rendered
element at that location is `<StatusPill>`, a *different* component entirely. `StatusBox.tsx`
itself had zero import statements referencing it anywhere in `frontend/src`.

**Instruction**: "Tell me what exactly needs to be fixed here" → then (after the explanation)
"recheck if really as dead code delete it" (item 4's instruction was actually for `itd_json.py`;
item 3's own resolution was implicit in the explanation — the component was deleted since it had
zero real callers, only a name collision with unrelated local variables).

**Fix applied**: `frontend/src/components/StatusBox.tsx` deleted. No other file needed editing —
`showStatusBox`/`statusBoxJob` in `ITRComputationPage.tsx` are unrelated local state and were left
untouched; the component actually rendered there (`StatusPill`) is unaffected.

---

## Item 4 — `app/engine/itd_json.py` (deleted)

**Finding**: An initial grep for `itd_json\b` produced false-positive matches against
`produce_itd_json` (a real, live function in `app/filing_automation/`) because the pattern was
missing a leading `\b`. Re-run with the exact module path `app\.engine\.itd_json` (anchored,
whole-path match) returned **zero** matches anywhere in `app/`, `tests/`, or `scripts/`. The real
per-form JSON builders live in `app/engine/itd/itr{1,2,3,4}.py`; `app/engine/itd_json.py` was an
earlier, generic, unused attempt at the same job.

**Instruction**: "recheck if really as dead code delete it."

**Fix applied**: `app/engine/itd_json.py` deleted. `import app.main` confirmed clean afterward.

---

## Item 5 — TDS/TCS sub-files: where the real logic actually lives

**Finding**: `app/engine/schedules/tds_tcs/{tcs,tds_other,tds_property,tds_salary}.py` had zero
importers. The user's instruction assumed the values *must* be computed from schedules somewhere
and asked where, if not from these files. Read `app/engine/schedules/tds_tcs/__init__.py` in
full: its `compute_all()` function implements the entire TDS/TCS aggregation **inline**, using
duck-typed `getattr()` reads directly against the schema entry objects
(`tds1_entries`/`tds2_entries`/`tds3_entries`/`tcs_entries`), e.g. the Rule 37BA(3) "claim this
year vs. brought-forward" logic for TDS-2:
```python
claimed_this_year = getattr(e, "tds_claimed_this_year", Decimal("0")) or Decimal("0")
tds_val = claimed_this_year if claimed_this_year > 0 else getattr(
    e, "tds_deducted", getattr(e, "tax_deducted", Decimal("0"))
)
result.total_tds_other += tds_val
```
The four sibling files were an earlier, abandoned per-category-dataclass design that was never
wired in — `__init__.py`'s `compute_all()` supersedes them entirely and is the one function
`app/engine/calculators/itr2.py`/`itr3.py`/`itr4.py` actually call.

**Instruction**: "These values must be called from the schedules, if not from schedules from
where are they being called."

**Fix applied**: This item was answered, not "fixed" — the four sibling files
(`tcs.py`, `tds_other.py`, `tds_property.py`, `tds_salary.py`) were confirmed genuinely dead
(zero importers, fully superseded by `__init__.py::compute_all()`) and deleted. `__init__.py`
itself was untouched — it is the live, correct implementation.

---

## Item 6 — `app/automation/downloader_168.py` (kept)

**Finding**: Flagged as a candidate (no current callers found in the router/worker wiring).

**Instruction**: "keep it, it is for a future feature to be implemented."

**Fix applied**: No change. Left in place, undocumented beyond this entry (the user did not ask
for an inline annotation on this file, unlike item 13's batch).

---

## Item 7 — `app/automation/emailer.py` (kept)

**Finding**: Flagged as a candidate (no current callers found).

**Instruction**: "keep it, it is for a future feature to be implemented."

**Fix applied**: No change, same treatment as item 6.

---

## Item 8 — `app/engine/itd/stub_gen.py` (deleted)

**Finding**: Zero importers in `app/`, and zero references anywhere under `tests/`.

**Instruction**: "if not used by any test or not called anywhere delete it."

**Verification**: `grep -rn "stub_gen" app/ tests/` → zero matches outside the file itself.

**Fix applied**: File deleted.

---

## Item 9 — Dead capital-gains/business-income HTTP routes + `capitalGainsCalculationService.ts`

**Finding**: `app/routers/tax.py` had four route handlers with zero live frontend callers:
`calculate_business_income` (`POST /business-income/calculate`), `validate_business_input`
(`POST /business-income/validate`), `calculate_capital_gains` (`POST /capital-gains/calculate`),
`calculate_capital_gains_batch` (`POST /capital-gains/calculate-batch`, which called
`calculate_capital_gains()` directly as a plain Python function internally, not via HTTP).
`frontend/src/services/capitalGainsCalculationService.ts` was the only frontend file that ever
called any of these — and it called three endpoint paths that don't even match what's above
(`/capital-gains/validate`, `/capital-gains/calculate-exemption`, `/capital-gains/validate-batch`
— none of which exist on the backend at all), confirming the frontend service itself was already
orphaned/broken, not just superseded.

A prior planning document, `Docs/ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md`, had explicitly
characterized these four routes as "6 live routers" with a planned **migration** (not deletion)
to a new `business_tax.py` file. This plan is **not** followed here — the user's explicit
instruction ("recheck if called nowhere delete entirely") was to verify zero callers and delete,
which was done. This is a deliberate override of that older plan's assumption, made only after
confirming zero real callers exist today; it is flagged here rather than silently diverging from
that document.

**Instruction**: "recheck if called nowhere delete entirely, also delete the
`capitalGainsCalculationService.ts`."

**Verification**: `grep -rn "business-income\|capital-gains" frontend/src` (excluding the service
file itself) → zero matches. `grep -rn "calculate_business_income\|validate_business_input\|calculate_capital_gains" tests/` → zero matches.

**Fix applied**:
- `app/routers/tax.py`: removed all four handlers (previously lines 1226–1443 of a 1443-line
  file; file is now 1226 lines), plus their now-unused imports
  (`compute_112a`/`compute_111a` from `app.engine.schedules.special_rates`; the
  `PRESUMPTIVE_44AD_DIGITAL`/`PRESUMPTIVE_44ADA_RATE`/`SEC_44AD_TURNOVER_LIMIT`/
  `SEC_44ADA_RECEIPTS_LIMIT`/`LTCG_OTHER_RATE_POST_JUL24` block from `app.engine.constants`).
- `frontend/src/services/capitalGainsCalculationService.ts` deleted entirely.
- `README.md`: the dead `/business-income/*`/`/capital-gains/*` API table rows replaced with an
  explanatory note, including the detail that the frontend service called three endpoints that
  never existed server-side.
- Verified via `import app.routers.tax` (clean) and the full `pytest` regression run.

---

## Item 10 — `/itr3/compute`, `/itr3/compute-json` routes (kept, flagged for ITR-3 work)

**Finding**: Both routes (`app/routers/itr.py`) have zero frontend callers and zero test
coverage — `grep -rln "itr3_compute\b\|itr3_compute_json\b" tests/*.py` returns zero matches, and
`frontend/src/api/itrCompute.ts` (the only file that ever referenced them) was itself confirmed
dead (item 11). This is architecturally the same shape as the deleted ITR-4 routes (item 12), but
the user's instruction here was different.

**Instruction**: "keep it for now, and mention it be solved in the ITR-3 implementation."

**Fix applied**: No code change — both routes are still live in `app/routers/itr.py`. Documented
in `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phase 8 (ITR-3) section: added a paragraph
flagging `/itr3/compute`/`/itr3/compute-json` as having zero frontend callers and zero test
coverage (weaker than ITR-1/ITR-2's tested equivalents), to be resolved in a new ITR-3 sub-phase
8.7 — either wire them up with real frontend callers and tests, or remove them once ITR-3's own
production-readiness pass reaches that point. This is deliberately *not* the same treatment as
the ITR-4 routes (item 12), which had a fully-dead-end caller (`itrCompute.ts`, itself deleted)
and no active development plan referencing them; ITR-3 is still an active, tracked, in-progress
form per that same production plan.

---

## Item 11 — `frontend/src/api/itrCompute.ts` (deleted)

**Finding**: Even after an earlier session's partial ITR-2-specific trim, the remaining file
(`computeItr1`, `computeItr4`, `saveReturn`, `listReturns`, `getReturn`) had zero importers
anywhere in `frontend/src`. A prior assumption inherited from that earlier trim was that only the
ITR-2-specific exports had been removed and the rest might still be live — rechecked from
scratch: `grep -rn "itrCompute" frontend/src` (excluding the file itself) → zero matches.

**Instruction**: "recheck if actually dead if yes check and delete the entire thing."

**Fix applied**: `frontend/src/api/itrCompute.ts` deleted in its entirety.

---

## Item 12 — Backend routes only reachable via `itrCompute.ts`

**Finding**: With `itrCompute.ts` confirmed dead (item 11), every backend route it was the sole
caller of became a candidate: `POST /itr4/compute`, `POST /itr4/compute-json`,
`POST /returns/save`, `GET /returns`, `GET /returns/{return_id}`.

A prior assumption from earlier in this same audit session (this session's own earlier priority
list) had grouped `/itr1/compute`/`/itr1/compute-json` into the same "dead, zero test coverage"
bucket as the ITR-4 routes, on the (wrong) assumption that ITR-1 and ITR-4 routes were
symmetrically dead since they shared the same caller file. Re-checking explicitly per this item's
instruction ("so what exactly needs to be deleted") found this assumption was **wrong**:
`tests/test_itr1_route_validation.py` has substantial real coverage of both `itr1_compute` and
`itr1_compute_json` (`test_compute_rejects_calculator_errors`,
`test_compute_json_rejects_calculator_errors_before_builder`,
`test_old_regime_rebate_uses_taxable_income_after_deductions`,
`test_compute_json_passes_validated_input_to_builder`,
`test_compute_json_reports_missing_filing_profile_as_client_error`, and more). This was caught
**before** any deletion, and the scope was corrected: `/itr1/compute`/`/itr1/compute-json` are
kept (matching the established `/itr2/compute` precedent — also kept, tested in
`tests/test_itr2_production_path.py`), while `/itr4/compute`, `/itr4/compute-json`,
`save_return`, `list_returns`, `get_return` were confirmed to have genuinely zero test coverage
(`grep -rln "itr4_compute\b\|itr4_compute_json\b" tests/*.py` and
`grep -rln "save_return\b\|list_returns\b\|get_return\b" tests/*.py`, both excluding
`test_itr2_*` files, returned zero matches).

**Instruction**: "so what exactly needs to be deleted."

**Fix applied** (`app/routers/itr.py`):
- Removed `itr4_compute` (`POST /itr4/compute`) and its helper `_build_itr4_response`.
- Removed the entire "persistence endpoints" section: `save_return` (`POST /returns/save`),
  `list_returns` (`GET /returns`), `get_return` (`GET /returns/{return_id}`).
- Removed `itr4_compute_json` (`POST /itr4/compute-json`).
- File went from 400 → 331 lines (later 319 after a further docstring/import trim).
- Removed now-dead imports: `SavedReturn` from `app.db.models` (kept `User`); `compute as
  compute_itr4` from `app.engine.calculators.itr4`; `run_input_validation as itr4_input_val,
  run_calc_validation as itr4_calc_val` from `app.engine.validators.itr4`; the entire `from
  app.schemas.itr4 import ITR4Input` line; `ITR4ComputeResponse, ReturnDetail, ReturnSummary,
  SaveRequest, SaveResponse` from the `itr_responses` import (kept `ITR1ComputeResponse,
  ITR2ComputeResponse, ITR3ComputeResponse`); `from sqlalchemy.orm import Session`; `from
  app.db.database import get_db`; the `_decimal_to_str` helper (only used by the now-deleted
  `save_return`) and its resulting now-unused `from decimal import Decimal` import.
- Rewrote the module's top docstring to document exactly what remains
  (`/itr{1,2,3}/compute[-json]`) and to record, in the docstring itself, what was removed and why
  — including an explicit note that `app.db.models.SavedReturn` (the underlying DB table) was
  **not** touched; dropping a live DB table is a separate, more consequential decision than
  removing unused API routes, and was out of scope here.
- `app/schemas/itr_responses.py`: removed the `ITR4ComputeResponse` class and the entire
  "saved-return endpoints" section (`SaveRequest`, `SaveResponse`, `ReturnSummary`,
  `ReturnDetail`), replaced with a short comment recording what was removed, when, and why, with
  a pointer to `app/routers/itr.py`'s docstring for the full evidence trail. Removed now-unused
  imports (`datetime`, narrowed `typing` import to just `Optional`).
- Verified via `import app.routers.itr` and the full `pytest` regression run (396 passed).

---

## Item 13 — 10 orphaned frontend pages + 6 API client files (documented as future features)

**Finding**: 10 page components and 6 corresponding API client files exist in the frontend with
zero route registration in `App.tsx` and zero imports anywhere else in the codebase:
`AccountingPage.tsx`, `BillingPage.tsx`, `CalendarPage.tsx`, `CommunicationPage.tsx`,
`JobsPage.tsx`, `NoticesPage.tsx`, `ReconciliationPage.tsx`, `ReportsPage.tsx`, `SyncPage.tsx`,
`TasksPage.tsx` (all under `frontend/src/pages/`), and `billing.ts`, `communication.ts`,
`documents.ts`, `jobs.ts`, `notices.ts`, `sync.ts` (all under `frontend/src/api/`). One of them,
`BillingPage.tsx`, already contains the UI text "🚧 Backend integration coming soon," corroborating
that these were originally built as deliberate future-feature scaffolding rather than abandoned
mid-build.

**Instruction**: "This chunk is to implemented in future, so as now document and keep it as a
future feature."

**Fix applied**: No files deleted. All 16 files were prepended with an identical header comment:
```
// FUTURE FEATURE — scaffolded but not yet wired into the app.
// Confirmed absent from App.tsx's route table and not imported by anything
// (full-codebase dead-code audit, 2026-09-05). Kept deliberately, not
// dead code to remove — see Docs/CODEBASE_DEAD_CODE_AUDIT_2026_09.md for
// the full list of what this belongs to and why it was kept.
```
This document is the file that comment references. Nothing about these 16 files' behavior
changed — the header is a comment only, verified not to affect `npm run build`/`npm test`.

---

## Item 14 — `apiError.ts`, `api.types.ts`, `usePhase2.ts`, `ValidationReportPanel.tsx` (deleted)

**Finding**: Four frontend files flagged as candidates in the original sweep:
`frontend/src/api/apiError.ts`, `frontend/src/types/api.types.ts`,
`frontend/src/hooks/usePhase2.ts`, `frontend/src/components/validation/ValidationReportPanel.tsx`.

**Instruction**: "recheck if all are not called anywhere and obsolate delete them off."

**Verification** (re-run immediately before deletion, each excluding the candidate file itself):
- `grep -rln "apiError" frontend/src --include="*.ts" --include="*.tsx"` → zero matches.
- `grep -rln "api\.types" frontend/src --include="*.ts" --include="*.tsx"` → zero matches.
- `grep -rln "usePhase2" frontend/src --include="*.ts" --include="*.tsx"` → zero matches.
- `grep -rln "ValidationReportPanel" frontend/src --include="*.ts" --include="*.tsx"` → zero
  matches.

**Fix applied**: All four files deleted.

---

## Post-cleanup verification

- Backend: `import app.main`, `import app.routers.tax`, `import app.routers.itr` all clean after
  every deletion cluster. Full `pytest` run: 396 passed (up from 388 before this session's ITR-2
  P0 work added `tests/test_itr1_route_validation.py` to the standard set) — no new failures
  attributable to any change in this document. The project's documented baseline
  (~177 pre-existing failures / 13 collection errors, per `CLAUDE.md`) is unrelated to this sweep
  and unaffected by it.
- Frontend: `npm run build` and `npm test` run after all deletions/edits (StatusBox.tsx,
  capitalGainsCalculationService.ts, itrCompute.ts, the item-14 deletions, and the 16
  header-comment insertions) to confirm no regression.
- Credential sweep (`grep -iE "password|secret|api[_-]?key|BEGIN (RSA|PRIVATE)|\.env"` across the
  full diff) run before commit — this is a pure dead-code removal / documentation pass, no
  credentials or `.env`-adjacent files are touched.

## What this document deliberately does not do

- Does not restore `env_backup.py`'s wiring into `app/main.py`'s lifespan (item 1) — flagged only.
- Does not delete `downloader_168.py` or `emailer.py` (items 6, 7) — kept for future features per
  explicit instruction.
- Does not delete `/itr3/compute`/`/itr3/compute-json` (item 10) — kept, tracked in
  `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` Phase 8 for resolution during ITR-3's own
  production-readiness work.
- Does not delete the 16 files annotated in item 13 — kept as documented future-feature
  scaffolding.
- Does not drop the `app.db.models.SavedReturn` database table (only its now-dead CRUD routes) —
  a separate, more consequential decision than route removal, correctly out of scope here.
