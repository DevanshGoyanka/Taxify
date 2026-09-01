# ERI UAT Expansion — ITR-1 through ITR-7 (Type-2 + Type-3) — Phase Plan

**Status:** Active implementation tracker. No phase is implemented until explicitly approved.
Every phase below is committed only after the user tests and approves it, and this file is
updated immediately after each phase completes — status, files touched, verification result.
Nothing gets built that isn't listed here first.
**Date:** 2026-09-01
**Authority:** This file is the single source of truth for this workstream. It extends, and
must stay consistent with, the invariants already established in
`Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` (the original Type-2/Type-3 architecture) and
`Docs/ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` (the v2 canonical-pipeline pattern every
new form below follows).

## Goal

One correctly-stamped, CBDT-schema-and-rule-validated sample ITR JSON per form (ITR-1
through ITR-7), for each credential bundle that needs it, ready to email to
`erihelp@incometax.gov.in` for ITD's UAT sanity check / production enablement:

- **Type-2 UAT sample needed for:** ITR-2, 3, 4, 5, 6, 7
- **Type-3 UAT sample needed for:** ITR-2, 3, 5, 6, 7
- ITR-1 (Type-2 prod-enabled, Type-3 mailed) and ITR-4 (Type-3 mailed) are already done —
  not touched by this plan except to reuse as the working reference pattern.

Out of scope this round: portal-upload automation, e-verify, and the Type-2 API submit flow
for the new forms. Every line of code touched in `app/eri/`, `app/engine/itd/`,
`app/engine/validators/`, or the filing pipeline is production-grade and reused unchanged
later — nothing written only to "pass UAT."

## Master Phase Table

| # | Phase | Files touched | Status |
|---|---|---|---|
| 0 | Credential-switching mechanism — decision | `app/eri/config.py` (reverted, untouched) | ✅ **Decided 2026-09-01 — see below** |
| 1 | Generalize the UAT sanity-pack script | `scripts/eri_uat_sanity.py` (new, replaces `scripts/type3_uat_sanity.py`) | ✅ **Delivered 2026-09-01** |
| 2 | ITR-2 — extend `ReturnDraft` | `app/schemas/return_draft.py` | Not started |
| 3 | ITR-2 — canonical mapper | `app/engine/draft_to_itr2_input.py` (new) | Not started |
| 4 | ITR-2 — wire into v2 pipeline | `app/engine/filing_gateway_v2.py` | Not started |
| 5 | ITR-2 — complete CBDT validators | `app/engine/validators/itr2/input_rules.py`, `calc_rules.py` | Not started |
| 6 | ITR-2 — draft builder + sanity registration | `audit_itr_coverage.py`, `scripts/eri_uat_sanity.py` | Not started |
| 7 | ITR-3 — extend `ReturnDraft` | `app/schemas/return_draft.py` | Not started |
| 8 | ITR-3 — canonical mapper | `app/engine/draft_to_itr3_input.py` (new) | Not started |
| 9 | ITR-3 — wire into v2 pipeline | `app/engine/filing_gateway_v2.py` | Not started |
| 10 | ITR-3 — complete CBDT validators | `app/engine/validators/itr3/input_rules.py`, `calc_rules.py` | Not started |
| 11 | ITR-3 — draft builder + sanity registration | `audit_itr_coverage.py`, `scripts/eri_uat_sanity.py` | Not started |
| 12 | Generate + verify Type-3 UAT pack (ITR-2, ITR-3) | `downloads/type3_uat_sanity/` (output) | Not started |
| 13 | Generate + verify Type-2 UAT pack (ITR-2, 3, 4) | `downloads/type2_uat_sanity/` (output) | Not started |
| 14 | ITR-5 — full build (sub-phased on start) | `app/schemas/itr5.py` + calculator + builder + validators | Not started, scoped below |
| 15 | ITR-6 — full build (sub-phased on start) | `app/schemas/itr6.py` + calculator + builder + validators | Not started, scoped below |
| 16 | ITR-7 — full build (sub-phased on start) | `app/schemas/itr7.py` + calculator + builder + validators | Not started, scoped below |

