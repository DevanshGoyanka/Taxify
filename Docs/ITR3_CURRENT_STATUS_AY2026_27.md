# ITR-3 Current Implementation Status (AY 2026-27)

**As of:** 2026-09-17, verified directly against live code, an empirical end-to-end run, and a full test-suite pass — not against either older planning document's own claims.
**Supersedes, for ITR-3 specifically:** `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` and `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phase 8, both of which have not been edited since 2026-09-14 and contain several claims now factually wrong (see §6). Those two documents' schedule-by-schedule phase breakdown and the PDF↔JSON-schema reconciliation table (Doc 1's §0A/§0B) remain useful *reference* material and are not being replaced — only their status claims are.
**Why this document exists:** four parallel research passes (a full re-read of both planning docs cross-checked against live code, a schedule-by-schedule code audit of the calculator/builder/validator/mapper layers, a reconciliation of the frontend field-coverage claims against an older correctness-focused audit, and a live empirical test of JSON generation against the real official schema) were run specifically to answer, with evidence rather than assumption, "what is actually true about ITR-3 today" before starting a schedule-by-schedule implementation push.

---

## 1. The practical answer

**If a real ITR-3 return were filed through this system today, it would fail before any network call to the ITD ever happens.**

Verified directly: a minimal-but-realistic `ITR3Input` (identity fields + one presumptive-44AD business, built the same way the project's own test suite constructs one) fails `generate_cbdt_json()` with:

```
ITR3PreparationIncompleteError: ITR-3 preparation is incomplete: 1991 official field paths have no typed source
```

raised by the new, strict, fail-closed completeness gate in `app/engine/itd/itr3_preparation.py`. Bypassing that gate and calling the builder + real schema validator directly still produces **75 concrete `required property` errors** against the actual official CBDT JSON schema, concentrated in Schedule OS (33), Part A-OI (18), Part A-BS (15), Schedule CYLA (6), Schedule BFLA (3). This is documented, expected, current-state behaviour — the project's own `test_itr3_generation_fails_closed_until_builder_is_schema_exact` test asserts exactly this failure for exactly this kind of minimal draft.

Separately and independently, filing is blocked at the router layer regardless: `app/routers/filing.py::_normalize_form()` accepts only `{"ITR-1", "ITR-2", "ITR-4"}` — ITR-3 is rejected with a 422 before any routing decision, for **both** Type-2 direct API submission and Type-3 portal automation. This is one gate stricter than ITR-2, which at least allows JSON generation/download through the Type-3 path. ITR-3 has never been exercised against a live ITD UAT endpoint (`validateItr`/`submitItr`) — confirmed via `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md`, which explicitly states ITR-2/ITR-3 "are not yet production-ready" and carries zero ITR-3 test-case mentions anywhere, unlike ITR-1/ITR-4's full live-trace records.

## 2. Scale, relative to the other three forms

| Form | Dedicated test count |
|---|---|
| ITR-1 | 253 |
| ITR-2 | 661 |
| **ITR-3** | **56** |
| ITR-4 | 194 |

ITR-3 has roughly 1/12th of ITR-2's test density and less than a quarter of ITR-1's or ITR-4's — by a wide margin the least mature of the four forms, and the test count alone corroborates every other finding below.

**Full combined regression** (`test_itr1_*.py`, `test_itr2_*.py`, `test_itr3_*.py`, `test_itr4_*.py` + the filing-gateway/AMT/CYLA/BFLA/capital-gains suites): **11 failed, 1311 passed** — one more than the established 10-failure AMT/AMTC/Schedule-FA/AL/5A baseline. The 11th, new failure is `tests/test_draft_to_itr2_input.py::test_other_exempt_income_preserves_per_clause_classification` — `ExemptIncomeEntry` has no `natureOfIncome` attribute; `app/engine/draft_to_itr2_input.py:701` reads a field that doesn't exist on `app/schemas/return_draft.py`'s `ExemptIncomeEntry` (which instead has `category`/`subCategory`/`description`/`grossAmount`). **This is a live ITR-2 bug, unrelated to ITR-3, and should be fixed as its own item** — it is not part of the known baseline and represents a currently-broken code path, not a test artifact.

## 3. What's genuinely wired end-to-end today (schema → calculator → builder → mapper, real arithmetic)

Schedule BP (core PGBP), CYLA, SI, SPI, VDA, 112A, Chapter VI-A (80C/80D/80DD/80U/loan schedules), FSI/TR1/FA/AL/5A/ESOP/IT (all via ITR-2's reused foreign-income and capital-gains plumbing), TDS1/TDS2/TDS3/TCS, Part A-GEN1/GEN2, Part B-TI, Part B-TTI, Verification, and Capital Gains core computation (STCG/LTCG/111A/112A classification, DCG integration).

The v2 pipeline scaffolding is real and current-generation, contradicting both planning docs' framing: `compute_canonical_itr3()` and `_generate_cbdt_json_itr3()` (`app/engine/filing_gateway_v2.py:2126-2172`) dispatch a genuine, complete lifecycle — `draft_to_itr3_input` → `run_itr3_input_validation` → `compute_itr3` → `run_itr3_calc_validation` → `build_itr3_json` → `require_complete_itr3_document()` → `validate_itr3_json()` — the same generation-pattern ITR-1/ITR-4 use, not a stub or an older/partial path. (Note: `compute_canonical()`'s own docstring at line 2153-2155 still says *"ITR-3 not yet supported by the v2 pipeline"* — stale in-code, not just stale documentation. `app/routers/client_itr_v2.py`'s `/pdf` statement-of-income route similarly still hard-blocks ITR-3 with a stale comment claiming "no canonical ReturnDraft compute pipeline yet" — also no longer true.)

## 4. What's partially wired — concrete, specific gaps

1. **Part A-BS / Part A-P&L**: totals real when a workspace is supplied, but dozens of individual line items (`Freight`, `ConsumptionOfStores`, `AuditFee`, `BadDebtDtls`, etc.) are hardcoded `0` in `_parta_pl()` (`app/engine/itd/itr3.py:469-503`). The codebase's own `itr3_preparation.py:16-18` deliberately excludes `PARTA_BS`, `PARTA_PL`, and `ScheduleCGFor23` from its "complete source" allow-list, explicitly because "their current builders still contain unsupported/defaulted fields."
2. **No depreciation engine exists anywhere in the backend.** Schedule DPM/DOA/DEP/DCG are pure passthrough serializers. The calculator never reads `schedule_dpm`/`schedule_doa`/`schedule_dep` at all, and only reads `schedule_dcg.SummaryFromDeprSchCG.TotalDepreciation` for the deemed-STCG figure. Depreciation only affects tax through one opaque scalar (`BusinessIncome.depreciation_it_act`) with no code path deriving it from the rich DPM/DOA data — the two can silently disagree. `scheduleRegistry.ts` still marks all four `'missing'`, consistent with this.
3. **Schedule BFLA hardcoded-zero bug**: `app/engine/itd/itr3.py:941` — `"BusProfExclSpecProf": {"IncBFLA": item(value(cyla, "stcg20_remaining") * z, value(bfla, "biz_setoff") * z)}`. Both operands multiplied by `z = Decimal("0")` — always zero in the emitted JSON regardless of the actual figure. Looks like a leftover placeholder, not an intentional omission.
4. **Dead fallback function**: `app/engine/itd/itr3.py:1917` calls `_schedule_cg_for23(cg_data)` when `typed_input is None`, but that function is never defined or imported anywhere in the file — a latent `NameError`. Currently unreachable in production (the real gateway always passes `typed_input`) but should be removed or fixed, not left as a trap.
5. **10AA/80-IA/80-IB/80-IC/80RA deduction amounts** flow into tax only through a generic Chapter VI-A breakdown (`bd.get("80-IA")` etc.), not from the rich typed schedule objects that are faithfully serialized to JSON — the disclosure schedules and the actual tax-affecting deduction amount are two independent, unreconciled sources.
6. **Part A-OI**: builder is a full `model_dump` passthrough of `ITR3PartAOI` (real, once populated), but the calculator only reads a handful of scalar disallowance totals from it, not the object itself — and per the correctness audit, the frontend domain model defines `methodOfAcct`/`changeInAcctMethFlg`/`methodOfValClgStk` fields that have no input control anywhere, so they can never actually be populated by a real preparer regardless of backend readiness.

## 5. Entirely absent from real filings, despite the engine already being able to handle them correctly

These are the **highest-confidence, cheapest wins** for a schedule-by-schedule push — calculator and builder already work (verified by tests calling them directly with a hand-constructed typed input), but `app/engine/draft_to_itr3_input.py` never populates the corresponding field from a real user `ReturnDraft`, so no real filing ever reaches them. In three of the four cases, ITR-2's own mapper already solves the identical problem and the fix is porting, not designing from scratch.

- **Schedule IF (partner-in-firm / interest from firms)** — the draft has a fully modeled, UI-facing `partnerInFirmEntries` field (`app/schemas/return_draft.py:204-205,1719-1721`, form item A19(k)) that is never read anywhere in `app/engine` (confirmed by repo-wide grep). The single easiest fix on this list.
- **Schedule EI (agricultural / exempt income)** — calculator (`compute_agri`, with real partial-integration tax logic) and builder (`_schedule_ei()`) are both real; neither `agricultural_income` nor `exempt_income` is ever mapped from the draft, even though ITR-2's mapper fully consumes the identical `ExemptIncomeSchedule` field (`app/engine/draft_to_itr2_input.py:640-729`).
- **Schedule CFL/BFLA brought-forward losses** — `bf_losses` is never mapped from the draft's real `broughtForwardLossEntries` field, even though ITR-2's mapper does this (`app/engine/draft_to_itr2_input.py:619-636`). Practical effect: **no ITR-3 return can currently set off a prior year's brought-forward loss at all**, only current-year loss adjustment.
- **Schedule AMTC (AMT credit)** — `amt_input` is never mapped from the draft's real `AMTCreditEntry`/`creditsBroughtForward` field, even though ITR-2's mapper does this (`app/engine/draft_to_itr2_input.py:885`). Current-year AMT computation itself works (it's trigger-driven, not `amt_input`-dependent); no prior-year AMT credit can currently be claimed.
- **Schedule UD (unabsorbed depreciation)** — broken at *both* layers, not just the mapper: `app/engine/calculators/itr3.py:516-517` hardcodes `r.unabsorbed_dep_setoff = z` with a `# Simplified: set off against business income` comment, and there is no draft field for it either.

