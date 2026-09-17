# ITR-3 Schedule-by-Schedule Implementation Tracker

**This is the single source of truth for the ITR-3 schedule-wise implementation push.** Updated after every schedule is completed end-to-end. Supersedes `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` and `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phase 8 for status purposes (their PDF↔schema reconciliation table, reproduced below, remains valid reference material and is not being redone).

## Ground rules for this push

1. **One schedule at a time, in official PDF print order** (the table below). No skipping ahead.
2. For each schedule: read the official ITR-3 form PDF section + the official JSON schema block, then implement **every mandatory and optional field** — schema → draft mapper → calculator → ITD JSON builder. A schedule is not "done" until data flows for real from a `ReturnDraft` through to schema-valid JSON, not just until the builder can serialize a hand-constructed object.
3. **Validators are explicitly out of scope for this entire push.** `app/engine/validators/itr3/` is not touched until every schedule below is done and a separate validator pass begins. Do not add, remove, or edit any ITR-3 validator rule while working through this tracker.
4. **ITR-3 only.** If a defect is found in already-shipped ITR-1/ITR-2/ITR-4 code along the way, it is flagged in the "Cross-form issues found, not fixed" log at the bottom of this document and the user is asked explicitly before anything in those forms' code is touched. Never edit ITR-1/ITR-2/ITR-4 code as a side effect of ITR-3 work.
5. Frontend work in this push is limited to what's needed for real end-to-end data flow (wiring a field to the draft, fixing a mapping bug) — **not** visual/UX redesign, which is tracked separately (`Docs/FRONTEND_UI_UX_REDESIGN_AUDIT_AY2026_27.md`) and deliberately deferred.
6. After each schedule: run the full regression suite, confirm no new failures beyond the established baseline, update this tracker's status table and add a dated "Fix status" note under that schedule, then commit.

## Status legend

| Symbol | Meaning |
|---|---|
| ⬜ | Not started this push |
| 🔍 | In progress — being verified/implemented now |
| ✅ | Done — every mandatory + optional field verified end-to-end (mapper → calculator → builder → schema-valid JSON), confirmed against the official PDF and schema directly |
| ⛔ | Blocked — needs a decision (e.g. a cross-form fix, an architectural piece like a depreciation engine) before it can be closed |

## Schedule order and status

Reusing the verified, PDF-line-cited, schema-cross-referenced table from `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` §0A (confirmed accurate as reference by a dedicated re-audit — see `Docs/ITR3_CURRENT_STATUS_AY2026_27.md` §6). The "Prior finding" column carries forward what the 2026-09-17 status investigation (`Docs/ITR3_CURRENT_STATUS_AY2026_27.md`) already established — it is a starting hypothesis for this push to verify, not a conclusion to trust blindly.

| # | PDF section | Schema block(s) | REQ? | Status | Prior finding (to verify, not trust) |
|---:|---|---|:---:|:---:|---|
| 1 | Personal Information (A1–A18) | `PartA_GEN1` | REQ | ✅ | Closed 2026-09-17 — see fix log |
| 2 | Filing Status (A19) | `PartA_GEN1` + `PartA_GEN2` | REQ | ⬜ | Believed core-wired |
| 3 | Audit Information (A20) | `PartA_GEN2.AuditInfo` | REQ | ⬜ | Believed core-wired |
| 4 | Nature of Business or Profession | `PartA_GEN2.NatOfBus` | REQ | ⬜ | Believed core-wired |
| 5 | Part A-BS (Balance Sheet) | `PARTA_BS` | REQ | ⬜ | Totals real when workspace supplied; excluded from "complete" allow-list (unspecified defaulted fields remain) |
| 6 | Part A-Manufacturing Account | `ManufacturingAccount` | opt | ⬜ | Generic key-lookup passthrough, not individually typed |
| 7 | Part A-Trading Account | `TradingAccount` | opt | ⬜ | Same generic passthrough |
| 8 | Part A-P&L | `PARTA_PL` | REQ | ⬜ | Totals real; dozens of `DebitsToPL` line items hardcoded 0 |
| 9 | Part A-OI | `PARTA_OI` | opt (mandatory if 44AB-audited) | ⬜ | Schema/builder real (full passthrough); calculator reads only a few scalars, not the object; frontend missing method-of-accounting inputs |
| 10 | Part A-QD | `PARTA_QD` | opt (mandatory if 44AB-audited) | ⬜ | Builder/mapper real |
| 11 | (Schedules banner) | — | — | N/A | Documentary only, no JSON |
| 12 | Schedule S — Salary | `ScheduleS` | opt | ⬜ | Not independently verified this push |
| 13 | Schedule HP — House Property | `ScheduleHP` | opt | ⬜ | Not independently verified this push |
| 14 | Schedule BP — Business/Profession | `ITR3ScheduleBP` | REQ | ⬜ | Core real; several bridging rows hardcoded 0 by design (presumptive/44AD-AE, inter-head bridging not tracked) |
| 15 | Schedule DPM | `ScheduleDPM` | opt | ⬜ | Pure passthrough — **no block-of-assets depreciation engine exists anywhere in the backend** |
| 16 | Schedule DOA | `ScheduleDOA` | opt | ⬜ | Same — no depreciation engine |
| 17 | Schedule DEP | `ScheduleDEP` | opt | ⬜ | Same — no depreciation engine |
| 18 | Schedule DCG | `ScheduleDCG` | opt | ⬜ | Only `TotalDepreciation` read, for deemed-STCG figure |
| 19 | Schedule ESR | `ScheduleESR` | opt | ⬜ | Passthrough only, deduction not reflected in tax |
| 20 | Schedule CG | `ScheduleCGFor23` | opt | ⬜ | Core computation real; excluded from "complete" allow-list; dead fallback fn `_schedule_cg_for23` referenced but never defined |
| 21 | Schedule 112A | `Schedule112A` | opt | ⬜ | Real |
| 22 | Schedule 115AD | `Schedule115AD` | opt | ⬜ | Real (FII/FPI bucket, thin real-world use for ITR-3 individual/HUF filers) |
| 23 | Schedule VDA | `ScheduleVDA` | opt | ⬜ | Real |
| 24 | Schedule OS | `ScheduleOS` | opt | ⬜ | Not independently verified this push |
| 25 | Schedule CYLA | `ScheduleCYLA` | REQ | ⬜ | Real |
| 26 | Schedule BFLA | `ScheduleBFLA` | REQ | ⛔ | **Confirmed bug**: `BusProfExclSpecProf.IncBFLA` hardcoded to always-zero (`itr3.py:941`, both operands ×`Decimal("0")`). `bf_losses` never mapped from draft at all |
| 27 | Schedule CFL | `ScheduleCFL` | opt | ⛔ | Downstream of unmapped `bf_losses` — no ITR-3 return can currently carry forward/set off a prior-year loss |
| 28 | Schedule UD | `ITR3ScheduleUD` | opt | ⛔ | Broken at both layers: calculator hardcodes `unabsorbed_dep_setoff = 0` with a `# Simplified` comment; no draft mapper either |
| 29 | Schedule ICDS | `ScheduleICDS` | opt | ⬜ | Passthrough only |
| 30 | Schedule 10AA | `Schedule10AA` | opt | ⬜ | Deduction amount comes from generic Chapter VI-A breakdown, not this typed schedule |
| 31 | Schedule 80G | `Schedule80G` | opt | ⬜ | Frontend bug found: ARN field renders unconditionally, should be category-D-only |
| 32 | Schedule 80GGA | `Schedule80GGA` | opt | ⬜ | Not independently verified this push |
| 33 | Schedule 80GGC | `Schedule80GGC` | opt | ⬜ | Not independently verified this push |
| 34 | Schedule 80DD | `Schedule80DD` | opt | ⬜ | Frontend: disability-type dropdown collapses 10 named conditions to 2 |
| 35 | Schedule 80U | `Schedule80U` | opt | ⬜ | Not independently verified this push |
| 36 | Schedule RA | `Schedule80RA` | opt | ⬜ | Not independently verified this push |
| 37 | Schedule 80-IA | `Schedule80_IA` | opt | ⬜ | Deduction amount via generic breakdown, not this typed schedule |
| 38 | Schedule 80-IB | `Schedule80_IB` | opt | ⬜ | Same |
| 39 | Schedule 80-IE | `Schedule80_IC` | opt | ⬜ | Same; naming divergence (PDF "80-IE" = schema `Schedule80_IC`) already documented |
| 40 | Schedule VI-A | `ScheduleVIA` + sub-blocks | opt | ⬜ | Real; frontend: **Section 80CCH missing entirely** |
| 41 | Schedule AMT | `ScheduleAMT` | opt | ⬜ | Real |
| 42 | Schedule AMTC | `ScheduleAMTC` | opt | ⛔ | **Confirmed gap**: `amt_input`/prior-year AMT credit never mapped from draft — no ITR-3 return can claim brought-forward AMT credit |
| 43 | Schedule SPI | `ScheduleSPI` | opt | ⬜ | Real |
| 44 | Schedule SI | `ScheduleSI` | opt | ⬜ | Real |
| 45 | Schedule IF | `ScheduleIF` | opt | ⛔ | **Confirmed dead field**: draft's `partnerInFirmEntries` fully modeled, never read anywhere in `app/engine` |
| 46 | Schedule EI | `ScheduleEI` | opt | ⛔ | **Confirmed gap**: calculator + builder real; `agricultural_income`/`exempt_income` never mapped from draft. Frontend: agri-income threshold shown as ₹5,000 instead of ₹5,00,000 (100x) |
| 47 | Schedule PTI | `SchedulePTI` | opt | ⬜ | Partial — disclosure only, thin GTI integration |
| 48 | Schedule TPSA | `ScheduleTPSA` | opt | ⬜ | Schema/builder real; calculator never reads it (no tax computation at all) |
| 49 | Schedule FSI | `ScheduleFSI` | opt | ⬜ | Real (reused ITR-2 plumbing) |
| 50 | Schedule TR | `ScheduleTR1` | opt | ⬜ | Real |
| 51 | Schedule FA | `ScheduleFA` | opt | ⬜ | Real |
| 52 | Schedule 5A | `Schedule5A2014` | opt | ⬜ | Real |
| 53 | Schedule AL | `ScheduleAL` | opt | ⬜ | Real; ₹1cr threshold fix already confirmed correct (2026-09-14) |
| 54 | Schedule GST | `ScheduleGST` | opt | ⬜ | Passthrough disclosure only |
| 55 | ESOP | `ScheduleESOP` | opt | ⬜ | Real |
| 56 | Part B-TI | `PartB-TI` | REQ | ⬜ | Real |
| 57 | Part B-TTI | `PartB_TTI` | REQ | ⬜ | Real |
| 58 | TRP details | `TaxReturnPreparer` | opt | ⬜ | Not independently verified this push |
| 59 | Section 17 Tax Payments | `ScheduleIT`+`TDS1`+`TDS2`+`TDS3`+`TCS` | opt | ⬜ | Real (reused ITR-2 plumbing); frontend: `ITR3TaxPaymentEditor` tab is dead code (defined, never rendered) — needs fixing as part of this schedule's end-to-end close |
| 60 | Verification | `Verification` | REQ | ⬜ | Real |

