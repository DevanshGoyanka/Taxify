# Taxify ITR-2 AY 2026–27 Frontend and Serialization Audit

**Audit type:** Read-only frontend and filing-pipeline audit  
**Assessment year:** AY 2026–27  
**Scope:** Frontend capture, canonical `ReturnDraft`, preparation, CBDT/ITD JSON serialization, and official-form coverage  
**Excluded:** Validators and validator-related working-tree changes  
**Status:** Not production-ready for complete real-world ITR-2 filing

> **Progress update (2026-09-04)**: this audit has moved from read-only findings-only into the
> same iterative audit-fix-reaudit cycle ITR-1/ITR-4's own audit docs used, per
> `C:\Users\Devansh\.claude\plans\zippy-juggling-sprout.md`'s Phase 1. §3.2's capital-gains
> serialization item is now fixed and re-verified (land/building rows, section 50C/50CA deeming,
> the generic "other assets" bucket for the remaining 10 `CGAssetType` categories) — see §3.1's
> and §3.2's own "Re-verified"/"Fix status" blockquotes for the full evidence trail, including one
> newly-found P0 (the section 112(1)(a) indexed-cost-primacy defect, deliberately deferred, not
> silently left broken). Schedule OS, TDS/TCS ownership, filing-profile completeness, and every
> other item below remain open — the overall "not production-ready" status is unchanged pending
> those.

## Executive conclusion

Taxify has broad ITR-2 frontend coverage and a substantial canonical data model, but it should not yet be considered production-ready for preparing or filing all AY 2026–27 ITR-2 returns.

The principal risk is the gap between:

1. a field existing in a TypeScript or Pydantic model;
2. a field being rendered and editable in the frontend;
3. that field being included in the canonical preparation path;
4. the calculator consuming it correctly; and
5. the official CBDT/ITD JSON serializer emitting it in the correct schedule and classification.

Several fields pass the first two stages but fail at later stages. A schema-valid JSON document is therefore not sufficient evidence of filing correctness.

The highest-priority areas are:

- Schedule 115AD and complete capital-gains serialization;
- Schedule OS category-by-category serialization;
- TDS-2, TDS-3, and TCS ownership/credit handling;
- filing-profile and Part A-GEN completeness;
- detailed Schedule S and Schedule HP capture;
- Schedule FA and foreign-income disclosures;
- AMT, AMTC, CFL, and loss reconciliation;
- exempt-income and deduction detail; and
- exact monetary representation and serialization.

---

## 1. Methodology and evidence

### Reviewed

- AY 2026–27 official ITR-2 JSON schema;
- official ITR-2 PDF;
- applicable ITR-2 form and tax-rule requirements;
- canonical frontend `ReturnDraft` model;
- React/TypeScript filing and schedule editors;
- canonical preparation and serializer path;
- legacy `frontend/src/api/itr2Mapper.ts` path;
- CBDT JSON schedule construction;
- backend monetary types and frontend money handling; and
- frontend production-build integrity.

### Explicitly excluded

Validators were excluded from this audit. The following pre-existing or unrelated working-tree changes were not assessed as part of the frontend/serialization findings:

```text
M  app/engine/validators/itr2/input_rules.py
M  tests/test_itr2_input_validation.py
?? Docs/ITR2_CBDT_VALIDATION_RULE_MATRIX.md
?? scripts/generate_itr2_rule_matrix.py
```

### Evidence paths

Representative evidence is cited using repository paths and line regions. Exact line numbers may move as the repository changes.

- Canonical model: `app/schemas/return_draft.py`
- Live ITR-2 serializer: `app/engine/itd/itr2.py`
- Legacy mapper: `frontend/src/api/itr2Mapper.ts`
- Personal information UI: `frontend/src/components/PersonalInfoTab.tsx`
- ITR-2 schedule workspace: `frontend/src/components/itr2/ITR2SchedulesWorkspace.tsx`
- Schedule OS UI: `frontend/src/components/othersources/ScheduleOSWorkspace.tsx`

---

## 2. Architecture assessment

### 2.1 Canonical v2 representation

The canonical model in `app/schemas/return_draft.py` contains dedicated structures for salary, house property, capital gains, other sources, exempt income, deductions, losses, SI, FSI, TR, FA, SPI, PTI, AMT, AL, Schedule 5A, ESOP, TDS/TCS, and tax challans.

Representative definitions include:

```text
return_draft.py:626      CapitalGainsSchedule
return_draft.py:725      ScheduleSIEntry
return_draft.py:744      ForeignSourceIncomeEntry
return_draft.py:758      ForeignTaxReliefEntry
return_draft.py:771      ForeignAssetEntry
return_draft.py:1238     Schedule80GGAEntry
return_draft.py:1250     Schedule80GGCEntry
return_draft.py:1315     TCS ownership fields
return_draft.py:1349     Taxes
return_draft.py:1586     capitalGainsSchedule
return_draft.py:1601     foreignSourceIncome
return_draft.py:1603     foreignAssets
return_draft.py:1606     amt
return_draft.py:1609     esopDeferrals
```

This is the correct architectural direction, but the presence of a typed model does not establish complete downstream support.

### 2.2 Legacy flat mapper

`frontend/src/api/itr2Mapper.ts` defines a substantially smaller `ITR2FormPayload` and assembles only a partial backend payload. It exposes simplified values such as:

```text
grossSalary
perquisitesValue
profitsInLieuOfSalary
hraExemptAmount
houseProperties
savingsBankInterest
fixedDepositInterest
familyPensionReceived
dividendIncome
cgTransactions
cg112aScrips
vdaTransactions
deductions
tds1Entries
tds2Entries
tcsEntries
taxPaymentEntries
```

It does not represent the breadth of the canonical model and drops substantial official detail. Any route still using it is not equivalent to the canonical v2 path.

**Severity: High**

**Required action:** establish one supported ITR-2 path. Remove, disable, or strictly adapt the legacy mapper to `ReturnDraft`; do not maintain two semantically different filing representations.

---

# 3. Critical findings

## 3.1 Schedule 115AD is not emitted as a distinct official schedule

### Evidence

The serializer registers:

```text
ScheduleCGFor23
Schedule112A
ScheduleVDA
```

in `app/engine/itd/itr2.py` around lines 1643–1669. The capital-gains serializer contains a block named `NRISecur115AD`, but it is a zero-valued generic placeholder within Schedule CG rather than a complete dedicated Schedule 115AD mapping.

`_schedule_112a()` begins around line 789 and serializes `cg_112a_scrips`; it does not provide a complete independent 115AD representation.

### Impact

Applicable non-resident securities or units under section 115AD may be:

- placed in the wrong schedule;
- emitted as zero-valued placeholder data; or
- omitted from the generated return.

### Severity

**Critical**

### Remediation

- Obtain the exact AY 2026–27 schema structures for the 115AD data.
- Add a dedicated canonical input type.
- Add a dedicated conditional frontend editor.
- Map every official field, including security/unit classification, consideration, cost, STT status, loss, and relevant non-resident details.
- Add schema and fixture tests for NRI 115AD securities, units, losses, and DTAA cases.