## 6. Validator coverage — thin, the thinnest layer in the pipeline

- `app/engine/validators/itr3/input_rules.py`: **7 rules** (ITR3-R001–R007) — business-income presence, non-negative advance/self-assessment tax/relief_89, date-format checks. No schedule-specific business rules.
- `app/engine/validators/itr3/calc_rules.py`: **3 rules** (ITR3-C001–C003) — non-negative GTI/TI/total-taxes-paid only.
- `app/engine/validators/itr3/parta_pl.py` (new, 126 lines): **4 real arithmetic-consistency checks** (TotCreditsToPL, PBIDTA, PBT, ProfitAfterTax chains), correctly wired into the mapper and raising `PartAPLArithmeticError` on contradiction — genuinely good, recent work, not reflected in either older planning doc.
- Total: **~14 explicit rules**, versus dozens in ITR-1/ITR-2's Category A/B/D validator suites. Doc 1's own §5 prescribes a proper 8-way disposition taxonomy (`IMPLEMENTED`/`STRUCTURALLY_GUARANTEED`/`CALCULATOR_ENFORCED`/`SCHEMA_ENFORCED`/`BUILDER_GUARANTEED`/`NOT_REPRESENTABLE`/`EXTERNAL_CHECK`/`PENDING`) intended to live in `app/engine/validators/itr3/official_rules_reference.py` — that file does not exist yet.