**Schema-only blocks with no standalone PDF section** (`CreationInfo`, `Form_ITR3`, the 80C-family sub-blocks under Schedule VI-A) are closed alongside the phase that owns them (60 and 40 respectively) per §0B of the old plan doc — not tracked as separate rows here.

---

## Cross-form issues found, not fixed

Issues spotted in already-shipped ITR-1/ITR-2/ITR-4 code while working ITR-3, per the ground rule above — flagged here and to the user explicitly, never fixed as a side effect.

1. **ITR-2, live regression, not caused by this push**: `tests/test_draft_to_itr2_input.py::test_other_exempt_income_preserves_per_clause_classification` fails — `app/engine/draft_to_itr2_input.py:701` (`_map_exempt_income()`) reads `row.natureOfIncome`, but `ExemptIncomeEntry` (`app/schemas/return_draft.py:1200-1204`) has no such attribute — it has `category`/`subCategory`/`description`/`grossAmount` instead. This was already surfaced during the ITR-3 status investigation (`Docs/ITR3_CURRENT_STATUS_AY2026_27.md` §2) and confirmed present in the full regression run after this push's Schedule 1 fix (still exactly this one extra failure, nothing new). **Not fixed — awaiting explicit go-ahead to touch ITR-2 code.**

---

## Schedule-by-schedule fix log