> **Re-verified (2026-09-04): scope narrowed, not yet fixed.** Cross-referenced against the
> official schema (`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_V1.1
> (2).json`) and `tmp/cbdt_rules/CBDT__e-Filing_ITR 2_Validation Rules_AY 2026-27_V1.0
> (1).txt` (rules #994, #495): `NRISecur115AD` (STCG) and `NRISaleOfEquityShareUs112A` (LTCG,
> the schema's "Schedule 115AD(1)(iii) proviso") are **genuinely and correctly** for FII/
> non-resident 115AD-specific securities, not a mislabeled generic bucket — the official
> ITR-2 form's own Schedule CG item 4/6 confirms this ("For NON-RESIDENT- from sale of
> securities... by an FII as per section 115AD"). `app/schemas/itr2.py`'s `CGAssetType` enum
> has no way to flag a transaction as this specific FII/115AD case (residency status alone is
> insufficient — 115AD is FII-specific, narrower than general non-resident), so these fields
> genuinely cannot be populated with today's schema and are correctly left at their zero
> placeholder rather than guessed at. **What §3.2's re-verification below did fix**: the
> non-115AD "everything else" gap this finding partly overlapped with — see §3.2.

---

## 3.2 Generic capital-gains rows are captured but not fully mapped

### Evidence

The canonical model contains `CapitalGainsSchedule` at `return_draft.py:626`. `_schedule_cg()` begins around `itr2.py:590` and explicitly handles only selected categories, including land/building and a narrow 111A path:

```python
if tx.asset_type.value in (
    "listed_equity_111a",
    "equity_oriented_fund_111a",
):
```

The serializer also emits zero-valued or placeholder structures for multiple categories, including:

```text
NRISecur115AD
SaleOnOtherAssets
SaleOfEquityShareUs112A
NRISaleOfEquityShareUs112A
NRISaleofForeignAsset
SaleofAssetNADtls
```

### Potentially affected categories

- land/building STCG and LTCG detail;
- listed securities outside the narrow 111A path;
- mutual funds and units;
- foreign assets;
- unlisted equity;
- other capital assets;
- section 50CA and deemed-consideration cases;
- non-resident classifications;
- DTAA-rate capital gains;
- buyback-related capital losses;
- exemptions under sections 54, 54B, 54EC, 54F, and 115F; and
- current-year and brought-forward capital-loss set-off.

### Loss and sign risk

The serializer calculates gains using expressions such as:

```python
gain = tx.full_consideration - tx.cost_of_acquisition - tx.expenditure_on_transfer
```

but uses `max(0, ...)` in other paths, including the 112A summary. This creates a risk that a loss becomes zero or is placed in a positive-income field instead of entering the loss matrix.

### Severity

**Critical**

### Remediation

Create a verified mapping matrix from every canonical capital-gains category to the exact official Schedule CG field. A populated category must either serialize fully or cause an explicit unsupported-case error before JSON generation. Do not silently emit zero placeholders for populated data.

> **Fix status (2026-09-04): land/building fixed and verified; generic "other assets" mapping
> still pending.** Re-investigating this finding's "land/building STCG and LTCG detail" item
> turned up a more severe, previously-unknown defect than originally described, plus two
> smaller related ones — all now fixed. The other 10 non-land/building, non-111A/112A
> `CGAssetType` categories (`unlisted_shares`, `listed_security`, `debt_mutual_fund`,
> `specified_mutual_fund_50aa`, `market_linked_debenture_50aa`, `bonds_debentures`,
> `depreciable_asset`, `jewellery`, `foreign_asset`, `other`) remain genuinely unmapped — see
> "Still pending" below.
>
> **Bug found #1 (schema-blocking — every land/building transaction was undeliverable)**:
> `_cg_land_building_row()` (`app/engine/itd/itr2.py`, old single shared function) emitted an
> entirely different, wrong key set for `SaleofLandBuildDtls` rows —
> `FullValueConsdRecvUnqshr`/a nested `DeductSec48` object/`BalanceCG`/`CapgainonAssets` (which
> is actually the shape for the unquoted-shares/other-assets block, §3.2's still-pending item,
> not land/building at all). The real schema (confirmed against
> `ShortTermCapGainFor23.SaleofLandBuild.SaleofLandBuildDtls` and
> `LongTermCapGain23.SaleofLandBuild.SaleofLandBuildDtls`) uses flat fields —
> `FullConsideration`/`AquisitCost`/`ImproveCost`(STCG)/`TotalDedn`/`Balance`/
> `STCGonImmvblPrprty`(STCG)/`LTCGonImmvblPrprty`(LTCG) — plus LTCG-only nested blocks
> (`CostOfImprovements`, `ExemptionOrDednUs54`) neither present nor named the same in the old
> code. `additionalProperties: false` means this would have been outright rejected by ITD's
> schema validator (or Taxify's own `validate_itr2_json()`) for *any* return with a land/building
> capital gain — confirmed no test anywhere exercised this path (`grep` for `land_building` across
> every ITR-2 test file returned zero hits before this fix).
>
> **Bug found #2 (arithmetic double-counting)**: for LTCG rows, the old code computed
> `cost = asset.acquisition_cost + asset.indexed_acquisition_cost` (summing non-indexed and
> indexed cost together) for the `gain`/`BalanceCG` figure, while separately computing
> `DeductSec48.AquisitCost` as *either* the non-indexed *or* indexed figure (a ternary, not a
> sum) — meaning the row's own displayed `TotalDedn` and `BalanceCG` could never actually
> reconcile (`BalanceCG` used a higher, double-counted deduction than what `TotalDedn` itself
> displayed). Confirmed the calculator's own total (`compute_ltcg` in
> `app/engine/schedules/capital_gains.py`) was *not* similarly double-counted — it correctly used
> `indexed_acquisition_cost or acquisition_cost` (fallback, not addition) — so the aggregate tax
> liability was never wrong, only the (unreachable, per bug #1) row-level detail.
>
> **Bug found #3 (missing plumbing, not just a formula bug)**: `STCGResult`/`LTCGResult`
> (`capital_gains.py`) had no field to carry the classified land/building `CGAsset` list through
> to the serializer at all — `_schedule_cg()`'s `getattr(stcg, "land_building", [])` always fell
> back to its empty-list default, so `SaleofLandBuildDtls` was **always empty**, even when
> land/building transactions existed and correctly contributed to the aggregate total. Fixed by
> adding a `land_building: list` field to both dataclasses, populated by `compute_stcg()`/
> `compute_ltcg()` from the same list already passed to them for `land_gain` (previously computed
> and discarded).
>
> **New capability added while fixing this: section 50C stamp-duty-value deeming.** Per the
> official form's own item 1(a)(iii): "in case (stamp value) does not exceed 1.10 times
> (consideration), take this figure as (consideration), or else take (stamp value)." This was
> entirely unimplemented — `CGAsset` (the calculator-internal dataclass) had no
> `stamp_duty_value` field at all, even though `CGTransaction` (the canonical schema) already
> captured it. Added `CGAsset.stamp_duty_value`, wired it through both construction sites
> (`app/engine/calculators/itr2.py` and `capital_gains.py`'s own `_classify()`), and added
> `deemed_consideration_50c()` (`capital_gains.py`), used consistently in both `compute_stcg()`'s
> and `compute_ltcg()`'s `land_gain` aggregate *and* the per-row serializer, so the schedule
> detail and the tax total can never disagree on which consideration figure was used.
>
> **New finding, deliberately NOT fixed here (documented, not silently left broken)**:
> `compute_ltcg()`'s `land_gain` formula prefers the *indexed* cost over the non-indexed cost
> when both are supplied (`indexed_acquisition_cost or acquisition_cost`) for the figure used in
> the **primary** declared LTCG. Per the official form's Schedule CG Part B item 1 (confirmed via
> `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf`, extracted text saved
> alongside it as `ITR-2-2026-Eng_extracted_text.txt`), the **primary** declared gain ("1c",
> flowing into `B1e`/`B1g`/the actual tax total) is explicitly computed from the **non-indexed**
> cost only; the indexed-cost figure ("1ca") is used *exclusively* for a separate section
> 112(1)(a) second-proviso tax comparison ("for the purpose of computing eiB") that protects
> resident taxpayers who acquired property before 23-Jul-2024 from paying *more* tax than the old
> 20%-with-indexation regime would have required — it is never meant to directly replace the
> primary gain figure. Using indexed cost as primary when it's *higher* than the non-indexed cost
> (the normal case, since indexation tracks inflation) understates the declared gain and,
> potentially, the tax owed. This is locked in by an existing test
> (`tests/test_standalone_cg_schedule.py::test_compute_land_building_long_term_uses_indexed_cost`)
> that encodes the same (likely incorrect) expectation, not derived independently from the
> statutory formula. **Deliberately not changed in this pass**: correctly fixing this requires
> implementing the full section 112(1)(a) dual computation (both tax figures, the
> "excess amount to be ignored" comparison) — the schema fields for it
> (`AquisitCostIndex`/`TotalDednForEiB`/`BalanceForEiB`/`TaxSec1121aiiB`/`TaxSec1121a`/
> `ExcessAmtSec1121a`, all schema-optional) are named but intentionally left unpopulated by the
> new serializer rather than guessed at under time pressure in the same pass as three other
> fixes. Flagged as a new, separate P0 item — see the remediation plan update below.
>
> **Tests**: `tests/test_itr2_itd_builder.py::test_land_building_stcg_and_ltcg_rows_are_schema_valid_with_correct_fields`
> and `::test_land_building_applies_section_50c_stamp_duty_deeming`, both validating the full
> generated document against the real official JSON schema (`Draft4Validator`), not just
> asserting individual field values — this is exactly the check that would have caught bug #1
> immediately had it existed before. Both confirmed via `git stash` (across all three touched
> files: `itr2.py`, `capital_gains.py`, `calculators/itr2.py`) to fail against the pre-fix code.
> Full combined regression run: `pytest tests/test_itr1_calculator.py tests/test_itr1_itd_builder.py
> tests/test_itr4_calculator.py tests/test_filing_gateway_v2_itr4.py tests/test_itr2_*.py
> tests/test_standalone_cg_schedule.py tests/test_draft_to_itr2_input.py` — 218 passed, 0 failed.
>
> **Update (2026-09-04, same day): the generic "other assets" mapping is now also fixed.** The
> 10 non-land/building, non-111A/112A `CGAssetType` categories (`unlisted_shares`,
> `listed_security`, `debt_mutual_fund`, `specified_mutual_fund_50aa`,
> `market_linked_debenture_50aa`, `bonds_debentures`, `depreciable_asset`, `jewellery`,
> `foreign_asset`, `other`) previously always emitted the zero-valued `SaleOnOtherAssets`
> (STCG)/`SaleofAssetNADtls.SaleofAssetNA` (LTCG) placeholder regardless of real transaction
> data. Confirmed via the official form (Schedule CG items 5 and 8, "From sale of assets other
> than at A1 or A2 or A3 or A4 above" / "...where B1 to B7 above are not applicable") that this
> is the genuine generic catch-all — internally split into "unquoted shares" (`unlisted_shares`,
> section 50CA deemed-consideration applies) and "assets other than unquoted shares" (the other 9
> categories). New helper `_other_assets_block()` (`app/engine/itd/itr2.py`) aggregates
> consideration/cost across every matching transaction, split by holding period (reusing
> `_is_short_term()`, matching the calculator's own classification exactly) and by the
> unquoted/non-unquoted split, with a new `deemed_consideration_50ca()` helper
> (`capital_gains.py`) applying the section 50CA "higher of consideration or FMV" comparison —
> deliberately distinct from `deemed_consideration_50c()`'s 110%-tolerance version for
> land/building, since the official form's own item 5(a)(i)(c)/8(a)(i)(c) text confirms section
> 50CA has no tolerance band. Indexation does not apply to this bucket at all (the official
> form's item 5b/8b only ever asks for "cost of acquisition **without** indexation" here), so no
> indexed-cost handling was needed, unlike land/building.
>
> **Tests**: `test_generic_other_assets_bucket_maps_jewellery_and_bonds` (schema-valid, and
> reconciles against `result.schedules["cg"].stcg.income_30per`/`ltcg.income_125per_other` — the
> calculator's own signed totals, not just the row's internal arithmetic) and
> `test_generic_other_assets_bucket_applies_section_50ca_for_unquoted_shares`. Both confirmed via
> `git stash` to fail against the pre-fix code. Full combined regression run after this addition:
> 220 passed, 0 failed (`test_itr1_calculator.py`, `test_itr1_itd_builder.py`,
> `test_itr4_calculator.py`, `test_filing_gateway_v2_itr4.py`, `test_itr2_*.py`,
> `test_standalone_cg_schedule.py`, `test_draft_to_itr2_input.py`).
>
> **Remaining, deliberately not attempted**: per-transaction §54/54B/54EC/54F exemption
> attribution to this bucket's `LossSec94of7Or94of8`/`DeductionUs54F` fields (both left at 0 —
> the aggregate `DeducClaimInfo.TotDeductClaim` elsewhere in Schedule CG is correct, just not
> broken out per-row here), and the section 94(7)/94(8) dividend-stripping loss-disallowance
> figure (Taxify has no input field capturing this at all). Also unaffected: §3.1's 115AD-specific
> fields (`NRISecur115AD`, `NRISaleOfEquityShareUs112A`) — confirmed distinct from this generic
> bucket, remain correctly zero pending a `CGAssetType`/FII-flag schema extension.

---

## 3.3 VDA business-income classification is serialized as capital gains

### Evidence

The VDA serializer at `itr2.py:876` emits:

```python
"HeadUndIncTaxed": "CG"
```

around lines 883–889. The generated VDA amount is also added to capital gains in Part B-TI around line 1471 and appears under `CapGains30Per115BBH` around line 1500.

### Impact

A VDA transaction selected or intended as business income can be filed as capital gains and taxed under the wrong head.

### Severity

~~**Critical**~~

> **Re-verified (2026-09-04): not a bug — ITR-2 cannot represent VDA business income at all, by
> form scope, not by omission.** The official AY 2026-27 schema's `ScheduleVDA.ScheduleVDADtls`
> item property for `HeadUndIncTaxed` has `"enum": ["CG"]` — a single legal value
> (`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_V1.1 (2).json`,
> `definitions.ScheduleVDA.properties.ScheduleVDADtls.items.properties.HeadUndIncTaxed`). There is
> no `"BP"` (business/profession) option in ITR-2's schema for this field at all. This matches
> ITR-2's own statutory scope: a taxpayer with any Profits & Gains from Business/Profession —
> including VDA transactions the taxpayer treats as business income — is required to file ITR-3
> (or ITR-4 for eligible presumptive cases), not ITR-2, regardless of how the taxpayer classifies
> the VDA transaction. `app/schemas/itr2.py`'s `VDATransaction` model correctly has no
> business/capital classification field, because ITR-2 has nothing to classify into — every VDA
> transaction reaching this serializer is definitionally capital-gains-taxed for this form. No fix
> applied; this finding is retracted as stated. (A taxpayer who genuinely wants VDA treated as
> business income needs Taxify to route them to ITR-3 filing at the form-selection stage, not to
> a VDA head-classification field within ITR-2 — that is a distinct, valid future feature request,
> not a defect in the current ITR-2 serializer.)

### Remediation

~~Add explicit VDA head classification to the canonical input. Reject unsupported head/form
combinations before calculation. Serialize `CG` or `BP` from the actual selection. Ensure
calculator, Schedule VDA, Part B-TI, and tax computation use the same classification. Add
capital-gains VDA, business-income VDA, mixed, zero-profit, and invalid-expense tests.~~ No
remediation needed — see re-verification note above.

---

## 3.4 Schedule OS has broad UI coverage but incomplete live serialization

### Evidence

`ScheduleOSWorkspace.tsx` supports categories including interest, dividends, gifts, lottery, online gaming, race-horse activity, unexplained income, DTAA income, section 89A, accumulated PF, deductions, pass-through income, and special-rate income. The category set is visible around lines 113–135, with entry creation and editing around lines 255–295.

The backend `_schedule_os()` begins at `itr2.py:482`. It initializes many fields to zero, including:

```text
IncomeNotified89AOS
IncomeNotifiedOther89AOS
IncomeNotifiedPrYr89AOS
TaxAccumulatedBalRecPF
OthersGross
PTIOthersGrossDtls
IncChargblSplRateOS
```

It then maps only selected aggregate values:

```python
block["DividendGross"] = ...
block["InterestGross"] = ...
block["IntrstFrmSavingBank"] = ...
block["IntrstFrmTermDeposit"] = ...
block["IntrstFrmIncmTaxRefund"] = ...
block["FamilyPension"] = ...
```

and handles only selected SI sections such as `115BB` and `115BBE`.

### Affected categories

- winnings;
- gifts under section 56(2)(x);
- DTAA income;
- section 89A income;
- accumulated PF;
- special-rate income;
- unexplained income categories;
- other-source deductions;
- pass-through income;
- race-horse income;
- dividend category distinctions; and
- date/quarter-specific information.

### Impact

A value can be entered in the frontend but not appear in the official JSON.

### Severity

**Critical**

### Remediation

Map each canonical `OtherSources` entry to the exact official field, including category code, gross amount, deductions, rate, dates/quarters, payer/donor information, TDS linkage, and source schedule. Add a populated-category preservation test for every OS category.

> **Fix status (2026-09-04): winnings, accumulated PF, and gifts fixed and
> verified; DTAA/§89A/special-rate-income-entries/deductions/quarter-level
> detail and race-horse-activity business income remain open (see below).**
>
> `draft.otherSources.winnings`/`accumulatedPf`/`gifts` were captured by the
> frontend but had **no path into `ITR2Input` at all** for ITR-2 --
> `_map_other_sources()` computed a `total_winnings` breakdown figure and
> discarded it, and gifts/PF had no mapping whatsoever. This meant winnings
> and gifts were silently excluded from **taxable income itself**, not just
> from the JSON -- a revenue-correctness bug, not merely an incompleteness
> one.
>
> `app/engine/draft_to_itr2_input.py` gained three new mapper functions:
> - `_map_os_winnings_to_si()` -- aggregates `WinningIncome` rows by Schedule-SI
>   section (LOTTERY/BETTING/CARD_GAME/HORSE_RACE → 115BB, ONLINE_GAMING →
>   115BBJ, UNEXPLAINED_115BBE → 115BBE) and appends them to `si_entries`,
>   reusing the calculator's existing (and already-correct) `compute_lottery`/
>   `compute_115bbj`/`compute_115bbe` dispatch in `compute()`.
> - `_map_os_accumulated_pf()` -- aggregates `AccumulatedPfEntry` rows into a
>   section-111 SI entry plus `TotalIncomeBenefit`/`TotalTaxBenefit` totals
>   (new `ITR2Input.os_pf_income_benefit`/`os_pf_tax_benefit` fields).
> - `_compute_os_gifts()` -- computes Section 56(2)(x) taxable-gift totals
>   with the correct statutory thresholds (money/other-property-without-
>   consideration tested against the aggregate INR 50,000 threshold, whole
>   amount taxable once crossed; immovable property tested per-property
>   against its own stamp-duty-value/inadequate-consideration threshold;
>   relative/marriage gifts exempt), feeding the existing
>   `OtherSourcesIncome.income_56_2_x` field via `model_copy`, plus a new
>   `ITR2Input.os_gift_breakdown` (`OSGiftBreakdown`, new schema type) for
>   the JSON category split.
>
> **A second, more severe pre-existing bug was found and fixed while wiring
> this**: `input_data.si_entries` sections 115BB/115BBE/115BBF/115BBG/
> 115BBJ/115BBA/111 were dispatched for *tax* (`special_rate_tax`) but were
> **never added to GTI/Total Income** in `compute()` -- unlike capital-gains
> SI categories (111A/112/112A/VDA), which correctly flow into
> `gti_before_loss_setoff` via `positive_regular_cg`/`vda_income` before the
> SI dispatch runs. Yet `special_rate_income_for_slab` (which shrinks the
> slab-tax base) already *subtracted* this same total via
> `si_result.surcharge_full_income` -- meaning any of these categories
> reduced slab tax on unrelated income without the income itself ever
> appearing in Total Income. This bug pre-dates this session (reachable via
> the frontend's generic Schedule SI manual-entry editor,
> `draft.scheduleSIEntries`, for any user who added a 115BB/etc row
> directly) but was never caught because no test exercised it end-to-end.
> Fixed in `app/engine/calculators/itr2.py::compute()` by adding these
> sections' `gross_income` to `r.other_sources_income` before GTI is
> computed (mirroring the CG pattern exactly).
>
> **A third bug surfaced by making section 111 (accumulated PF) reachable
> for the first time**: `_schedule_si()` in `app/engine/itd/itr2.py` emitted
> `SplRatePercent: 0` for the section-111 SI entry (it's a genuine 0%-rate
> dispatch entry internally, since PF income is taxed at slab rate) -- but
> the official schema's `SplRatePercent` enum has no `0` value, so this
> failed schema validation outright. Fixed by excluding section-111 entries
> from `ScheduleSI`'s `SplCodeRateTax` rows entirely (its disclosure lives
> in Schedule OS's `TaxAccumulatedBalRecPF`, already wired above); also
> added the missing `115BBA`/`115BBJ` → `5BBA`/`5BBJ` `SecCode` mappings
> (previously fell through to the generic default `"1"`, which happens to
> be section 111's own code -- silently wrong for any 115BBJ/115BBA income).
>
> **Deliberately not fixed in this pass** (documented, not silently
> dropped): DTAA-rate OS income, Section 89A (foreign retirement-account
> deferral), `SpecialRateIncomeEntry` (the generic Schedule 5A-adjacent
> bucket), Schedule OS deductions (`Deductions` block), and per-entry
> quarter-level advance-tax-interest detail (`IncFrmLottery`/
> `IncFrmOnGames`/`NOT89A`/dividend-category date-range objects, currently
> emitted as all-zero placeholders via `_date_range()`) remain open --
> these are lower real-world frequency and/or informational/relief-only
> (89A specifically is a deferral, not new taxable income, so its absence
> is not a Total Income correctness bug the way winnings/gifts were).
> `RACE_HORSE_ACTIVITY` winning-income rows are also intentionally excluded
> from the SI mapping -- income from owning/maintaining race horses is a
> distinct business-like OS sub-head (`IncFromOwnHorse`) with its own
> deduction rules, not a flat special-rate item, and has no calculator
> support at all yet. These are tracked as follow-up work, not silently
> left broken.
>
> Regression tests: `test_lottery_winnings_are_included_in_total_income_and_taxed_at_115bb`,
> `test_accumulated_pf_maps_to_section_111_si_entry_and_pf_totals`,
> `test_taxable_gift_from_non_relative_is_included_income_56_2_x`,
> `test_gift_from_relative_is_exempt`,
> `test_gift_below_fifty_thousand_threshold_is_exempt` (all in
> `tests/test_draft_to_itr2_input.py`), and
> `test_schedule_os_serializes_lottery_pf_and_gift_income` (in
> `tests/test_itr2_itd_builder.py`) -- confirmed via `git stash` to be
> entirely absent (and their underlying schema fields nonexistent) on
> pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite (227 tests) green.

---

## 3.5 Negative house-property income is forced to zero in Part B-TI

### Evidence

`_partb_ti()` emits:

```python
"IncomeFromHP": _to_rupees(max(_ZERO, result.house_property_income))
```

at `itr2.py:1474`.

The Schedule HP serializer separately emits the signed result around `itr2.py:471`.

### Impact

A legitimate house-property loss can appear as zero in Part B-TI while the calculation engine and Schedule HP contain a negative amount. This can create inconsistencies in current-year set-off, BFLA, CFL, and total-income reporting.

### Severity

**Critical** — ~~superseded, see re-verification below~~

> **Re-verified (2026-09-04): not a bug.** `PartB-TI.IncomeFromHP` in the official AY 2026-27
> JSON schema (`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_V1.1 (2).json`,
> `definitions.PartB-TI.properties.IncomeFromHP`) is schema-constrained to `"minimum": 0,
> "exclusiveMinimum": false` — a negative value here would fail official schema validation, so
> the `max(_ZERO, ...)` clamp at `itr2.py:1474` is schema-mandated, not a defect. By contrast
> `ScheduleHP.TotalIncomeChargeableUnHP` (`itr2.py:474`, cited correctly by this finding as
> emitting the signed value) has `"minimum": -99999999999999` in the schema — the two fields are
> legitimately different: Schedule HP reports the head's own signed result, Part B-TI reports
> post-set-off income only. The loss is not silently dropped: `_schedule_cyla()`
> (`itr2.py:203-253`) separately computes `hp_remaining = abs(min(z, result.house_property_income))`
> when HP income is negative and correctly emits it via `LossRemAftSetOff.BalHPlossCurYrAftSetoff`,
> `TotalCurYr.TotHPlossCurYr`, and `TotalLossSetOff.TotHPlossCurYrSetoff` — the official CYLA
> mechanism's actual designated place for a per-head current-year loss, not Part B-TI's aggregate
> income field. No fix applied; this finding is retracted as stated. (Not yet independently
> re-verified: whether the calculator's `cyla.hp_setoff` value itself is arithmetically correct
> for every HP-loss scenario — that is a calculator-correctness question, not this serializer
> finding, and remains open for whoever next audits `app/engine/calculators/itr2.py`'s CYLA step.)

### Remediation

~~Preserve signed HP values where the official field permits them and use separate fields for current-year loss, set-off, remaining loss, and income after set-off. Add self-occupied, let-out, multiple-property, interest-limitation, and carried-forward-loss tests.~~ No remediation needed for Part B-TI's `IncomeFromHP` itself — see re-verification note above.

---

## 3.6 TDS-2 and TDS-3 details are hardcoded or incomplete

### Evidence

`_schedule_tds2()` is around `itr2.py:1383–1411`. It hardcodes:

```python
"TDSCreditName": "S"
"BroughtFwdTDSAmt": 0
"HeadOfIncome": "OS"
```

`_schedule_tds3()` is around `itr2.py:1414–1435` and hardcodes ownership and brought-forward values similarly. TDS-3 uses buyer/tenant PAN and head-of-income details, but the full official data set remains incomplete.

### Impact

The return cannot correctly represent:

- TDS belonging to another person;
- brought-forward credit;
- credit carried forward;
- heads other than OS;
- partial claims;
- buyer/tenant details; and
- full TDS-3 classification.

### Severity

**High to Critical**

### Remediation

Map canonical TDS ownership, spouse/other-person PAN, deducted year, brought-forward credit, current-year deduction, claim, carry-forward, head of income, gross amount, and buyer/tenant fields. Do not substitute `S` or `OS` unless that is the actual selected value.

> **Fix status (2026-09-04): fixed and verified.** `TDS2Entry`/`TDS3Entry`
> (`app/schemas/itr1.py`) gained `ownership`, `pan_of_other_person`,
> `aadhaar_of_other_person` fields; `TDS2Entry` and `TDS3Entry` already carried
> `brought_forward_tds`/`tds_credit_carried_forward`/`head_of_income` but these
> were being discarded rather than serialized. `_map_tds()`/`_map_tds3()`
> (`app/engine/draft_to_itr1_input.py`) now read the ownership/PAN/Aadhaar
> fields from the frontend's existing `TdsCredit` draft rows (this data was
> always captured by the UI — it was dropped in mapping, not missing at the
> source). `_schedule_tds2()`/`_schedule_tds3()` (`app/engine/itd/itr2.py`) now
> emit `entry.ownership` for `TDSCreditName`, conditionally add
> `PANofOtherPerson`/`AadhaarOfOtherPerson` when ownership is `"O"`, and read
> `BroughtFwdTDSAmt`/`AmtCarriedFwd`/`HeadOfIncome` from the real fields
> instead of hardcoding.
>
> While wiring this, found and fixed **three separate crash bugs**, all
> variants of the same root cause (a field name copied from `TDS2Entry`,
> which has different attribute names than `TDS3Entry`):
> 1. `app/engine/calculators/itr2.py::compute()` read
>    `entry.tds_claimed_this_year` on `TDS3Entry` objects (that name belongs
>    only to `TDS2Entry`; `TDS3Entry`'s field is `tds_claimed`) — this crashed
>    `compute()` itself, before the JSON builder ever ran, on any return with
>    populated `tds3_entries`.
> 2. `_schedule_tds3()` (`app/engine/itd/itr2.py`) read `entry.financial_year`
>    on `TDS3Entry` (no such field exists on that model — it carries the
>    deducted year directly as `deducted_yr`, a `"20XX"` string, not a
>    `"20XX-YY"` financial-year string to parse).
> 3. `_schedule_tds3()` also read `entry.gross_amount` on `TDS3Entry` (that
>    field is named `gross_receipt` on that model).
>
> None of these three were reachable by any prior test — `test_itr2_itd_builder.py`
> had zero tests constructing a `TDS3Entry` with real data before this fix.
> The same `tds_claimed_this_year`/`tds_claimed` typo was independently found
> and fixed a fourth time in `app/engine/validators/itr2/calc_rules.py`'s
> `validate_itr2_calculation()` (a genuine crash bug, fixed even though
> validator *logic* additions are out of this audit doc's scope — this was a
> mechanical attribute-name fix, not a new validation rule).
>
> Regression test: `test_tds2_tds3_tcs_carry_ownership_and_brought_forward_data`
> in `tests/test_itr2_itd_builder.py`, confirmed via `git stash` to be entirely
> absent (and its underlying schema fields nonexistent) on pre-fix code.

---

## 3.7 TCS ownership and claim amounts are hardcoded to self

### Evidence

The canonical model has ownership fields around `return_draft.py:1315–1337`. The serializer at `itr2.py:1438–1460` emits:

```python
"TCSCreditOwner": "1"
```

and sets spouse/other-person collection and claim values to zero.

### Impact

TCS belonging to a spouse or another person cannot be represented. The credit may be attributed to the wrong taxpayer or omitted.

### Severity

**Critical**

### Remediation

Map current-year ownership, spouse/other-person PAN, own-hand and other-person collection, own-hand and other-person claim, brought-forward, and carried-forward values. Add tests for self, spouse, other-person, and partial claims.

> **Fix status (2026-09-04): fixed and verified.** `TCSEntry`
> (`app/schemas/itr1.py`) gained `ownership`, `pan_of_spouse_or_other_person`,
> `tcs_collected_spouse_or_other`, `tcs_credit_claimed_spouse_or_other`,
> `brought_forward_tds`, `tds_credit_carried_forward`, `deducted_year`.
> `_map_tcs()` (`app/engine/draft_to_itr1_input.py`) now reads all of these
> from the frontend's existing `TcsCredit` draft rows. `_schedule_tcs()`
> (`app/engine/itd/itr2.py`) now emits `entry.ownership` for
> `TCSCreditOwner`, conditionally adds `PANOfSpouseOrOthrPrsn` when ownership
> is `"2"`, uses the real spouse-side collected/claimed amounts for
> `TCSCurrFYDtls.TCSAmtCollSpouseOrOthrHand`/
> `TCSClaimedThisYearDtls.TCSAmtCollSpouseOrOthrHand` (previously hardcoded
> to `0`), and reads `AmtCarriedFwd` from the explicit
> `tds_credit_carried_forward` field. `TotalSchTCS` was also fixed to sum
> both own-hand and spouse-side claimed amounts, not own-hand alone.
>
> Regression test: `test_tds2_tds3_tcs_carry_ownership_and_brought_forward_data`
> in `tests/test_itr2_itd_builder.py` (same test covers all three schedules —
> TDS2/TDS3/TCS share the ownership-pattern root cause). Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite (221 tests)
> confirmed green after this fix, alongside §3.2's land/building and
> generic-other-assets fixes from the same phase.

---

## 3.8 Schedule IT can omit tax-payment challans

### Evidence

`_schedule_it()` requires BSR code, payment date, and challan serial number and raises when any is absent, around `itr2.py:1350–1365`.

### Impact

A tax payment can exist in canonical data but fail to appear in Schedule IT if the frontend does not capture all required challan details or if the entry is not routed into `tax_payment_entries`.

### Severity

**High**

### Remediation

Use a complete Schedule IT editor, block JSON generation with field-specific errors for incomplete challans, and reconcile Schedule IT totals with Part B-TTI taxes paid.

---

# 4. Part A-GEN and filing profile

## 4.1 Residential-status facts are incomplete

The serializer emits only the status classification:

```python
"ResidentialStatus": profile.residential_status.value
```

at `itr2.py:111–137`. The frontend does not visibly capture the complete supporting facts, including current/prior India stay, foreign jurisdiction, foreign TIN, and the basis for NRI/NOR classification.

**Severity: High**

**Remediation:** add a conditional residential-status questionnaire and retain the supporting facts in the canonical profile.

## 4.2 FII/FPI and SEBI information is incomplete

The backend emits `FiiFpiFlag` and optionally `SEBIRegNo` around `itr2.py:132–137`, but the frontend does not provide a complete workflow for all associated information and income classification.

**Severity: High**

## 4.3 Director and unlisted-equity disclosures are reduced to flags

The model has `isDirector` and `holdsUnlistedShares` around `return_draft.py:1492–1502`, but the frontend does not provide the complete official detail tables, such as company identity, DIN/directorship details, ISIN, acquisition/disposal, share count, face value, and cost.

**Severity: High**

## 4.4 Section 115H is missing

The frontend filing-profile workflow does not expose section 115H applicability and supporting information.

**Severity: High**

## 4.5 Section 92CD is missing from the filing-section dropdown

`PersonalInfoTab.tsx:205–211` exposes filing sections including 139(1), 139(4), 142(1), 148, 153C, 139(5), 139(9), and 119(2)(b), but not 92CD, despite backend support.

**Severity: High**

> **Fix status (2026-09-04): fixed and verified.** "Despite backend
> support" needed correction during the fix: `ITR2Input`'s
> `ReturnFileSection.MODIFIED_92CD = 19` enum member existed, but nothing
> upstream could actually reach it — the canonical draft's own
> `FilingSection` `Literal` (`app/schemas/return_draft.py`) had no `"92CD"`
> member, and `app/engine/personal_profile.py::FILING_SECTION_CODES` (the
> string→CBDT-code map `normalize_personal_profile()` uses for every form)
> had no entry for it either. Added `"92CD"` to both, added
> `"92CD": 19` to `FILING_SECTION_CODES`, and added the missing
> `<option value="92CD">92CD — Modified return</option>` to
> `PersonalInfoTab.tsx`'s filing-section dropdown (and the frontend's own
> `FilingSection` type in `frontend/src/domain/returns/types.ts`).
> `ITR2FilingProfile.validate_conditional_filing_facts()` does not require
> notice-number/notice-date for 92CD (that requirement is scoped to
> 142(1)/148/153C/139(9) only), so no further conditional-field work was
> needed. Regression test:
> `test_normalize_personal_profile_maps_92cd_to_code_19` in
> `tests/test_personal_profile.py`, confirmed via `git stash` to be absent
> on pre-fix code.

## 4.6 Current-account deposits are incorrectly gated to ITR-4

At `PersonalInfoTab.tsx:215`, the current-account deposit threshold controls are rendered only when `itrForm === 'ITR-4'`. The canonical model documentation at `return_draft.py:1399–1403` states that the seventh-proviso block is shared by ITR-2 and ITR-4.

**Severity: Critical**

**Remediation:** render the control for ITR-2 with the correct form-specific clauses and thresholds.

> **Fix status (2026-09-04): fixed and verified.** Changed the gate from
> `itrForm === 'ITR-4'` to `itrForm === 'ITR-4' || itrForm === 'ITR-2'` in
> `PersonalInfoTab.tsx`. The backend side of this was already correct
> before this fix — `app/engine/filing_gateway_v2.py`'s ITR-2 profile
> builder already reads `seventh.deposit_amount`/`deposit_exceeds_one_crore`
> into `ITR2FilingProfile.current_account_deposits`/`seventh_proviso_139`
> (confirmed at `filing_gateway_v2.py:1230-1238`) — the bug was purely that
> the frontend control was unreachable for ITR-2 filers, so the data could
> never be entered in the first place. `npm run build` confirmed clean
> after the type/dropdown change.

## 4.7 LEI fields are missing or incomplete

Applicable LEI information is not represented through a complete frontend workflow.

**Severity: Medium to High**, depending on taxpayer and transaction applicability.

---

# 5. Schedule S — Salary

## 5.1 Salary detail rows are modeled but not fully rendered

The canonical model contains salary nature, perquisite nature, and section 10 exemption rows around `return_draft.py:208–210`. The frontend does not provide a complete official detail-table experience for all categories.

Missing or incomplete areas include:

- nature of salary;
- employer-specific breakdown;
- perquisite categories;
- profits in lieu of salary;
- section 10 exemption classifications;
- retirement benefits;
- section 89A;
- employer address and TAN completeness;
- arrears and salary-period details; and
- relief linkage.

**Severity: High**

## 5.2 HRA is simplified

HRA captures simplified facts but does not expose the complete section 10(13A) structure, including rent, period, landlord details/PAN where applicable, city classification, and computation inputs.

**Severity: High**

## 5.3 Retirement and section 89A fields are incomplete

Retirement-benefit and section 89A data are not consistently represented with the full assessment-year-specific official structure.

**Severity: High**

---

# 6. Schedule HP — House Property

## 6.1 Loan and property details are incomplete

`_schedule_hp()` begins around `itr2.py:424` and emits an empty section 24(b) detail array:

```python
"Section24BDtls": []
```

around `itr2.py:454–465`.

Missing or incomplete details include:

- lender identity, PAN, and address;
- loan sanction date and amount;
- property completion date;
- pre-construction interest;
- current-year interest;
- ownership percentage and co-owner data;
- tenant identity/details;
- unrealized rent and arrears;
- municipal tax detail;
- property completion status; and
- complete property address information.

**Severity: Critical for affected cases**

## 6.2 Self-occupied property is over-simplified

The serializer calculates ALV and standard deduction using simplified logic around `itr2.py:434–438`, which does not guarantee that the official self-occupied-property and loan fields are correctly represented.

**Severity: High**

## 6.3 Schedule HP and Part B-TI can disagree

Schedule HP emits `result.house_property_income`, while Part B-TI clamps negative HP income to zero.

> **Re-verified (2026-09-04): not a defect — see §3.5's re-verification note for the full
> schema evidence.** `PartB-TI.IncomeFromHP` is schema-constrained non-negative
> (`minimum: 0`); `ScheduleHP.TotalIncomeChargeableUnHP` is schema-permitted negative
> (`minimum: -99999999999999`). The two fields are intentionally different by design, and the
> loss itself is correctly tracked through `_schedule_cyla()`'s dedicated loss fields, not lost.

~~**Severity: Critical**~~

---

# 7. Schedule OS and exempt income

## 7.1 UI breadth exceeds backend coverage

The frontend supports categories that are initialized but not equivalently serialized. This is especially material for winnings, gifts, DTAA, 89A, PF, unexplained income, special-rate income, PTI, and deductions.

**Severity: Critical**

## 7.2 Exempt-income rows default to a misleading category

New exempt-income rows default to provident-fund income under section 10(11), even if the taxpayer has not selected that source.

**Severity: Medium to High**

**Remediation:** use an explicit unselected state and require the exemption category.

## 7.3 Agricultural-income details are not fully gated

Agricultural-income fields are not consistently gated by the official income threshold and applicable category conditions.

**Severity: Medium**

## 7.4 Legacy mapper has no complete Schedule EI mapping

`frontend/src/api/itr2Mapper.ts` has no complete Schedule EI mapping and therefore drops exempt-income detail on that path.

**Severity: High**

---

# 8. Deductions

## 8.1 Detail schedules are frequently reduced to aggregates

The canonical model contains detailed structures such as `Schedule80GGAEntry` and `Schedule80GGCEntry`, but several frontend and legacy-mapper paths expose aggregate amounts rather than complete official detail rows.

Affected areas include 80C, 80D, 80G, 80GGA, 80GGC, 80GG, 80CCD, 80DD, 80DDB, 80E, 80EE, 80EEA, 80EEB, and 80U.

**Severity: High**

## 8.2 Cash contributions remain editable where restricted

The canonical 80GGA and 80GGC entries contain `cashAmount` and `otherModeAmount`, and the frontend allows cash values to remain editable even where statutory rules restrict or disallow them.

**Severity: High**

The UI should remove the prohibited mode, render it as fixed zero, or clearly block it before submission.

## 8.3 Monetary limits and integer semantics are inconsistent

Preventive-health-checkup limits and other statutory monetary semantics are not enforced consistently in the UI. These concerns are separate from the excluded validator audit because they relate to frontend input design and user-visible state.

---

# 9. Schedule SI, AMT, AMTC, and CFL

## 9.1 Schedule SI is too generic and narrow

`ITR2SchedulesWorkspace.tsx:35` creates a generic Schedule SI entry with default section `115BB`. The list is rendered using generic fields around line 117. The official form has substantially more special-rate classifications and category-specific structures.

**Severity: High**

**Remediation:** use the complete AY 2026–27 official section-code enumeration and render category-specific fields.

## 9.2 AMT and AMTC are combined in the frontend

The frontend presents `Schedule AMT / AMTC` as one nullable generic section around `ITR2SchedulesWorkspace.tsx:123`, while the backend has separate `_schedule_amt()` and `_schedule_amtc()` functions at `itr2.py:1171` and `itr2.py:1184`.

**Severity: High**

## 9.3 AMTC historical credit ledger is absent

The frontend exposes only a few AMT deduction fields and no year-by-year AMTC ledger for brought-forward credit, utilization, and carry-forward.

**Severity: High**

## 9.4 CFL is backend-only with no reconciliation display

The frontend states around `ITR2SchedulesWorkspace.tsx:116` that Schedule CFL is computed by the backend and has nothing to enter. Computation can remain backend-authoritative, but the preparer needs a read-only year-by-year reconciliation showing current-year losses, set-off, and carry-forward.

**Severity: Medium to High**

---

# 10. Foreign schedules

## 10.1 FSI and TR are compressed generic rows

The frontend renders FSI and TR with generic lists around `ITR2SchedulesWorkspace.tsx:118–119`.

FSI fields include country code, TIN, salary/HP/CG/OS income, foreign tax, Indian tax, and relief section. TR adds income included, tax paid, Indian tax, relief, section, and Form 67 flag.

This is useful baseline coverage but does not fully expose official category, treaty, conversion, Form 67, timing, and limitation information.

**Severity: High**

## 10.2 Schedule FA is substantially under-modeled

The frontend creates a generic foreign asset row around `ITR2SchedulesWorkspace.tsx:38` with:

```text
assetType
countryCode
institutionOrEntityName
address
accountOrAssetIdentifier
ownershipStatus
openingOrAcquisitionDate
peakValue
closingValue
grossIncome
incomeOffered
incomeHead
```

The official Schedule FA requires different structures for foreign bank accounts, custodial accounts, equity/debt interests, insurance, trusts, signing authority, immovable property, and other assets.

Missing category-specific data includes account type, institution details, peak/closing values, acquisition and ownership facts, entity interest, policy/trust information, signing-authority reason, income, and tax-offering linkage.

**Severity: Critical for foreign-asset taxpayers**

---

# 11. Schedule SPI and PTI

## 11.1 SPI is compressed to a generic clubbing row

The frontend exposes name, PAN, relationship, amount, and head around `ITR2SchedulesWorkspace.tsx:121`, but not the complete section 64 clause, source-income, loss, and schedule-linkage structure.

**Severity: Medium to High**

## 11.2 PTI is compressed

The frontend exposes entity name/PAN, income head, section, income amount, and TDS credit around line 122, but this is insufficient for all pass-through income distinctions and credit linkage.

**Severity: High for affected taxpayers**

---

# 12. Schedule 5A — Portuguese Civil Code

## 12.1 Independent applicability state can diverge

The canonical model has both `portugueseCivilCodeApplies` and `portugueseCivilCode` around `return_draft.py:1416–1419` and `return_draft.py:1608`. The frontend presents Schedule 5A as an independently nullable generic section around `ITR2SchedulesWorkspace.tsx:125`.

This can permit contradictory states: Schedule 5A enabled without the filing-profile condition, or the filing-profile condition enabled without complete schedule data.

**Severity: High**

**Remediation:** use one authoritative applicability state derived from the filing profile and conditionally render the schedule.

## 12.2 Schedule 5A is reduced to a compact row

The UI exposes spouse name/PAN/Aadhaar and apportioned HP, CG, OS, and TDS values, but not the complete official apportionment structure.

**Severity: Medium to High**

---

# 13. Schedule ESOP

## 13.1 Generic ledger is insufficient for official events

The frontend renders ESOP entries around `ITR2SchedulesWorkspace.tsx:126` with employer PAN, DPIIT registration number, AY, brought-forward deferred tax, current-year payable tax, and carried-forward balance.

The serializer begins around `itr2.py:1316` and serializes from the first entry. This is not sufficient for complete assessment-year-specific event structures and multiple employer/event cases.

**Severity: High**

**Remediation:** model employer-level data, grant/event-level information, and a complete AY ledger with brought-forward, current-year, payable, and carried-forward amounts.

---

# 14. Precision and monetary representation

## 14.1 Backend Decimal versus frontend number

The backend uses `Decimal` by project convention, but the frontend and legacy mapper extensively use JavaScript `number`, `Number(value)`, and `parseFloat`.

Representative locations include:

```text
frontend/src/api/itr2Mapper.ts
frontend/src/utils/prefillTypes.ts
frontend/src/utils/mapTisToDraftPatch.ts
```

### Risks

- IEEE-754 precision loss for large amounts;
- inconsistent rounding;
- blank values becoming zero;
- loss of negative/empty distinctions;
- inaccurate statutory caps;
- mismatch between displayed totals and submitted totals; and
- inaccurate exact CBDT integer serialization.

**Severity: High**

### Remediation

Represent editable money as decimal strings in the frontend, normalize only at the API boundary, avoid JavaScript arithmetic for authoritative totals, reject malformed values rather than coercing them to zero, and preserve blank, zero, and negative states distinctly.

---

# 15. Legacy mapper detail

`frontend/src/api/itr2Mapper.ts` is unsuitable as a complete ITR-2 filing mapper.

### Filing profile

It captures a narrow identity/address/status subset but does not fully map alternate addresses, conditional filing sections, seventh-proviso details, representatives, TRP data, director/unlisted-share detail, FII/FPI/SEBI information, 115H, 92CD, and LEI data.

### Salary

It maps aggregate salary, perquisites, profits in lieu, and HRA exemption but not complete employer, salary-nature, perquisite, section 10, retirement, and section 89A records.

### House property

It maps property type, rent, municipal taxes, loan interest, and limited address data but not complete loan, ownership, tenant, property, and address structures.

### Other sources

It maps selected savings-bank interest, term-deposit interest, family pension, and dividends but not the complete Schedule OS category set.

### Capital gains

It exposes transaction and 112A arrays but does not fully map all official CG categories, non-resident classifications, DTAA rates, losses, deemed consideration, and exemption rows.

### Deductions

It uses aggregate deduction fields and does not preserve all detail schedules.

### TDS/TCS

It uses simplified credit arrays and lacks the complete ownership, brought-forward, carry-forward, spouse/other-person, and head-of-income model.

**Conclusion:** the legacy mapper must be removed, made unreachable, or replaced by a strict adapter that preserves canonical data.

---

# 16. Schema-validity versus semantic completeness

The serializer intentionally emits many zero-valued structures. Some are required by the schema, but zero placeholders are unsafe when they stand in for populated canonical data.

Examples include:

- `NRISecur115AD` and other Schedule CG placeholders;
- many Schedule OS category fields;
- empty `Section24BDtls` in Schedule HP;
- hardcoded loss and special-rate fields in Part B-TI;
- hardcoded TDS/TCS ownership and head values.

`additionalProperties: false` protects the structure but cannot detect that a taxpayer-entered field was dropped or misclassified. Official schema validation is necessary but not sufficient.

---

# 17. Production-readiness classification

## Not safe for broad production use today

The current implementation is not safe for complete returns involving:

- NRI/NOR status;
- foreign assets or foreign income;
- foreign tax relief;
- section 115AD;
- complex capital gains;
- VDA business income;
- detailed Schedule OS categories;
- AMT/AMTC history;
- ESOP deferrals;
- Portuguese Civil Code apportionment;
- spouse/other-person TDS/TCS credits;
- complex house-property loans;
- director/unlisted-share disclosures; or
- detailed prior-year loss reconciliation.

## Narrow cases with possible limited utility

The system may serve as a calculation aid for a simple resident taxpayer with salary and simple interest, no foreign matters, no complex capital gains, no special-rate OS income, no AMT/AMTC, no complex credits, and no complex HP loan.

Even those cases require independent review of the generated JSON against the official utility/schema before filing.

---

# 18. Prioritized remediation plan

## P0 — Required before production filing

1. **Establish one canonical path**
   - remove or disable the legacy mapper;
   - ensure every ITR-2 route uses `ReturnDraft`;
   - assert the active route at the API boundary;
   - add serialized-field coverage tests.

2. **Complete capital-gains serialization**
   - ~~dedicated Schedule 115AD~~ — re-verified §3.1: genuinely not representable without a new
     `CGAssetType`/FII-flag addition; `NRISecur115AD`/`NRISaleOfEquityShareUs112A` are correctly
     zero when absent, not a mislabeled bucket. Remains open, scope narrowed.
   - ~~land/building STCG/LTCG detail~~ — **fixed 2026-09-04**, see §3.2's fix write-up (was a
     schema-blocking wrong-field-name bug, not just missing detail; §50C deeming added as a new
     capability).
   - ~~all OTHER CG categories (`unlisted_shares`, `listed_security`, `debt_mutual_fund`,
     `specified_mutual_fund_50aa`, `market_linked_debenture_50aa`, `bonds_debentures`,
     `depreciable_asset`, `jewellery`, `foreign_asset`, `other`)~~ — **fixed 2026-09-04**, see
     §3.2's fix write-up update (mapped into the generic `SaleOnOtherAssets`/`SaleofAssetNADtls`
     bucket per the official form's Schedule CG items 5/8, with section 50CA deeming for
     unquoted shares).
   - section-specific exemptions — still pending (per-transaction §54/54B/54EC/54F claims are not
     wired to individual Schedule CG rows, though the aggregate `DeducClaimInfo.TotDeductClaim`
     is correct).
   - signed loss handling — resolved for land/building (§3.2); still open for the other 10
     categories above.
   - CYLA/BFLA/CFL reconciliation — not yet independently re-audited in this pass.
   - **New P0 item found 2026-09-04**: `compute_ltcg()`'s land/building gain formula uses the
     *indexed* cost as primary when supplied, but the official form requires the *non-indexed*
     cost as primary — indexation should only feed a separate section 112(1)(a) second-proviso
     tax comparison that can only reduce, never set, the base gain. Deliberately left unfixed in
     this pass (needs the full dual tax-comparison implemented correctly, not a one-line formula
     swap) — see §3.2's fix write-up for the complete evidence trail.
   - no silent zero placeholders for populated data — resolved for land/building; open elsewhere.

3. **Complete Schedule OS**
   - ~~winnings, accumulated PF~~ — **fixed 2026-09-04**, see §3.4's fix write-up (also fixed a
     pre-existing bug where this SI-dispatched income was taxed but never added to Total Income).
   - ~~gifts (section 56(2)(x))~~ — **fixed 2026-09-04**, see §3.4's fix write-up (relative/marriage
     exemption and the correct aggregate/per-property thresholds applied).
   - DTAA, 89A, unexplained income, special-rate-income entries, PTI, deductions, and dividend
     sub-categories — still open (documented in §3.4's fix write-up as deliberately scoped out;
     89A specifically is a deferral relief, not new taxable income, so lower urgency than the
     items above were).
   - `RACE_HORSE_ACTIVITY` winnings (owning/maintaining race horses — a distinct business-like OS
     sub-head with its own deduction rules) — still open, no calculator support at all yet.
   - category-specific detail and TDS linkage — still open.
   - populated-category preservation tests — added for winnings/PF/gifts; still open for the rest.

4. ~~**Correct TDS/TCS credits**~~ — **fixed 2026-09-04**, see §3.6/§3.7's fix write-ups: ownership,
   spouse/other-person PAN, brought-forward and carry-forward, correct head of income, and total
   reconciliation are all now real. Also fixed four crash-bug typos found along the way
   (`TDS3Entry.tds_claimed_this_year`/`financial_year`/`gross_amount` misreads). Partial-claims
   handling was already correct before this fix (unaffected).

5. ~~**Correct negative HP handling**~~ — **re-verified 2026-09-04, not a defect**: see §3.5's
   and §6.3's re-verification notes. `PartB-TI.IncomeFromHP`'s non-negative constraint is
   schema-mandated; the loss is correctly tracked via `_schedule_cyla()`'s dedicated fields, not
   silently dropped.

6. **Complete filing profile**
   - ~~current-account deposit seventh-proviso field for ITR-2~~ — **fixed 2026-09-04**, see §4.6's
     fix write-up (backend was already correct; the frontend control was simply gated to ITR-4 only).
   - ~~92CD~~ — **fixed 2026-09-04**, see §4.5's fix write-up (was unreachable at three layers: draft
     schema, `FILING_SECTION_CODES` map, and the frontend dropdown).
   - 115H — still open.
   - residential-status facts — still open.
   - FII/FPI and SEBI — still open.
   - director details — still open.
   - unlisted-equity details — still open.
   - LEI — still open.