Track A = Phases 1–13. Track B = Phases 14–16, started only after Track A is fully done
(confirmed sequencing).

---

## Phase 0 — Credential-switching mechanism (decided)

**The problem:** `get_eri_credentials()` (per `DUAL_MODE_ERI_INTEGRATION_PLAN.md` §3.1)
resolves whichever `(ERI_MODE, ERI_ENV)` is set in `.env` at process start — one bundle per
process. Phase 1's sanity script must produce a Type-2-UAT-stamped JSON and a
Type-3-UAT-stamped JSON for the same return. The reference plan never specifies how to do
that within one script run.

**Options considered and rejected:**
- *Edit `.env` between runs, flipping `ERI_MODE`/`ERI_ENV` by hand or by script.* Rejected —
  requires mutating the real, persisted `.env` file on the exact operation class that caused
  the Recovery Incident (`DUAL_MODE_ERI_INTEGRATION_PLAN.md`, "Recovery incident
  2026-08-19"), even done carefully.
- *A `use_eri_credentials()` context-manager override inside `app/eri/config.py`.* This was
  implemented and verified (27/27 ERI tests green) in an earlier pass of this session, then
  **reverted** — `app/eri/config.py` is back to its exact committed state, 0-line diff.
  Rejected because it adds a new mechanism to the single file the reference plan calls
  security-critical ("Critical invariant," no-placeholder-fallback), for a capability
  production code never needs — a live deployment is always single-`(mode,env)` for its
  entire process lifetime. Tooling concerns don't belong in the credential-resolution module.

**Decided approach — process-level environment variables, zero `app/eri/config.py` changes:**

```bash
ERI_MODE=type3 ERI_ENV=uat python scripts/eri_uat_sanity.py --forms ITR-2 ITR-3 --output-dir downloads/type3_uat_sanity
ERI_MODE=type2 ERI_ENV=uat python scripts/eri_uat_sanity.py --forms ITR-2 ITR-3 --output-dir downloads/type2_uat_sanity
```

Each mode's pack is generated by a fully separate OS process — no shared mutable state
between runs, no file written to or read back from disk beyond the existing `.env` (which is
never modified). The only code change this requires, and it lives entirely in Phase 1's new
script, not in `app/eri/config.py`: `load_dotenv(ROOT / ".env")` **without** `override=True`
(the current `scripts/type3_uat_sanity.py` uses `override=True`, which would clobber a
shell-set `ERI_MODE` back to whatever `.env` currently has). Dropping the override makes
shell-set variables win over the file — standard, unsurprising precedence — with no effect
on anything else the script reads.

**Delivered:** `app/eri/config.py` confirmed reverted to its committed state (`git diff`
0 lines; `tests/test_eri_creation_info_invariant.py`,
`tests/test_eri_routers.py`, `tests/test_eri_envelope.py` — 27 passed). Decided 2026-09-01.

---

## Phase 1 — Generalize the UAT sanity-pack script

**Goal:** One script, parameterized by mode and form list, replaces the ITR-1/ITR-4-only,
Type-3-only `scripts/type3_uat_sanity.py`.

**File:** `scripts/eri_uat_sanity.py` (new). `scripts/type3_uat_sanity.py` is deleted once
the new script's output is verified byte-for-byte equivalent for `--mode type3 --forms ITR-1
ITR-4` (regression check against the already-mailed ITR-1/ITR-4 packs).

**Changes from the current script:**
- CLI gains `--mode {type2,type3}` (default `type3`, matching current behavior).
- `_form_variants(form)` becomes a registry dict populated by each form's own module
  (Phase 6 registers ITR-2, Phase 11 registers ITR-3) instead of the current hardcoded
  `if form == "ITR-1": ... if form == "ITR-4": ...` chain.
- `load_dotenv(ROOT / ".env", override=True)` loses its `override=True` — becomes plain
  `load_dotenv(ROOT / ".env")` — per the Phase 0 decision, so a shell-set `ERI_MODE`/
  `ERI_ENV` wins over whatever `.env` has stored. The script itself does not read `--mode`
  into a variable it passes around for credential resolution; it trusts whatever
  `get_eri_credentials()` resolves from the process environment, and only uses `--mode` for
  labeling the manifest/output-dir naming and for asserting the resolved `creds.mode`
  actually matches what the operator asked for (fail loudly if `ERI_MODE` wasn't set to what
  `--mode` claims, so a forgotten env-var prefix can't silently generate the wrong bundle).
- Manifest gains a `mode` field per entry (currently implicit/always Type-3).
- Everything else — `_summarize_json`, `_digest_round_trips`, `_apply_current_filing_section`,
  manifest JSON shape — unchanged, since it's already correct and already validated.
- The form-variant registry (`_FORM_VARIANT_BUILDERS`, populated by
  `_load_builtin_registrations()`) replaces the old `if form == "ITR-1": ... elif form ==
  "ITR-4": ...` chain. ITR-1 and ITR-4 are registered today; Phases 6/11/14/15/16 each add
  one more `_register_form_variants(...)` call for their form, with zero changes to the
  generation loop itself.

**Delivered:**
- `scripts/eri_uat_sanity.py` (new) — mode-agnostic, form-registry-based, `--mode`
  asserted against the resolved `ERI_MODE`, `load_dotenv()` without `override=True` per the
  Phase 0 decision.
- `scripts/type3_uat_sanity.py` — deleted (`git rm`) after verifying its replacement is
  equivalent.
- `app/filing_automation/uploader.py` — one user-facing error string updated to reference
  `scripts/eri_uat_sanity.py` instead of the deleted script (was pointing operators at a
  file that no longer exists).

**Verification (all run 2026-09-01):**
1. **Content equivalence:** ran the old script and the new script (`--mode type3`) against
   the same `ITR-1`/`ITR-4` fixtures. Every generated file's Digest matched exactly between
   old and new, and a direct `diff` of the JSON files themselves (`ITR-1_default_80EEA...`,
   `ITR-4_44AD...`) showed **zero differences** — byte-for-byte identical output, confirming
   the refactor changed nothing about what gets generated.
2. **Type-2 mode works:** `ERI_MODE=type2 ERI_ENV=uat python scripts/eri_uat_sanity.py
   --mode type2` correctly resolved the Type-2 UAT bundle (`SW20014242`, 1344 iterations)
   and produced schema-and-rule-valid, digest-round-tripping JSON for both ITR-1 and ITR-4 —
   the first time a Type-2-stamped UAT sample has been generated for either form.
3. **Fail-loud guard works:** `--mode type2` with `ERI_MODE` left at `type3` in the process
   environment correctly refused to run (exit code 1, clear message) instead of silently
   generating a Type-3-stamped file into what would look like a Type-2 pack.
4. **Backend:** `python -c "import app.main"` — OK. `pytest
   tests/test_eri_creation_info_invariant.py tests/test_eri_routers.py
   tests/test_eri_envelope.py tests/test_itr1_calculator.py tests/test_itr4_calculator.py
   tests/test_filing_gateway_v2.py` — 71 passed.
5. **Frontend:** `npm run build` (`tsc -b && vite build`) — clean build, no type errors (this
   phase touched no frontend files; run per the standing testing requirement anyway).

---

## Phase 2 — ITR-2: extend `ReturnDraft`

**File:** `app/schemas/return_draft.py` (additive only — ITR-1/ITR-4 fields never touched,
same rule `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` Phase 1 used).

**What's added:** whatever `ITR2Input` (`app/schemas/itr2.py`, 655 lines) needs that
`ReturnDraft` doesn't already carry — read against the existing ITR-2 schema field-by-field
before writing. From the ITR-2 schema types already imported by ITR-3
(`CG112ATransaction`, `STCG111ATransaction`, `LandBuildingTransaction`, `VDATransaction`,
`FAEntry`, `SPISpecifiedPersonEntry`, `AMTEntry`, etc. — see `Docs/ARCHITECTURE.md` §5.1),
the likely additions are: full capital-gains transaction lists, VDA transactions, foreign
assets (FA), foreign source income (FSI), clubbing (SPI/5A), AMT entries. Exact field list
finalized when this phase starts (reading `app/schemas/itr2.py` line-by-line against the
current `ReturnDraft`, not guessed here).

**Tests:** 3 new cases in `tests/test_return_draft_schema.py` (empty ITR-2 draft validates;
additive fields round-trip; existing ITR-1/ITR-4 drafts still validate — same 3-case pattern
`ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` Phase 1 used).

## Phase 3 — ITR-2: canonical mapper

**File:** `app/engine/draft_to_itr2_input.py` (new), mirrors `app/engine/draft_to_itr4_input.py`
structure exactly: typed `ReturnDraft` → `ITR2Input`, no alias/flat-blob guessing.

**Tests:** `tests/test_draft_to_itr2_input.py` (new) — golden vectors: draft → `ITR2Input` →
`compute_itr2` (existing calculator, `app/engine/calculators/itr2.py`, unchanged).

## Phase 4 — ITR-2: wire into the v2 pipeline

**File:** `app/engine/filing_gateway_v2.py`. Extends the two dispatch points that currently
hardcode ITR-1/ITR-4 only:
- `compute_canonical()` (line ~1202): add `if draft.form == "ITR-2": return compute_canonical_itr2(draft)`.
- `generate_cbdt_json()` (line ~1248): add `if draft.form == "ITR-2": return _generate_cbdt_json_itr2(draft)`.
- New `compute_canonical_itr2()` and `_generate_cbdt_json_itr2()`, mirroring
  `compute_canonical_itr4`/`_generate_cbdt_json_itr4` exactly, including running
  `run_input_validation` + `run_calc_validation` from `app.engine.validators.itr2` before
  calling `build_itr2_json` (Phase 5 makes those calls meaningful).

**Tests:** `tests/test_filing_gateway_v2_itr2.py` (new) — parity/smoke tests mirroring
`tests/test_filing_gateway_v2_itr4.py`.

## Phase 5 — ITR-2: complete the CBDT validator suite

**The critical phase.** `app/engine/validators/itr2/input_rules.py` (365 lines) and
`calc_rules.py` (260 lines) today cover roughly 15% of what ITR-1's suite covers (4431
lines). Extended from `Reference Docs by CBDT & ITD/Official Validations/CBDT__e-Filing_ITR
2_Validation Rules_AY 2026-27_V1.0 (1).pdf`, following the exact `ValidationRule`/Category
A-B-D/`ValidationReport.can_upload`/`blocking_errors` pattern `itr1/input_rules.py` already
establishes — no new validation framework, this is filling in an existing one.

**Tests:** extend `tests/test_itr1_input_validation.py`'s ITR-2 analog (new
`tests/test_itr2_input_validation.py` if it doesn't already meaningfully exist) — one test
per new rule, known-good and known-bad cases, same pattern as the R145 tests added to ITR-1.

## Phase 6 — ITR-2: draft builder + sanity registration

**Files:** `build_full_itr2_draft()` added to `audit_itr_coverage.py` (mirrors
`build_full_itr1_draft`/`build_full_itr4_draft`), seeded from the real ITD test-data sheet
(`Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/Sunit Ramashankar
Goyanka Test Data 2026*.xlsx`) wherever it has ITR-2 scenarios, synthetic-but-maximal
elsewhere. Registered into Phase 1's `scripts/eri_uat_sanity.py` form-variant registry.

**Verification:** `python scripts/eri_uat_sanity.py --mode type3 --forms ITR-2` (and
`--mode type2`) produces a `generated` status with `digest_round_trips: true` and zero
Category-A validator findings.

## Phase 7–11 — ITR-3: same five phases, applied to ITR-3

Identical shape to Phases 2–6, for ITR-3:
- Phase 7: extend `ReturnDraft` for ITR-3-specific fields not already covered by the Phase 2
  additions (PGBP/business schedules per `app/engine/schedules/business.py`, balance sheet,
  partner-in-firm — `app/schemas/itr3.py` is only 263 lines, the smallest of the four
  existing schemas, so the gap analysis here is the fastest of the two Track A forms).
- Phase 8: `app/engine/draft_to_itr3_input.py` (new).
- Phase 9: wire `compute_canonical_itr3`/`_generate_cbdt_json_itr3` into
  `filing_gateway_v2.py`.
- Phase 10: **the largest single phase in Track A.** `app/engine/validators/itr3/` is 57
  lines total today — essentially unimplemented (a stub, not a partial suite like ITR-2's).
  Built from `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-filing_ITR-3_Validation
  Rules_V1.0_AY 26-27 (1).pdf` from near-zero, same pattern as Phase 5.
- Phase 11: `build_full_itr3_draft()` + sanity-script registration.

## Phase 12 — Generate + verify the Type-3 UAT pack (ITR-2, ITR-3)

Run `scripts/eri_uat_sanity.py --mode type3 --forms ITR-2 ITR-3 --output-dir
downloads/type3_uat_sanity`. Verify per the Verification section below. Manually upload one
generated JSON per form to the ITD Type-3 UAT portal as the control step (same control the
original DUAL_MODE plan's Phase 3 UAT required) before anything is mailed.

## Phase 13 — Generate + verify the Type-2 UAT pack (ITR-2, ITR-3, ITR-4)

Run `scripts/eri_uat_sanity.py --mode type2 --forms ITR-2 ITR-3 ITR-4 --output-dir
downloads/type2_uat_sanity`. ITR-4 is included here because Type-2 production enablement is
only done for ITR-1 so far — ITR-4 needs a Type-2 UAT sample too, even though its Type-3
sample already shipped. Same verification + manual-upload control as Phase 12, against the
Type-2 UAT portal.

---

## Phase 14 — ITR-5 (sub-phased once started; not before Track A is done)

Not started. Schema (`Official JSON Schema/ITR-5_2026_Main_V1.1.json`, 22,983 lines) and
validation rules (`Official Validations/CBDT_e-Filing_ITR-5_Validation Rules_V1.0_AY
26-27.pdf`, 1.36MB) are already in the repo. When this phase starts, it is broken into the
same six-step shape as Phases 2–6/7–11 (extend `ReturnDraft` or a new dedicated ITR-5 draft
shape if the field overlap with ITR-1's is too low to justify reuse — decided once the
schema is actually parsed — → schema → calculator → builder → validators → draft+sanity),
written out with exact file/function names at that time, not guessed now.

## Phase 15 — ITR-6 (sub-phased once started)

Not started. Schema (28,352 lines) + rules (1.26MB) in repo. Largest of the three remaining
forms — companies, MAT (§115JB), extensive corporate/audit schedules. Same six-step shape,
detailed when started.

## Phase 16 — ITR-7 (sub-phased once started)

Not started. Schema (15,702 lines) + rules (0.58MB) in repo. Smallest by raw size but a
different schedule shape (trusts/political parties/institutions — exemption and
application-of-income schedules, not business/PGBP). Same six-step shape, detailed when
started.

---

## Verification (applies to every phase touching computation or JSON generation)

- **Digest/SW_ID correctness:** `compute_digest(json) == stamped Digest` round-trip for
  every generated file, under both credential bundles.
- **Schema validity:** every generated JSON passes `jsonschema` validation against the
  matching official `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-N_...json`.
- **CBDT rule validity:** `run_input_validation`/`run_calc_validation` report
  `can_upload=True`, zero Category-A blocking errors.
- **Regression:** `pytest tests/test_itr1_*.py tests/test_itr4_*.py -v` stays green through
  every phase — ITR-1/ITR-4 must never regress while ITR-2/3/5/6/7 are built.
- **Manual control:** one generated JSON per form, Type-3 flavor, manually uploaded to the
  ITD UAT portal before that form's pack is emailed.

## Update discipline

After each phase: this file's Master Phase Table row flips to ✅ with a one-line result
summary and the commit hash; the phase's own section gains a **"Delivered"** block (files
actually touched, verification actually run, any deviation from what this section originally
said — same convention `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` uses throughout). No
phase after the current one starts until the user has tested and approved the one before it.