### Schedule 1 — Personal Information (A1–A18) — ✅ closed 2026-09-17

**What was found** (comparing `Docs/ITR3_FIELD_BY_FIELD_GUIDE_1_PERSONAL_INFO_TO_HP.md` §1 and the official schema's `PersonalInfo`/`AlternateAddress` definitions directly against `app/engine/itd/itr3.py::_parta_gen1`):
- A6a (building/village name) and A7a (road/street) were captured nowhere — the builder hardcoded `ResidenceName`/`RoadOrStreet` to `""` unconditionally.
- A16 (Aadhaar) was read by `_parta_gen1`'s signature but never actually sourced from `ITR3Input` in the canonical path — always absent from real filings.
- A17's office/residence phone (schema `Address.Phone`) had no code path at all; its secondary-mobile columns (`CountryCodeMobileNoSec`/`MobileNoSec`) were hardcoded to `0`/`0` unconditionally.
- A18's secondary email (`EmailAddressSec`) was never emitted.
- **A5b–A13b, the "Secondary Address"**: `SecondaryAdd` was hardcoded `"N"` regardless of the taxpayer's actual declaration, and — the most serious finding — whenever `secondary_add == "Y"` was forced via a non-canonical caller, `AlternateAddress` was populated as a **literal copy of the primary address**, not real secondary-address data. There was no source data path for a genuine alternate address anywhere in the pipeline.
- Root cause for all of the above: `app/schemas/itr3.py`'s `ITR3Input` had no fields at all for any of this (only the eight primary-address scalars), and `app/engine/draft_to_itr3_input.py` never read the corresponding `ReturnDraft.personal.*` fields — even though every one of those fields (`aadhaar`, `secondaryEmail`, `secondaryMobile`(+country code), `landlineStdCode`/`landlinePhoneNo`, `residenceName`, `roadOrStreet`, `secondaryAddressDifferent`, `alternateAddress`) already existed on the shared `PersonalInfo` draft model. **No frontend/draft-schema changes were needed** — this was purely a backend mapper + builder gap.

**What was fixed:**
- `app/schemas/itr3.py`: added `residence_name`, `road_or_street`, `zip_code`, `mobile_country_code`, `assessee_aadhaar`, `office_phone_std_code`, `office_phone_no`, `secondary_mobile_country_code`, `secondary_mobile_no`, `secondary_email`, `secondary_address_different`, and the nine `alternate_*` fields to `ITR3Input`.
- `app/engine/draft_to_itr3_input.py`: mapped all of the above from `draft.personal.*`/`draft.personal.alternateAddress.*` (soft/optional, matching the mapper's existing style for this section — hard requiredness stays the builder's job, as it already was for the original 8 fields).
- `app/engine/itd/itr3.py`: `_parta_gen1()`/`build_itr3_json()` rewritten to emit every field for real: `ResidenceName`/`RoadOrStreet` from sourced data; `AadhaarCardNo` from the typed input; `Address.Phone` emitted only when a real STD code + number exist; secondary mobile/email sourced for real; `SecondaryAdd` reflects the taxpayer's actual flag; `AlternateAddress` built from genuinely distinct secondary-address data, never copied from the primary address. Added a fail-closed check: if `secondary_address_different` is True but the required alternate-address fields weren't actually sourced, `build_itr3_json` now raises rather than silently omitting or fabricating the block. `AlternateAddress.PinCode`/`ZipCode` are only emitted when real (neither is schema-required — no fabricated PIN default was introduced for the new code, unlike the pre-existing primary-address fallback which was left as dead-path legacy scaffolding, see below).
- Deliberately **not** touched: the primary `Address`'s existing fabricated-default kwargs (`locality: str = "Locality"`, `pin_code` falling back to `110001`, etc.) on `build_itr3_json`'s legacy (`typed_input=None`) call path — every real canonical caller already passes `typed_input`, which hard-requires these via the pre-existing `required_identity` check before `_parta_gen1` is ever reached, so this fallback code is effectively dead in production; changing pin_code's required-ness policy (e.g. to support a foreign-only ZIP-code address) is a separate design decision, not evidenced as broken today, and was left alone to keep this fix scoped to real field-completeness, not a required-ness policy change.

**Verification**: two new tests in `tests/test_itr3_canonical_foundation.py` — `test_itr3_personal_info_optional_fields_reach_typed_input_and_json` (every new field set on a realistic draft, asserted present in both `typed_input` and the emitted JSON, validated against the official `PersonalInfo` schema sub-definition directly via `jsonschema.Draft4Validator` — scoped to this schedule since the full document doesn't validate yet yet, pending Schedules 5/8/9/25/26/24 etc.) and `test_itr3_secondary_address_flag_without_data_fails_closed` (confirms the new fail-closed guard). Both confirmed genuinely failing pre-fix via `git stash`. Full combined regression (`test_itr1/2/3/4_*.py` + filing-gateway/AMT/CYLA/BFLA/capital-gains suites): 1313 passed, same 10 pre-existing baseline failures plus the one already-flagged, pre-existing, unrelated ITR-2 regression (see "Cross-form issues" above) — no new failures.