## P1 — Required for broad taxpayer coverage

7. Expand Schedule HP with section 24(b), pre-construction interest, ownership, co-owner, tenant, unrealized-rent, and complete property details.

8. Replace generic Schedule FA rows with category-specific foreign bank, custodial, equity/debt, insurance, trust, signing-authority, property, and other-asset editors and serializers.

9. Separate AMT and AMTC in the UI and add the historical AMTC ledger.

10. Add a read-only Schedule CFL year-by-year reconciliation.

11. Expand Schedule S with employer, salary nature, perquisite, section 10, HRA, retirement, arrears, and section 89A structures.

## P2 — Quality and maintainability

12. Replace frontend monetary `number` values with decimal strings.

13. Add populated-data preservation tests for every canonical category.

14. Add semantic reconciliation between canonical input, prepared input, calculator result, and CBDT JSON.

15. Add explicit unsupported-case errors instead of silently omitting data.

---

# 19. Recommended test matrix

## Filing profile

- resident, NRI, and NOR;
- seventh-proviso current-account deposit;
- foreign travel and electricity thresholds;
- 92CD and 115H;
- FII/FPI;
- director;
- unlisted shares;
- LEI.

## Salary

- multiple employers;
- perquisites;
- profits in lieu;
- HRA;
- retirement benefits;
- arrears and section 89;
- section 89A.