## 7. The frontend coverage claim needs a specific caveat before anyone relies on it

A separate, very recent commit (`82e0080`, co-authored by a concurrent agent) regenerated `frontend/src/domain/itr3CoverageManifest.ts` and reports, per `frontend/docs/itr3-coverage-gaps.md`: **2,936 official paths, 69 schedules, 0 missing mandatory paths.**

This is **not an empirical "does a working input control exist" check** — it's a naming-heuristic classifier. Most schedules are routed to a bespoke per-schedule Python function that can only ever output one of six dispositions (never "missing"), or to a blanket whole-schedule assignment (e.g. every path under `ScheduleCYLA`/`ScheduleBFLA`/`ScheduleAMT`/`ScheduleTDS1-3`/`ScheduleTCS` is labeled purely because the schedule *name* is in a hardcoded set, with zero per-field verification). Concrete, confirmed proof this matters: **`ITR3TaxPaymentEditor.tsx` (covering Schedule IT/TDS1-3/TCS) is imported and defined as UI tab 16 in `ITRComputationPage.tsx`, but there is no render branch for it — the switch statement jumps from tab 15 straight to tab 17.** It is dead code, introduced in the very commit that generated this "0 missing" report, and every one of its schedules is still marked as covered.

Real, empirically-confirmed frontend bugs from the older, correctness-focused `Docs/ITR3_FRONTEND_COMPREHENSIVE_FIELD_AUDIT.md` (written ~10.5 hours before the coverage-gaps commit, same day): Schedule CG's on-screen category letters are mismatched against their own field content (a scrip labeled "A5" is actually field-content "A2"); Schedule EI's agricultural-income threshold displays as ₹5,000 instead of ₹5,00,000 (a 100x error); Schedule 80G's ARN field renders unconditionally for every category when the form restricts it to one; Manufacturing and Trading Account totals double-count Direct Expenses; Schedule BP's core output figures (items 6, 10, 13, 34, 36, 37, 38, D) had zero computation anywhere as of that writing; Section 80CCH is missing entirely from Chapter VI-A.