## House property

- self-occupied loss;
- let-out property;
- multiple properties;
- pre-construction interest;
- co-owned property;
- unrealized rent;
- tenant details;
- section 24(b) loan records.

## Capital gains

- land/building STCG and LTCG;
- 111A;
- 112A;
- 115AD;
- foreign asset;
- other asset;
- DTAA rate;
- sections 54, 54B, 54EC, 54F, and 115F;
- current-year loss;
- brought-forward loss;
- buyback-related loss;
- deemed consideration.

## Other sources

- all interest categories;
- dividend classifications;
- gifts;
- lottery;
- online games;
- racehorse activity;
- unexplained income;
- DTAA income;
- 89A;
- accumulated PF;
- special-rate income;
- OS deductions;
- PTI.

## Foreign schedules

- FSI;
- TR under sections 90, 90A, and 91;
- Form 67;
- each Schedule FA asset category.

## Credits

- TDS self;
- TDS spouse/other person;
- brought-forward TDS;
- partial claims;
- carry-forward;
- TDS-3 buyer/tenant;
- TCS spouse/other person;
- complete Schedule IT challans.

## Precision and boundaries

- zero;
- permitted negative values;
- large values above ₹1 crore;
- decimal input;
- blank versus zero;
- duplicate rows;
- one-row and multi-row schedules;
- malformed and incomplete entries.

---

# 20. Final assessment

Taxify has meaningful architecture and broad UI coverage, including a strong canonical model and a structured CBDT serializer. The frontend build succeeds, confirming build integrity.

That success does not establish ITR-2 filing completeness. The implementation currently has a material gap between UI/model coverage and official JSON output. Before real ITR-2 filing, the project must complete the canonical serialization path and resolve the P0 findings, especially Schedule 115AD, capital gains, Schedule OS, TDS/TCS, filing profile, and negative house-property handling.

> **Final classification: broadly implemented but not production-ready for complete AY 2026–27 ITR-2 filing.**