**To be fair to the newer work**: it did close several of the older audit's biggest gaps for real — CYLA/BFLA, Part A-OI, AMT/AMTC, PTI, TPSA, AL/FA/ESOP, and the Special/Foreign schedules now have genuine, wired editor components that did not exist before, which is real progress, not just relabeling. But `frontend/src/domain/scheduleRegistry.ts` — the app's actual navigation source of truth — still marks 21 ITR-3-specific schedules `'missing'` (`PartA_GEN2`, `ITR3ScheduleBP`, `PARTA_BS`, `PARTA_PL`, `ManufacturingAccount`, `TradingAccount`, `ScheduleDPM/DOA/DEP/DCG`, `ScheduleESR`, `ITR3ScheduleUD`, `ScheduleICDS`, `Schedule10AA`, `Schedule80_IA/IB/IC`, `Schedule80RA`, `ScheduleIF`, `ScheduleTPSA`, `ScheduleGST`) even where editor components now exist for several of them — the registry itself hasn't been updated to reflect the new work, which is an internal frontend inconsistency worth fixing regardless of anything else.

**Bottom line for planning:** treat the coverage-gaps report as "every schema path has been triaged and assigned an intended owner" — a genuinely useful inventory — not as "every path has a verified, correctly-wired, form-matching input." Those are different claims, and the report cannot currently distinguish them.

## 8. Recommended next step

Before writing new schedule code, the two existing planning documents need to stop being a source of misinformation:

1. **Retire `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phase 8** to a single line pointing at Doc 1 and this document — it was never meant to carry ITR-3 detail and has drifted independently of Doc 1 since.
2. **Walk `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phases 1–14 (Personal Info through Schedule BP) and flip/annotate each against this document's findings** before adding new phases on top — several of them (Personal Info, Filing Status, Audit Info, Nature of Business, Balance Sheet, Part A-P&L totals) have real, dated commits behind them that the doc's own checkboxes don't reflect yet.
3. **Fix the four "engine-ready, mapper-missing" schedules first** (§5) — Schedule IF, Schedule EI, BFLA/CFL brought-forward losses, AMTC — since three of the four are direct ports of working ITR-2 code, they're the fastest way to close real, load-bearing gaps before tackling the harder architectural ones (a real depreciation engine, Part A-BS/P&L's remaining hardcoded line items, a genuine ITR-3 validator suite).
4. **Fix the unrelated ITR-2 regression** (`test_other_exempt_income_preserves_per_clause_classification`, §2) separately and promptly — it's a live, currently-broken code path unrelated to the ITR-3 push.
