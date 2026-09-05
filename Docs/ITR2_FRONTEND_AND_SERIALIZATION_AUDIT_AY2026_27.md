# Taxify ITR-2 AY 2026–27 Frontend and Serialization Audit

**Audit type:** Read-only frontend and filing-pipeline audit  
**Assessment year:** AY 2026–27  
**Scope:** Frontend capture, canonical `ReturnDraft`, preparation, CBDT/ITD JSON serialization, and official-form coverage  
**Excluded:** Validators and validator-related working-tree changes  
**Status:** Not production-ready for complete real-world ITR-2 filing

> **Progress update (2026-09-04)**: this audit has moved from read-only findings-only into the
> same iterative audit-fix-reaudit cycle ITR-1/ITR-4's own audit docs used, per
> `C:\Users\Devansh\.claude\plans\zippy-juggling-sprout.md`. Phases 1-3 of that plan are now
> complete:
> - **Phase 1** (§3.1-§3.3, §3.5): capital-gains serialization — land/building rows, section
>   50C/50CA deeming, the generic "other assets" bucket for the remaining 10 `CGAssetType`
>   categories, negative-HP re-verification. One P0 (section 112(1)(a) indexed-cost-primacy) was
>   found and deliberately deferred, not silently left broken — see §3.2's write-up.
> - **Phase 2** (§3.4, §3.6, §3.7): Schedule OS winnings/accumulated-PF/gifts, and TDS/TCS
>   ownership+brought-forward+carry-forward data — all previously silently dropped despite the
>   frontend already capturing them. Found and fixed a genuine Total-Income-understatement bug
>   along the way (special-rate Schedule-SI income taxed but never added to GTI).
> - **Phase 3** (§3.8, §4.1-§4.7): every remaining filing-profile gap — 92CD, the
>   current-account-deposit gate, FII/FPI, LEI, residential-status facts, Section 115H,
>   director/unlisted-equity disclosure, and Schedule IT challan completeness. Found and fixed two
>   further schema-blocking bugs (`SEBIRegNo`/`SebiRegnNo` key mismatch; a dead
>   `CompDirectorPrvYrFlg` emission) plus a missing residential-status *selector* the frontend
>   never had at all.
>
> - **Phase 4** (P0 exit re-audit, see the dedicated section between §4 and §5): a systematic
>   key-by-key schema diff of `_part_a_gen1()` — the function every Phase 3 fix landed in — found
>   one more CRITICAL gap the Phase 3 fixes exposed: the seventh-proviso sub-flags/amounts and
>   `PortugeseCC5A` were never emitted at all, meaning §4.6's own fix was itself incomplete. Fixed
>   inline in the same pass.
>
> See each section's own "Fix status"/"Re-verified" blockquote for full evidence, regression
> tests, and `git stash` pre-fix confirmation.
>
> **Update (2026-09-05): Schedule OS's remaining P0 sub-items are now also closed.** Per explicit
> user instruction that the system must capture and process every schema field, mandatory or
> optional, §3.4's Schedule OS finding is now closed except one narrow, explicitly-tracked item
> (deeper PTI category-specific TDS linkage beyond the flat `tds_credit` field already wired; the
> PTI HP/OS-head GTI-inclusion gap itself is now fixed too) — see §3.4's "Update
> (2026-09-05)" blockquotes for the full write-up, including a full NRI Section 115A/AC/ACA/AD/E
> special-rate income module (17 new tax-rate handlers) and DTAA-rate Other Sources tax
> computation (a pre-written but never-called helper function, now wired up).
>
> **Correction to this note's own prior claim**: the sentence previously here — "every CRITICAL P0
> finding is now closed" — was inaccurate and has been removed. §3.1 (Schedule 115AD) and several
> §3.2 (capital-gains) sub-items remain genuinely open P0 findings, not merely P1 polish; see the
> consolidated open-findings list in §18 for the accurate current state. What *is* true: every P0
> finding in the **filing-profile family** (§4.1-§4.7, Phase 3/4) and in **TDS/TCS/Schedule IT**
> (§3.6-§3.8) is closed with a verified fix, and Schedule OS (§3.4) is now closed to the same
> two-item exception noted above.
>
> **Update (2026-09-05): all remaining named P0 items closed except one.** Schedule 115AD (§3.1),
> per-transaction capital-gains exemption attribution (§3.2), and the legacy-mapper duplication
> (§2.2/§1) are now all fixed — see each section's own write-up. What remains open in the
> capital-gains cluster specifically: the section-94(7)/94(8) dividend-stripping loss-disallowance
> figure (no input field captures it at all) and CYLA/BFLA/CFL's one noted discretionary-ordering
> observation (reviewed, not a proven defect — flagged for live-UAT confirmation). See §18 for the
> complete, current picture.

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

> **Fix status (2026-09-05): the confirmed-dead legacy mapper chain is removed; two adjacent
> discoveries corrected the original plan's scope.**
>
> Confirmed via live-code tracing (not just a string grep) that the ENTIRE chain --
> `frontend/src/api/itr2Mapper.ts` -> `frontend/src/api/itrCompute.ts`'s `computeItr2`/
> `computeItr2Json` -> `POST /itr2/compute`/`/itr2/compute-json` -- had zero live frontend callers:
> `itr2Mapper.ts` had zero importers anywhere in `frontend/src`, and `itrCompute.ts`'s entire
> `itrComputeApi` object (including its ITR-1/ITR-4 functions, left untouched here as out of
> scope) was in turn imported nowhere except by the now-dead `itr2Mapper.ts`. Deleted
> `itr2Mapper.ts` outright and removed `computeItr2`/`computeItr2Json`/the `ITR2Result` interface
> from `itrCompute.ts`, leaving its ITR-1/ITR-4 exports untouched. `npm run build` and `npm test`
> (186 tests) both clean after the change.
>
> A SECOND, independently dead ITR-2 flat-payload path was also found and removed in the same
> pass: `app/routers/tax.py::_compute_itr2_from_flat_payload`, dispatched from the shared
> `compute_tax_summary()`/`_compute_tax_summary_impl()` (backing the legacy `/tax-summary/compute`
> and `/api/tax/compute` routes) whenever `payload["form"] == "ITR-2"`. The live frontend only
> ever calls the canonical `/v2/tax-summary/compute` route (`tax_v2.py`) for ITR-2 -- this legacy
> endpoint's ITR-2 branch had a real, but entirely synthetic, test harness (three test files
> called it as a direct Python function, never through an HTTP client exercising the actual live
> route). Removed the function and its dispatch branch; an ITR-2-tagged request landing on this
> legacy endpoint now falls through to the SAME "provisional common-income preview" (via the
> ITR-1 engine) that ITR-3 -- which never had a flat-payload engine of its own -- already
> receives; `filing_computation_status` was already correctly set to
> `"PROVISIONAL_COMMON_INCOME_PREVIEW"` for both by the pre-existing `is_future_form` check, so no
> caller is told a real computation happened when it didn't. Also removed the now-dead
> `_itr2_filing_section()` helper and five now-unused module-level imports
> (`ITR2Input`/`CGAssetType`/`CGTransaction`/`ResidentialStatus as ITR2ResidentialStatus`/
> `ReturnFileSection` from `app.schemas.itr2`, `compute as compute_itr2` from
> `app.engine.calculators.itr2`) that existed only to support the removed function.
>
> **Correction to the plan's own prior scoping (caught before acting on it, not after): `/itr2/
> compute`/`/itr2/compute-json` in `app/routers/itr.py` are NOT dead code and were deliberately
> left untouched.** The originating plan document assumed these were "dead ... routes" alongside
> `itr2Mapper.ts`, but `tests/test_itr2_production_path.py` (its own docstring: "Production-path
> tests for ITR-2 JSON validation and routing") has real, meaningful assertions about their
> behavior -- schema-valid-document generation, HTTP 400 mapping for incomplete filing identity,
> and post-calculation validation-report inclusion. Unlike the removed flat-payload mapper, these
> two routes accept an ALREADY-TYPED `ITR2Input` body directly (no flat-payload translation
> involved at all), making them a legitimate, if currently frontend-unused, typed direct-input API
> surface -- not the "two different incomplete mappers of the same user data" problem this finding
> was originally about. Deleting them would have broken 3 passing tests for no correctness gain.
>
> **Also investigated, confirmed unaffected, not further modified**: two OTHER, unrelated callers
> of the shared `compute_tax_summary()` --
> `app/engine/filing_gateway.py::generate_filing_artifact()` (confirmed zero callers anywhere in
> `app/`, i.e. also dead, but out of scope for this fix) and
> `app/routers/client_itr.py::validate_client_itr()` (its own frontend caller,
> `frontend/src/api/validation.ts`, posts to a URL shape --
> `/clients/{clientId}/validate/{assessmentYear}` -- that does not match this endpoint's actual
> route -- `/clients/{client_id}/itr/{year}/validate` -- a separate, pre-existing routing mismatch
> unrelated to this fix, not investigated further here). Neither is exercised by any test with an
> ITR-2-tagged payload, so this fix's behavior change to `compute_tax_summary()` does not affect
> any passing test through either path.
>
> Regression test: `test_tax_summary_legacy_endpoint_redirects_itr2_cg_evidence_to_itr2_or_itr3`
> (`tests/test_ay2026_calculator_regressions.py`, replacing
> `test_tax_summary_preserves_imported_cg_evidence_without_taxing_it`, which explicitly tested the
> now-removed ITR-2 computation branch) confirmed via `git stash` to fail
> (`DID NOT RAISE HTTPException`) on pre-fix code. Full combined backend regression suite (388
> tests, including all of `test_itr2_production_path.py`, `test_ay2026_calculator_regressions.py`,
> `test_integration_routers.py`, `test_purchase_evidence_filtering.py`) green; the 3 failures in
> `tests/test_tax_v2_compute.py` are confirmed pre-existing baseline failures (fail identically
> with `git stash` on/off this change), not caused by this fix.

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

> **Fix status (2026-09-05): fixed and verified — the prior re-verification's own conclusion
> ("genuinely cannot be populated with today's schema... residency status alone is insufficient")
> was itself wrong and is retracted.** Section 115AD applies based on the ASSESSEE's FII/FPI
> registration status, a whole-taxpayer classification -- not a per-transaction one. Once this was
> understood correctly, no new `CGAssetType` enum value or per-transaction flag was needed at all:
> `ITR2FilingProfile.is_fii_fpi` (already implemented for §4.2's FII/FPI filing-profile checkbox)
> is exactly the right discriminator, and simply routing an FII/FPI assessee's existing
> `CGTransaction`/`CG112AScrip` classifications to the parallel 115AD-specific fields closes this
> finding completely.
>
> Cross-referenced the full official form text (Schedule CG items A2-A4 for STCG, B3-B6 for LTCG,
> `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng_extracted_text.txt` lines
> 285-330, 558-626) and the official schema's `EquityOrUnitSec94Type`/`EquityShareUs112A`
> `$ref` reuse (`NRISecur115AD` and `SaleOnOtherAssets` share the identical type; likewise
> `NRISaleOfEquityShareUs112A`/`SaleOfEquityShareUs112A`) to confirm section 115AD reuses the same
> field SHAPES as the ordinary buckets — it is a parallel disclosure slot, not a structurally
> different schedule. The official form's own Schedule SI rate table (rows 2/3/8/11) additionally
> confirms every 115AD-specific rate is IDENTICAL to its ordinary counterpart (111A-equivalent
> 20%, 112A-equivalent 12.5%, LTCG-other 12.5%) with exactly one exception: 115AD(1)(ii) STCG on
> securities where STT is NOT paid is a flat 30% special rate for an FII/FPI -- unlike an ordinary
> taxpayer's identical basket, which is slab-rate, never a flat special rate. This is the one
> genuine COMPUTATION change (not just disclosure-routing) this fix required.
>
> Implementation:
> - `app/engine/schedules/special_rates.py`: four new `SpecialRateSection` codes
>   (`S115AD_STCG_111A="5AD1biip"`, `S115AD_STCG_OTHER="5ADii"`, `S115AD_LTCG_OTHER="5ADiii"`,
>   `S115AD_LTCG_112A="5ADiiiP"`), three added to `_SURCHARGE_CAP_SECTIONS` (matching their
>   ordinary counterparts' cap treatment; the 30% STCG-other code is deliberately excluded, same as
>   VDA), and a new `compute_115ad_stcg_other()` function for the one genuinely new rate.
> - `app/engine/calculators/itr2.py`: a new `is_fii_fpi` flag derived from
>   `input_data.filing_profile.is_fii_fpi`. The existing `compute_111a()`/`compute_112a_taxable()`/
>   `compute_112()` calls are unchanged (same rates); their resulting `SpecialRateEntry.section` is
>   simply relabeled to the FII-specific code when `is_fii_fpi` is true. The one new dispatch is
>   `compute_115ad_stcg_other(post_loss_cg["normal_stcg"])`, added to Schedule SI only when
>   `is_fii_fpi` -- for every other taxpayer type this exact same basket remains correctly
>   slab-rate (unchanged), since `special_rate_income_for_slab`'s existing
>   `si_result.surcharge_full_income` mechanism (already used for 115BB/115BBE/etc.) automatically
>   excludes it from the slab base once it is SI-dispatched, with no separate double-subtraction
>   needed.
> - `app/engine/itd/itr2.py`: `_schedule_cg()` now derives `is_fii_fpi` and routes accordingly --
>   `EquityMFonSTT`'s `MFSectionCode` (`"5AD1biip"` vs `"1A"`), the 112A summary (`gain_112a` now
>   populated from the real `compute_112a()` result instead of a hardcoded zero, routed to
>   `NRISaleOfEquityShareUs112A` or `SaleOfEquityShareUs112A`), and the generic "other assets"
>   bucket, newly split by a `_FII_SECURITIES_ASSET_TYPES` subset (`unlisted_shares`,
>   `listed_security`, `debt_mutual_fund`, `specified_mutual_fund_50aa`,
>   `market_linked_debenture_50aa`, `bonds_debentures` -- genuine "securities"; `jewellery`,
>   `depreciable_asset`, `foreign_asset`, `other` are NOT securities under 115AD and always stay in
>   the ordinary bucket regardless of FII/FPI status) routed to `NRISecur115AD` (STCG) or
>   `NRIOnSec112and115Dtls[SectionCode="5ADiii"]` (LTCG, omitted entirely when empty per the
>   project's no-placeholder convention, since that array is schema-optional unlike its STCG
>   sibling). `_other_assets_block()` gained an `asset_types` parameter to support calling it twice
>   with disjoint sets.
> - **A genuinely separate, non-FII-specific bug was found and fixed in the same pass**:
>   `SaleOfEquityShareUs112A` (Schedule CG item 3a/3c, "LTCG u/s 112A (column 14 of Schedule
>   112A)") was hardcoded to zero regardless of ANY taxpayer's actual 112A gain -- a resident with
>   genuine 112A gains would see this summary field as zero even though the dedicated
>   per-scrip `Schedule112A` block and the actual Schedule-SI tax were both already correct. Fixed
>   by populating it from `ltcg.income_112a` (the gross, pre-threshold aggregate, matching "column
>   14" -- the ₹1.25L threshold is a separate Schedule-SI-only adjustment, not applied to this
>   disclosure figure) for a non-FII taxpayer.
>
> **Known, explicitly documented limitation**: the "other securities" STCG/LTCG baskets
> (`post_loss_cg["normal_stcg"]`/`post_loss_cg["112"]`) blend EVERY generic-other asset type
> together after loss set-off -- if an FII/FPI assessee holds a non-securities asset (jewellery
> etc.) in the same return as genuine 115AD securities (statutorily unusual but not
> schema-forbidden), the blended SI entry is relabeled entirely to the FII-specific SecCode even
> though a portion is technically ordinary section-112/slab income. The TAX AMOUNT is unaffected
> (both codes share the identical rate), only the SecCode attribution can be imprecise in this
> edge case; splitting it exactly would require tracking an FII-securities-vs-other sub-basket
> through CYLA/BFLA/`_post_loss_cg_baskets()`, a materially larger change not attempted here.
> Documented in code comments at both dispatch points.
>
> **Known pre-existing bug found in passing, NOT fixed (out of scope for this pass)**: the
> official schema's `EquityMFonSTT` array has `maxItems: 2` (one row per distinct `MFSectionCode`),
> but `_schedule_cg()` emits one row PER TRANSACTION -- a taxpayer with 3+ separate 111A-eligible
> transactions would already exceed this limit and fail schema validation, independent of this
> fix (this fix only changes which single `MFSectionCode` value such rows carry, since an
> assessee is never both FII and non-FII in the same return). Flagged here as a newly-found item
> for a future pass, not expanded into this fix's scope.
>
> Regression tests: `test_sale_of_equity_share_us112a_reflects_real_gain_not_hardcoded_zero` and
> `test_fii_fpi_capital_gains_route_to_section_115ad_fields_and_si_codes` (both in
> `tests/test_itr2_itd_builder.py`), confirmed via `git stash` to fail on pre-fix code. Full
> combined `test_itr1_*`/`test_itr4_*`/`test_itr2_*`/`test_standalone_cg_schedule.py`/
> `test_capital_gains_loss_foundation.py` regression suite (322 tests) green.

> **Fix status (2026-09-05): per-transaction §54/54B/54EC/54F/115F exemption attribution is now
> implemented** (the item flagged in §3.2's "Remaining, deliberately not attempted" list). The
> data was already fully captured per-transaction — `CGTransaction.exemptions: List[
> CapitalGainExemptionClaim]`, an evidence-backed claim structure (investment/CGAS-deposit amount,
> dates, CGAS account/IFSC) — but only the AGGREGATE `_claim_total()` sum reached
> `DeducClaimInfo.TotDeductClaim`; individual Schedule CG rows always showed the pre-exemption gain
> as if no claim existed, and the five `DeducClaimDtlsUs{54,54B,54EC,54F,115F}` detail arrays were
> always empty.
>
> **Deliberate architectural choice, confirmed correct before implementing**: exemption
> attribution here is a DISCLOSURE-granularity fix only, not a tax recomputation. The actual
> taxable total was already correct — computed once via the existing aggregate-level
> `compute_exemptions()`/`eligible_exemption` mechanism (confirmed: `eligible_exemption =
> min(positive_ltcg, exemptions.total_exemption)`, applied exactly once in `aggregate()`). Making
> individual rows ALSO subtract their own exemption from the SAME real gain figures used in that
> aggregate (rather than only from a separate disclosure copy) would have double-counted the
> exemption. So each row's PRIMARY gain field (`Balance`/`BalanceCG`, "1c"/"5c") is left untouched
> — still feeding the real aggregate/tax pipeline unchanged — while a NEW post-exemption field
> (`LTCGonImmvblPrprty`/"1e", `CapgainonAssets`/"5e") is computed purely for disclosure, matching
> the official form's own item-lettering distinction between the pre- and post-exemption figures.
>
> Implementation:
> - `app/engine/schedules/capital_gains.py`: `CGAsset` gained an `exemptions` field (the
>   transaction's own claim list, threaded through by `_classify()`) and an `exemption_total`
>   field (computed by `compute_stcg()`/`compute_ltcg()`: §54B only for STCG land/building, per
>   the form's own item 1d; §54/54B/54EC/54F for LTCG land/building, per item "1d").
> - The section 112(1)(a) second-proviso relief comparison (§3.2's earlier fix, same session) was
>   ALSO corrected in the same pass: the official form bases "ei(A)"/"ei(B)" on the POST-exemption
>   "1e"/"1ea" figures, not the pre-exemption "1c"/"1ca" the relief comparison previously used
>   (documented at the time as a known simplification pending this exact fix) — now both tracks
>   subtract the same `exemption_total`.
> - `app/engine/itd/itr2.py`: new `_exemption_or_dedn_us54_block()` builds land/building's
>   per-code `ExemptionOrDednUs54Dtls` array (omitted entirely, not empty-array-emitted, when the
>   asset has no claims — only `ExemptionGrandTotal` is schema-required); the generic-other LTCG
>   bucket (`_other_assets_block`) and the 112A summary block each gained their own §54F
>   attribution (54F is the only §54-series section applicable to either, per the form's own
>   items 5d/8d and 3b); new `_deduction_claim_detail_rows()` populates all five top-level
>   `DeducClaimDtlsUs*` arrays by scanning every transaction's claims for one section, independent
>   of which Schedule CG bucket the transaction belongs to.
> - **Known, narrower limitation**: `CG112AScrip` (the explicit Schedule-112A-detail path used via
>   `cg_112a_scrips`, distinct from a 112A-classified `CGTransaction`) has no `exemptions` field at
>   all, so a 54F claim against an explicit scrip entry isn't representable yet — a separate,
>   smaller gap than this fix's scope, not expanded into it.
> - The section 94(7)/94(8) dividend-stripping loss-disallowance figure (a distinct concept from
>   §54-series exemptions) remains unrepresented — Taxify has no input field capturing it at all;
>   not attempted here.
>
> Regression test: `test_per_transaction_exemption_claims_reduce_own_row_and_populate_detail_arrays`
> (`tests/test_itr2_itd_builder.py`) — asserts both the per-row disclosure figures AND that the
> real `total_capital_gains` is unchanged by this fix (still driven by the one existing
> aggregate-level mechanism) — confirmed via `git stash` to fail on pre-fix code. Full combined
> `test_itr1_*`/`test_itr4_*`/`test_itr2_*`/`test_standalone_cg_schedule.py`/
> `test_capital_gains_loss_foundation.py` regression suite (323 tests) green.

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
> **Remaining, deliberately not attempted**: ~~per-transaction §54/54B/54EC/54F exemption
> attribution to this bucket's `LossSec94of7Or94of8`/`DeductionUs54F` fields~~ — **fixed
> 2026-09-05**, see the dedicated write-up below (after §3.1's Schedule 115AD fix). The section
> 94(7)/94(8) dividend-stripping loss-disallowance figure remains open (Taxify has no input field
> capturing this at all — a distinct concept from §54-series exemptions, not attempted here). Also
> unaffected: §3.1's 115AD-specific fields (`NRISecur115AD`, `NRISaleOfEquityShareUs112A`) — see
> §3.1's own fix write-up, since the "requires a `CGAssetType`/FII-flag schema extension"
> conclusion here was also corrected there.
>
> **Fix status (2026-09-05): the section 112(1)(a) indexed-cost-primacy defect (flagged above as
> "New P0 item found 2026-09-04") is now fixed, including the full second-proviso relief, not just
> the primary-balance correction.** Per the official form's own text (Schedule CG item 1,
> `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng_extracted_text.txt` lines
> 459-522): the primary declared LTCG ("1c"/`Balance`) must always use the non-indexed cost;
> `compute_ltcg()` (`app/engine/schedules/capital_gains.py`) previously preferred the indexed cost
> whenever supplied, understating the declared gain (and tax) any time indexed cost exceeded
> actual cost — the common case. Fixed by removing the indexed-cost preference from the primary
> `Balance`/`TotalDedn` computation entirely.
>
> This also implements the previously-unattempted second-proviso comparison itself, not just the
> primary-balance fix: a resident (`CGAsset.eib_applicable`, true for RES/NOR — NRI excluded — with
> `date_of_acquisition` before 23-Jul-2024) gets a per-row comparison of two tax figures —
> `TaxSec1121a` (12.5% × non-indexed gain) vs `TaxSec1121aiiB` (20% × indexed gain, `BalanceForEiB`,
> floored at nil per the form's own "in case of negative, to be considered as nil") — with the
> excess of the former over the latter (`ExcessAmtSec1121a`) disclosed per row and aggregated as
> `SaleofLandBuild.TotalExcessTax` (both previously hardcoded/omitted placeholders). Critically,
> this relief is not merely disclosed: `calculators/itr2.py::compute()` subtracts
> `ltcg_result.total_excess_tax_112_1a` from the actual Schedule SI section-112 tax figure (capped
> at that bucket's own computed tax, never negative) — a self-assessed return declares tax
> liability *inclusive* of every relief the law allows, so a JSON-only disclosure that didn't
> reduce the actual payable amount would itself have been a new, distinct bug (Schedule CG
> claiming a relief that Part B-TTI's tax figure doesn't reflect).
>
> **Known, explicitly documented simplification**: the relief is capped at the actual computed
> section-112 tax rather than proportionally attributed across land/building vs. the generic-other
> LTCG sub-basket that `_post_loss_cg_baskets()` blends together after loss set-off and exemption
> consumption — that function doesn't track the two sub-baskets separately post-loss-setoff, and
> building that separate tracking is a larger undertaking than this fix's scope. The cap means the
> relief can never exceed what was actually taxed (never manufactures a negative tax or an
> impossible over-relief), but in a return that also has current-year/brought-forward losses or
> §54-series exemptions consuming part of the section-112 bucket, the relief actually granted may
> be a conservative (i.e., not necessarily exact-to-the-rupee) approximation. Documented here
> rather than silently assumed exact; a return with no such losses/exemptions on the 112 bucket
> (the common case for a standalone land/building sale) computes this relief exactly.
>
> Also similarly simplified, consistent with the pre-existing per-row exemption limitation
> documented above: the per-row comparison itself uses each row's gross balance, not a
> post-exemption one (no per-row §54/54B/54EC/54F attribution exists yet) — this can only ever
> make the computed relief a lower-bound estimate, never an overstatement, since a real per-row
> exemption would shrink both the 12.5% and 20% tax figures together.
>
> Regression tests: `test_compute_land_building_long_term_uses_non_indexed_cost_as_primary`
> (renamed/corrected from the old `..._uses_indexed_cost`, which had encoded the bug's own wrong
> expectation), `test_compute_land_building_section_112_1a_second_proviso_relief`,
> `test_compute_land_building_section_112_1a_not_applicable_for_non_resident` (in
> `tests/test_standalone_cg_schedule.py`), and
> `test_land_building_section_112_1a_relief_reduces_actual_si_tax` plus corrected assertions in
> `test_land_building_stcg_and_ltcg_rows_are_schema_valid_with_correct_fields` (in
> `tests/test_itr2_itd_builder.py`) — the latter proving the relief reaches the actual
> `ScheduleSI.SplCodeRateTax` tax figure, not just Schedule CG's disclosure fields. All confirmed
> via `git stash` to fail on pre-fix code. Full combined `test_itr1_*`/`test_itr4_*`/`test_itr2_*`/
> `test_standalone_cg_schedule.py`/`test_capital_gains_loss_foundation.py` regression suite (318
> tests) green; ITR-1/3/4's shared `compute_ltcg()`/`compute()` call sites were checked and remain
> unaffected (they default `is_resident=False` and, for ITR-1/4, never surface land/building LTCG
> at all via `project_restricted_112a`'s own aggregation).

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
>
> **Update (2026-09-05): every item deliberately deferred above has now
> been closed**, per explicit user instruction that the system must
> capture and process every schema field, mandatory or optional, not just
> the highest-frequency ones. Specifically:
> - **Unexplained income** (§68/69/69A/69B/69C/69D, `UnexplainedIncomeDetails`
>   -- previously not wired at all): new `OSUnexplainedIncome` type on
>   `ITR2Input`, its total combined with any `UNEXPLAINED_115BBE`-type
>   winnings into one 115BBE Schedule-SI entry (both sources feed the same
>   bucket, not two competing entries), and each of the 8 sub-fields
>   individually disclosed in the JSON.
> - **Section 89A** (foreign-retirement-account deferral): aggregates
>   (notified/other/prior-year/relief) plus the per-country
>   `IncomeNotified89ATypeOS` array now wired from `Section89AAggregates`/
>   `Section89AEntry`. Deliberately NOT added to current-year taxable
>   income -- notified income is a statutory deferral by definition.
> - **Dividend section/quarter breakdown**: `DividendIncome` rows (previously
>   collapsed into one undifferentiated aggregate) now drive the
>   `Dividend22e`/`Dividend22f`/`DividendOthThan22e` split and all 8
>   top-level `DividendDTAA`/`DividendIncUs115*` date-range fields with real
>   quarterly data.
> - **DTAA-rate OS income**: the aggregate (`IncChargblSplRateOS.
>   TotalAmtTaxUsDTAASchOs`) and full `NRIDTAADtlsSchOS` per-entry detail
>   (country, article, treaty/Act/applicable rates, tax-residency
>   certificate) now wired from `dtaaAggregates`/`dtaaIncome`. Disclosure
>   only -- correctly computing NRI-specific DTAA tax rates per treaty
>   article is a separate, larger undertaking not attempted here (see the
>   new finding below on `SpecialRateIncomeEntry` for the same boundary).
> - **Schedule OS deductions**: `Expenses`/`Depreciation`/`IntExp57`/
>   `UsrIntExp57`/`AmtNotDeductibleUs58`/`ProfitChargTaxUs59` now wired from
>   `OtherSourcesDeductions`; `DeductionUs57iia` now reads the calculator's
>   own already-correct `compute_os()` result (`OSResult.deduction_57iia`)
>   instead of a hardcoded zero.
> - **Race-horse activity** (`IncFromOwnHorse`): `RACE_HORSE_ACTIVITY`-type
>   `WinningIncome` rows now map to a new `OSRaceHorseActivity` type, with
>   the net profit (never a loss, per section 74A(3)'s no-set-off rule)
>   added to GTI as slab-rate Other Sources income -- this required a small
>   calculator change (`compute()` now adds `max(0, balance)`), plus a
>   correction to `BalanceNoRaceHorse`/`TotOthSrcNoRaceHorse` (which must
>   exclude the race-horse profit per their own naming, previously computed
>   identically to the now-inclusive `IncChargeable` total) and to the
>   top-level `IncChargeable` field (previously hardcoded `0`, now the true
>   grand total including race-horse profit).
> - **PF-interest-proviso categorization** (`IntrstSec10XIFirstProviso`/
>   `SecondProviso`/`IntrstSec10XIIFirstProviso`/`SecondProviso`, Budget
>   2021's taxable-above-threshold PF interest): computed independently
>   from `draft.otherSources.interest`'s `PF_10_11_FIRST`/etc. kinds rather
>   than the shared `_map_other_sources()` helper, which collapses them
>   into the generic `other_income` aggregate for ITR-1's purposes.
> - **`IncFrmLottery`/`IncFrmOnGames` quarterly breakdown**: real Q1-Q5
>   sums from lottery/betting/card-game/horse-race and online-gaming
>   `WinningIncome` rows respectively, replacing the all-zero placeholder.
>
> **New finding surfaced while implementing, deliberately left open and
> explicitly flagged (not silently folded into "done")**:
> `SpecialRateIncomeEntry`/`OthersGrossDtls` (the ~20-category NRI-specific
> Section 115A/115AC/115ACA/etc. special-rate income bucket) genuinely
> requires ~20 new statutory tax-rate handlers this codebase has never
> implemented -- this is categorically different from every item above
> (which needed only data wiring against calculator logic that already
> existed correctly). Wiring the JSON disclosure alone without the
> matching tax computation would misrepresent the return as complete while
> leaving tax liability wrong, which is worse than not wiring it at all.
> This -- and the DTAA-rate NRI tax computation noted above -- join §3.1's
> Schedule 115AD as the project's now-consolidated list of "genuinely
> requires new NRI/FII-specific tax logic" follow-up items, tracked for
> Phase 5+ rather than deferred as merely "optional."
>
> **Correction (same day): `RentFromMachPlantBldgs` was NOT actually a
> frontend gap.** `ScheduleOSWorkspace.tsx` already has full UI for it --
> its "other income" row editor lets a row be tagged `nature ===
> 'MACHINERY_RENT'` (labeled exactly "RentFromMachPlantBldgs — Rent from
> machinery, plant or building" in the dropdown) and reuses the existing
> `Deductions` UI (already wired above) for its expenses/depreciation.
> `PASS_THROUGH`-tagged rows (labeled "NatofPassThrghIncome") exist in the
> same editor too. Both were being silently absorbed into the generic
> "any other income" bucket by the mapper rather than routed to their own
> fields -- fixed by filtering `MACHINERY_RENT`/`PASS_THROUGH`-tagged rows
> out of the generic aggregate (in both this mapper's own detail-row list
> *and* the shared `_map_other_sources()` aggregate it reuses, which would
> otherwise double-count machinery-rent income once gross, once net of its
> deductions) and routing them to `RentFromMachPlantBldgs` (net of
> Expenses/Depreciation/interest-u/s-57, added to GTI, floored at zero)
> and `NatofPassThrghIncome` (pure disclosure -- already taxed as ordinary
> income "at normal rate" per the frontend's own label) respectively.
>
> Regression tests: `test_schedule_os_serializes_unexplained_income_89a_deductions_and_dtaa`,
> `test_schedule_os_serializes_dividend_section_breakdown`,
> `test_schedule_os_serializes_race_horse_activity_and_includes_net_profit_in_gti`,
> `test_schedule_os_omits_optional_blocks_when_unset` (in
> `tests/test_itr2_itd_builder.py`), and
> `test_unexplained_income_maps_to_115bbe_si_entry_and_is_taxed`,
> `test_unexplained_income_combines_with_115bbe_winnings_into_one_entry`,
> `test_dividend_dtaa_89a_other_income_and_deductions_map_correctly`,
> `test_race_horse_activity_winnings_map_to_os_race_horse`,
> `test_pf_interest_proviso_kinds_map_to_dedicated_fields` (in
> `tests/test_draft_to_itr2_input.py`), all confirmed via `git stash` to be
> absent on pre-fix code. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> suite (299 tests) green.
>
> **Update (2026-09-05): the `SpecialRateIncomeEntry`/`OthersGrossDtls` NRI
> special-rate income module (flagged above as a deliberately-open "new
> finding") is now implemented end-to-end**, per the same explicit user
> instruction driving this whole batch, extended by the user's own choice
> ("Implement both now, including the full NRI Section 115A tax-rate
> module") when asked to prioritize between this and `RentFromMachPlantBldgs`
> (which turned out to already have frontend UI, see the correction above).
> This required genuinely new tax-computation logic, not just data wiring:
> - 17 new `SpecialRateSection` enum values and a `_OTHER_SPECIAL_RATE_TABLE`
>   dispatch table in `app/engine/schedules/special_rates.py`, covering the
>   full official `OthersGrossDtls.SourceDescription` dropdown (Section
>   115A(1)(a)(i)/(A)/(ii)/(iia)/(iiaa)/(iiaa proviso)/(iiaa second
>   proviso)/(iiab)/(iiac)/(iii), 115A(1)(b), 115AC(1)(a)/(b), 115ACA(1)(a),
>   115AD(1)(i) dividend/non-dividend/proviso) plus the pre-existing
>   115BBF/115BBG/115E(a)/115BBA handlers for the four codes that dispatch
>   to their own functions instead of the generic table.
> - New `OSSpecialRateEntry` schema type and `os_special_rate_entries` field
>   on `ITR2Input` (`app/schemas/itr2.py`); mapped from
>   `draft.otherSources.specialRateIncome` (a pre-existing `ReturnDraft`
>   field from an earlier phase that had never been wired into the v2
>   pipeline) via `_map_os_special_rate_entries()` in
>   `app/engine/draft_to_itr2_input.py`.
> - Calculator dispatch (`compute()` in `app/engine/calculators/itr2.py`):
>   each entry is taxed via Schedule SI at its statutory rate, and — since
>   `os_special_rate_entries` is a field entirely separate from
>   `input_data.si_entries` (the pre-existing `_OS_HEAD_SI_SECTIONS` GTI
>   inclusion only scans the latter) — a **second, independent GTI-inclusion
>   step** was required, adding the gross total directly to
>   `r.other_sources_income`. This was caught before shipping, not found as
>   a live bug: the entries would otherwise have been taxed correctly via
>   Schedule SI while silently never reaching Gross Total Income at all,
>   the same "computed but not added to GTI" bug class documented for gifts/
>   winnings/race-horse/machinery-rent above.
> - Builder emission (`_schedule_os()` in `app/engine/itd/itr2.py`):
>   `OthersGross` (sum) and `OthersGrossDtls[]` (per-entry `SourceDescription`/
>   `SourceAmount`) now populated instead of the permanent zero/empty
>   placeholder; `IncChargeableSpecialRates` (also previously a hardcoded
>   zero placeholder, not part of the original 8 CRITICAL findings but the
>   exact same bug pattern, fixed in the same sitting since it aggregates
>   the same "special rate" OS sub-categories this fix touches) now sums
>   `LtryPzzlChrgblUs115BB + IncChrgblUs115BBJ + IncChrgblUs115BBE +
>   OthersGross`; the early-return guard extended with
>   `os_special_rate_entries` (the same guard-completeness bug class found
>   for every other new field this session — a test with only this field
>   populated would otherwise silently omit the whole Schedule OS block).
>
> **Confidence flag for a future live-UAT/ITD cross-check**: 10 of the 17
> new rates were confirmed directly against the official ITR-2 form PDF's
> own Schedule SI rate table (`Reference Docs by CBDT & ITD/Official ITR
> FORMS/`, read as page images for rows 15-16 since `pdfplumber` text
> extraction silently dropped several inline "@X%" annotations — this is
> also how the pre-existing assumption of a 10% royalty/FTS rate was caught
> and corrected to the form's actual 20%). The remaining 7 — `5A1aii`
> (interest from govt/Indian concern in foreign currency, 20%), `5A1aiia`
> (Infrastructure Debt Fund interest, 5%), `5A1aiiab` (§194LD interest, 5%),
> `5A1aiiac` (business-trust-distributed §194LBA interest, 5%), `5A1aiii`
> (UTI/mutual-fund foreign-currency unit income, 20%), `5AD1i` (FII income
> other than dividend, 20%), and `5AD1iP` (FII §194LD bond/govt-security
> interest, 5%) — use well-established general statutory knowledge of
> Section 115A/115AD rather than an inline form-PDF confirmation, since the
> form's own printed rate table does not itemize every one of these
> narrower sub-clauses individually. Recommend a live ITD Type-2 UAT
> `validateItr` cross-check (Phase 12) before relying on these 7 specific
> rates for a real filing — the same "static cross-referencing does not
> prove correctness, only a live call does" discipline this project's own
> CLAUDE.md already states for the Digest computation.
>
> **Correction (same day): DTAA-rate NRI tax computation was NOT actually a
> "separate, larger undertaking" as first assessed above.** On closer
> inspection, `OSDtaaEntry`/`NRIDTAADtlsSchOS` already carries its own
> per-entry `applicable_rate` field (the section 90(2) beneficial
> treaty-vs-Act rate, entered directly by the preparer per DTAA article --
> not something this codebase needs to derive from a treaty-rate lookup
> table), and `app/engine/schedules/special_rates.py::compute_dtaa_os()`
> already existed, pre-written but never called from anywhere. The actual
> gap was the same "computed but never reaches GTI/Schedule SI" pattern as
> every other item in this section, just not yet recognized as such. Fixed
> by dispatching each `os_dtaa_entries` row through `compute_dtaa_os(amount,
> applicable_rate)` in the calculator (a new Schedule SI "DTAAOS" entry per
> row, since a taxpayer can hold DTAA income taxed at different treaty
> rates across countries/articles) and adding a second, independent
> GTI-inclusion step (same reason as the `os_special_rate_entries` one
> above: this field is not covered by `_OS_HEAD_SI_SECTIONS`, which only
> scans `input_data.si_entries`). Builder-side, `_schedule_si()`'s
> `section_code_map` gained the `"DTAAOS": "DTAAOS"` identity mapping; no
> other builder change was needed since `NRIDTAADtlsSchOS` disclosure was
> already correct.
>
> **Known constraint, not fixed here** (an ITD schema property, not a bug
> in this codebase): the official schema's `ScheduleSI.SplCodeRateTax[].
> SplRatePercent` is a closed enum (`{1, 4, 5, 9, 10, 12.5, 15, 20, 25, 30,
> 50, 60}`), not a free-form percentage. A treaty `applicable_rate` outside
> this set (an unusual but real possibility -- some DTAAs specify rates
> like 7.5%) will fail schema validation at compute time. This is the
> correct fail-closed behavior per this project's own convention (matching
> the pre-existing section-111 zero-rate schema bug documented above), not
> a gap to silently work around by rounding/clamping the rate.
>
> Regression tests:
> `test_schedule_os_serializes_nri_special_rate_entries_and_taxes_them_via_si`,
> `test_schedule_os_dtaa_entries_are_taxed_via_si_at_applicable_rate_and_reach_gti`
> (in `tests/test_itr2_itd_builder.py`), and
> `test_special_rate_income_entries_map_and_are_taxed_at_correct_nri_rate`,
> `test_special_rate_income_zero_amount_rows_are_excluded`,
> `test_dtaa_os_income_is_taxed_at_applicable_rate_and_reaches_gti` (in
> `tests/test_draft_to_itr2_input.py`), confirmed via `git stash` to fail
> on pre-fix code (an `ImportError` for the special-rate-entries tests;
> a wrong-GTI/missing-SI-entry `AssertionError` for the DTAA tests, stashing
> only the two DTAA-specific implementation files while keeping the tests).
> Full combined `test_itr1_*`/`test_itr4_*`/`test_itr2_*` regression suite
> (307 tests) green.

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

> **Fix status (2026-09-04): fixed and verified.** This item is shared with ITR-1
> (`app/engine/itd/itr1.py::_tax_payments_from_input` has the identical raise-with-no-field-detail
> pattern as ITR-2's `_schedule_it`), so both forms were fixed and tested together per CLAUDE.md's
> scope boundary.
>
> A complete challan editor **already existed** (`frontend/src/pages/ITRComputationTabs.tsx`,
> BSR code/deposit date/challan serial number/amount, shared by both forms) — the actual gaps were
> narrower than "use a complete editor":
> 1. **Frontend validation was cosmetic only.** The editor showed red inline `aria-invalid` text
>    via regex checks but had no blocking gate anywhere — an incomplete row could be saved and
>    submitted, surfacing only as the backend's opaque exception at generate/submit time. Added a
>    real blocking check to `validateCbdtFrontendFields()` (`domain/returns/filingPreflight.ts`) —
>    the same pre-flight gate `handleGenerateCbdtJson` (`ITRComputationPage.tsx`) already calls and
>    blocks on for every other CBDT-constrained field (PAN, TAN, bank accounts, etc.) — so an
>    incomplete challan row now surfaces the same actionable, pre-submit toast as those checks
>    always have, instead of reaching the backend at all.
> 2. **Backend errors had no per-row/per-field detail.** `_schedule_it()`'s
>    `raise ValueError("Schedule IT payment requires BSR code, date, and challan serial number")`
>    named neither the row nor which of the three fields was actually missing. Both existing call
>    paths already resolved this to a clean HTTP 400 (`routers/itr.py`'s explicit
>    `except ValueError`, `filing_gateway_v2.py`'s `FilingGatewayV2Error` wrapping), so this was a
>    message-quality fix, not a 500-prevention fix. Rewrote both `_schedule_it()` (ITR-2) and
>    `_tax_payments_from_input()` (ITR-1) identically to report `"Tax payment entry #N is missing:
>    <field list>."`.
> 3. **Reconciliation** (`ScheduleIT.TotalTaxPayments` vs. Part B-TTI's taxes-paid total) was
>    traced end-to-end rather than assumed: `app/engine/calculators/itr2.py`'s
>    `detailed_advance`/`detailed_self_assessment` are computed by summing the *same*
>    `input_data.tax_payment_entries` list `_schedule_it()` serializes (split by `payment_type`),
>    and both derive from `draft.taxes.challans` through the same shared mapper
>    (`_map_tax_payments`, `draft_to_itr1_input.py`, reused by ITR-2). Confirmed already
>    structurally consistent for the actual product path — no new validator added, since the one
>    theoretical divergence (directly constructing `ITR2Input` with `tax_payment_entries` and an
>    inconsistent separate `advance_tax_paid`/`self_assessment_tax_paid` scalar) is not reachable
>    through the mapper any real caller uses.
>
> Regression tests: `test_schedule_it_serializes_complete_challan_rows` and
> `test_schedule_it_incomplete_challan_error_names_row_and_missing_fields`
> (`tests/test_itr2_itd_builder.py`), `test_incomplete_challan_error_names_row_and_missing_fields`
> (`tests/test_itr1_itd_builder.py`), and a new frontend vitest case in
> `frontend/src/domain/returns/filingPreflight.test.ts`, all confirmed via `git stash` to be absent
> (or, for the vitest count, present-and-passing pre-fix at 12 tests vs. 13 post-fix) on pre-fix
> code. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite (287 tests) green; frontend `npm test`
> (186 tests) and `npm run build` clean.

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

> **Fix status (2026-09-04): fixed and verified.** Re-audit at implementation time found an even
> more basic gap than the one originally documented: `PersonalInfoTab.tsx` had **no residential-
> status selector at all** — `draft.personal.residentialStatus` (ROR/RNOR/NR) was set nowhere in
> the ITR-2 filing form itself, only read by `eligibility.ts`/`itr2Mapper.ts` elsewhere. Added the
> selector first, then the full supporting-facts questionnaire.
>
> New fields (all optional per the official schema — only bare `ResidentialStatus` is required):
> `conditionsResStatus` (Section 6 basis code 1-9), `jurisdictionResidenceEntries` (new
> `JurisdictionResidenceEntry` repeatable row: country + TIN, reusing the existing
> `ITD_COUNTRY_CODES` dropdown already used for postal addresses), `totalStayIndiaPrevYr` (0-365),
> `totalStayIndia4PrecYr` (0-1461) — added to `FilingStatus` (`return_draft.py`) and
> `ITR2FilingProfile` (`app/schemas/itr2.py`), wired through `_itr2_filing_profile()`
> (`filing_gateway_v2.py`), emitted as `ConditionsResStatus`/`JurisdictionResPrevYr.
> JurisdictionResPrevYrDtls[]`/`TotalPrStayIndiaPrevYr`/`TotalPrStayIndia4PrecYr` in
> `_part_a_gen1()` (`itd/itr2.py`), each only when set. Frontend section gated on
> `residentialStatus !== 'ROR'` (matches this remediation's own "conditional questionnaire"
> suggestion — day-count/jurisdiction facts are only meaningful for NRI/RNOR).
>
> §4.4's `BenefitUs115HFlg` was implemented in the same pass (see below) since it lives in the
> identical schema block and is logically tied to residential status.
>
> Regression tests: `test_generate_cbdt_json_itr2_emits_residential_status_facts` and
> `test_generate_cbdt_json_itr2_omits_residential_status_facts_when_unset` in
> `tests/test_filing_gateway_v2_itr2.py`, confirmed via `git stash` to be absent on pre-fix code.
> `npm run build` clean. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite (281 tests) green.

## 4.2 FII/FPI and SEBI information is incomplete

The backend emits `FiiFpiFlag` and optionally `SEBIRegNo` around `itr2.py:132–137`, but the frontend does not provide a complete workflow for all associated information and income classification.

**Severity: High**

> **Fix status (2026-09-04): fixed and verified.** Re-audit at implementation time found the
> backend/builder path was already fully wired end-to-end
> (`filing_gateway_v2.py::_itr2_filing_profile` already reads `draft.filing.isFiiFpi`/
> `sebiRegistrationNumber` into `ITR2FilingProfile`) — only the frontend control to actually set
> these draft fields was missing, and no test exercised the path at all. Added a checkbox + SEBI
> registration number field to `PersonalInfoTab.tsx` (gated `itrForm === 'ITR-2'`).
>
> **A real, pre-existing schema-blocking bug was found and fixed while adding the first end-to-end
> test for this path**: `itd/itr2.py`'s `_part_a_gen1()` emitted the JSON key `"SEBIRegNo"`, but
> the official schema requires `"SebiRegnNo"` (confirmed via live `Draft4Validator` rejection:
> `Additional properties are not allowed ('SEBIRegNo' was unexpected)`). This meant any FII/FPI
> taxpayer's return would have failed CBDT JSON schema validation outright — the bug simply had
> no test to catch it before now.
>
> Regression test: `test_generate_cbdt_json_itr2_emits_fii_fpi_declaration` in
> `tests/test_filing_gateway_v2_itr2.py`, confirmed via `git stash` to be absent (and the wrong
> key present) on pre-fix code. `npm run build` clean.

## 4.3 Director and unlisted-equity disclosures are reduced to flags

The model has `isDirector` and `holdsUnlistedShares` around `return_draft.py:1492–1502`, but the frontend does not provide the complete official detail tables, such as company identity, DIN/directorship details, ISIN, acquisition/disposal, share count, face value, and cost.

**Severity: High**

> **Fix status (2026-09-04): fixed and verified.** Re-audit found two real, more severe gaps than
> "reduced to flags": `CompDirectorPrvYrFlg` was **never emitted at all** — `is_company_director`
> was read from the draft into `ITR2FilingProfile` but the builder silently dropped it (its
> sibling `HeldUnlistedEqShrPrYrFlg` one line above was emitted correctly, `CompDirectorPrvYrFlg`
> was simply missing) — and `HeldUnlistedEqShrPrYrFlg`, which the official schema marks
> **required**, had no backing `HeldUnlistedEqShrPrYr.HeldUnlistedEqShrPrYrDtls[]` array ever
> built, so a real "Y" flag could reach ITD with zero supporting detail rows.
>
> Added `CompanyDirectorEntry` (`companyName`, `companyType` D/F, `pan`, `sharesType` L/U, `din`)
> and `UnlistedEquityEntry` (`companyName`, `companyType`, `pan`, opening/closing share count +
> cost, acquired/transferred-during-year sub-fields, face/issue/purchase price) — field names and
> required-ness taken directly from the official schema's `CompDirectorPrvYrDtls`/
> `HeldUnlistedEqShrPrYrDtls` definitions — as new list fields on `PersonalInfo`
> (`return_draft.py`) and `ITR2FilingProfile` (`app/schemas/itr2.py`), wired through
> `_itr2_filing_profile()` (`filing_gateway_v2.py`), fixed the dead `CompDirectorPrvYrFlg` emission
> and added both detail arrays in `_part_a_gen1()` (`itd/itr2.py`).
>
> **New model validator** added to `ITR2FilingProfile.validate_conditional_filing_facts()`
> (matching the existing `is_fii_fpi`/`sebi_registration_number` precedent):
> `is_company_director=True` now requires ≥1 director entry, `held_unlisted_equity=True` requires
> ≥1 equity entry. The official schema itself only enforces object shape, not this business rule —
> without the validator, the exact live bug (a bare "Y" flag with zero backing rows) could be
> silently reintroduced.
>
> Frontend: two new repeatable-row table editors in `PersonalInfoTab.tsx` (director rows and
> unlisted-equity rows, following the existing seventh-proviso clause add/remove-row pattern),
> gated `itrForm === 'ITR-2'`. Also found and fixed two frontend `PersonalInfo` constructor
> call-sites (`factory.ts`, `canonicalRepository.ts`) that needed the new list fields added — a
> `tsc` build failure caught both immediately.
>
> Regression tests: `test_generate_cbdt_json_itr2_emits_director_and_unlisted_equity_detail`,
> `test_generate_cbdt_json_itr2_omits_director_and_equity_blocks_when_unset`, and
> `test_itr2_filing_profile_rejects_director_flag_without_entries` in
> `tests/test_filing_gateway_v2_itr2.py`, confirmed via `git stash` to be absent on pre-fix code.
> `npm run build` clean. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite (284 tests) green.

## 4.4 Section 115H is missing

The frontend filing-profile workflow does not expose section 115H applicability and supporting information.

**Severity: High**

> **Fix status (2026-09-04): fixed and verified.** Implemented in the same pass as §4.1 (same
> schema block, `BenefitUs115HFlg`, `Y`/`N`, optional). Added `benefitUs115H: bool` to
> `FilingStatus`/`ITR2FilingProfile`, wired through `_itr2_filing_profile()`, emitted as
> `BenefitUs115HFlg: "Y"` in `_part_a_gen1()` only when true (omitted otherwise). Frontend
> checkbox added to the same conditional "Residential status details" section as §4.1.
> Confirmed backend had genuinely zero representation before this fix — `prefill_parser.py`
> already parsed `benefitUs115HFlg` from ITD prefill JSON into an intermediate dataclass field,
> but nothing downstream could receive or re-emit it.
>
> Regression test: `test_generate_cbdt_json_itr2_emits_residential_status_facts` (shared with
> §4.1, asserts `BenefitUs115HFlg == "Y"`).

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
>
> **Update (2026-09-04, Phase 4 P0 exit re-audit): the above fix was itself incomplete — corrected
> and now verified end-to-end.** A systematic cross-check of every key `_part_a_gen1()` emits
> against the official schema's full `FilingStatus` property list (prompted by this session's two
> prior key-name/dead-field bugs in the same function) found that **none** of the seventh-proviso
> sub-fields were ever emitted into the JSON at all — only the single umbrella
> `SeventhProvisio139` Y/N flag. `DepAmtAggAmtExcd1CrPrYrFlg`, `AmtSeventhProvisio139i/ii/iii`,
> `IncrExpAggAmt2LkTrvFrgnCntryFlg`, `IncrExpAggAmt1LkElctrctyPrYrFlg`, `clauseiv7provisio139i`,
> `clauseiv7provisio139iDtls`, and (unrelated to this item but discovered in the same sweep)
> `PortugeseCC5A` were all absent from the builder — meaning a taxpayer declaring >₹1 crore
> current-account deposits, even after the frontend-gate fix above, would still have had that fact
> silently dropped from the actual filed JSON. `ITR2FilingProfile` already carried the correct
> aggregate amounts (`current_account_deposits`, `foreign_travel_expenditure`,
> `electricity_expenditure`) from `_itr2_filing_profile()`'s existing wiring — this was a pure
> builder gap, the exact same "captured but discarded mid-pipeline" pattern found repeatedly
> earlier in this session (TDS/TCS, Schedule OS).
>
> Added four new boolean sub-flags (`deposit_exceeds_one_crore`, `foreign_travel_flag`,
> `electricity_expenditure_flag`, `other_clause_iv_flag`) and a new `SeventhProvisoClauseEntry` row
> list to `ITR2FilingProfile`, wired from `NormalizedSeventhProviso`'s already-captured raw fields
> (`seventh.deposit_exceeds_one_crore`/`.foreign_travel`/`.electricity_expenditure`/
> `.other_clause_iv`/`.clause_iv_details`, all pre-existing in `personal_profile.py`, simply never
> reaching `ITR2FilingProfile` before now). Added a new model validator enforcing the schema's own
> hard statutory minimums (deposit ≥ ₹1cr, foreign travel ≥ ₹2L, electricity ≥ ₹1L) whenever the
> corresponding flag is true — a flag set without a qualifying amount is a genuine data-entry
> inconsistency, not a value to silently pass through. `_part_a_gen1()` now emits all four sub-flags
> unconditionally (matching the sibling `HeldUnlistedEqShrPrYrFlg`/`FiiFpiFlag`/
> `CompDirectorPrvYrFlg` convention) and the amounts/detail array/`PortugeseCC5A` conditionally.
>
> No frontend changes were needed for this correction — the "Seventh proviso to section 139(1)"
> UI (checkboxes, amounts, clause-IV row editor) already existed and already captured this data
> correctly; only the backend pipeline from `ITR2FilingProfile` onward silently dropped it.
>
> Regression tests: `test_generate_cbdt_json_itr2_emits_seventh_proviso_sub_flags_and_amounts`,
> `test_generate_cbdt_json_itr2_omits_seventh_proviso_sub_amounts_when_unset`, and
> `test_itr2_filing_profile_rejects_deposit_flag_below_statutory_minimum` in
> `tests/test_filing_gateway_v2_itr2.py`, confirmed via `git stash` to be absent on pre-fix code.
> Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite (290 tests) green.

## 4.7 LEI fields are missing or incomplete

Applicable LEI information is not represented through a complete frontend workflow.

**Severity: Medium to High**, depending on taxpayer and transaction applicability.

> **Fix status (2026-09-04): fixed and verified.** Confirmed fully greenfield before this fix —
> nothing existed at any layer (backend schema, builder, frontend). Added `leiNumber`
> (20-character, matches the official schema's exact `LEINumber` length constraint) and
> `leiValidUptoDate` to `FilingStatus` (`app/schemas/return_draft.py`) and
> `lei_number`/`lei_valid_upto_date` to `ITR2FilingProfile` (`app/schemas/itr2.py`), wired through
> `_itr2_filing_profile()` (`filing_gateway_v2.py`), emitted as `LEIDtls.LEINumber`/`ValidUptoDate`
> in `_part_a_gen1()` (`itd/itr2.py`) only when `lei_number` is set (the block is omitted entirely
> otherwise, not emitted as an empty placeholder). Added a two-field UI section to
> `PersonalInfoTab.tsx` (gated `itrForm === 'ITR-2'`), a note explaining the CBDT ₹50cr-refund
> instructional trigger (not schema-enforced).
>
> Regression tests: `test_generate_cbdt_json_itr2_emits_lei_details` and
> `test_generate_cbdt_json_itr2_omits_lei_block_when_unset` in
> `tests/test_filing_gateway_v2_itr2.py`, confirmed via `git stash` to be absent on pre-fix code.
> `npm run build` clean.

---

## Phase 4 — P0 exit re-audit (2026-09-04)

Per `C:\Users\Devansh\.claude\plans\zippy-juggling-sprout.md`'s Phase 4: a targeted re-read of
`_part_a_gen1()` (`app/engine/itd/itr2.py`) — the exact function every Phase 3 fix landed in —
against the official schema's complete `FilingStatus`/`PersonalInfo` property lists, prompted by
this session's two prior latent bugs in that same function (a wrong JSON key name, a dead field
emission). Method: enumerated every property the schema defines for both blocks and diffed
against every key the builder actually constructs.

**Finding, fixed inline (CRITICAL — see §4.6's "Update" note above for the full write-up):** the
seventh-proviso sub-flags/amounts (`DepAmtAggAmtExcd1CrPrYrFlg`, `AmtSeventhProvisio139i/ii/iii`,
`IncrExpAggAmt2LkTrvFrgnCntryFlg`, `IncrExpAggAmt1LkElctrctyPrYrFlg`, `clauseiv7provisio139i`,
`clauseiv7provisio139iDtls`) and `PortugeseCC5A` were never emitted at all — only the umbrella
`SeventhProvisio139` flag was. This meant §4.6's own fix (unblocking the frontend control) was
incomplete: the disclosure still never reached the actual filed JSON. Fixed, tested, and
`git stash`-verified in the same pass.

**Checked and confirmed correct, no further finding:** `PersonalInfo`'s full property list
(`AssesseeName`, `PAN`, `Address`, `SecondaryAdd`, `AlternateAddress`, `DOB`, `Status`,
`AadhaarCardNo`) — every key matches exactly. `AssesseeRep`/`AsseseeRepFlg` — `AsseseeRepFlg` is
correctly hardcoded `"N"` (not a bug): `_itr2_filing_profile()` already rejects
`verification.capacity == REPRESENTATIVE` outright before construction, so ITR-2 genuinely never
has a represented return, unlike ITR-1/ITR-4.

Extended the same key-by-key technique to `_schedule_tds2()`/`_schedule_tds3()`/`_schedule_tcs()`
(Phase 2's other major fix area) against the official schema's `TDSOthThanSalaryDtls`/
`TDS3onOthThanSalDtls`/`ScheduleTCS.TCS[]` item definitions — every emitted key matches the schema
exactly (including all conditional `PANofOtherPerson`/`AadhaarOfOtherPerson`/
`PANOfSpouseOrOthrPrsn` keys); no further bug found.

Not re-checked in this pass (deferred, in scope for Phase 5's own P1 review rather than expanding
Phase 4): Schedule CG/OS/IT builders were spot-checked via their own regression tests' schema
validation (all passing) rather than independently re-diffed key-by-key against the schema, since
those tests already assert `Draft4Validator` passes on realistic populated data.

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

## 5.4 Schedule S standard deduction could be silently reported as zero

**New finding (2026-09-05, Phase 5).** `_schedule_s()` (`itr2.py:467`) derives every employer's
`GrossSalary`/`Salary` from `tds1_entries[].income_chargeable` (Schedule TDS1, a per-employer
Form-16/26AS-sourced figure) and separately back-derives `DeductionUnderSection16ia` as
`net_salary - result.salary_income - entertainment_allowance - professional_tax_paid`, where
`result.salary_income` comes from the calculator taxing the *aggregate* `SalaryIncome` schema
object. These are two genuinely independent inputs — confirmed in `filing_gateway_v2.py:1386-1389`,
where `TDS1Entry.income_chargeable` is populated from imported TDS-row data (`row.deductorName`
etc.), not from the frontend's salary-entry form that feeds `SalaryIncome` — and nothing validates
that they agree; `ITR2-IN-TDS-004` (`app/engine/validators/itr2/input_rules.py:765`) only bounds
`tds_deducted` against a chargeable-income figure, never `tds1_entries[].income_chargeable`
itself. When the TDS1 figure is smaller than what `SalaryIncome` yields once taxed (e.g. a
26AS-imported "amount credited" that predates a manually-entered retirement benefit or exemption
adjustment), the subtraction went negative and the previous code silently clamped it to `0` —
reporting a real, calculator-applied standard deduction as if none had been claimed, while
`TotIncUnderHeadSalaries` (`result.salary_income`) disagreed with the schedule's own visible
Gross/Net/Deduction arithmetic.

**Severity: High**

> **Fix status (2026-09-05): fixed and verified.** Replaced the silent `max(0, ...)` clamp with an
> explicit `raise ValueError` when the subtraction goes negative, matching
> `app/engine/itd/itr1.py`'s identical cross-foot guard for its analogous Schedule HP
> back-derivation (fail closed rather than silently wrong, this project's established standard).
> This does not resolve *which* of the two inputs is correct when they diverge — that would
> require deciding whether `tds1_entries` or `salary_income` is authoritative, a product/data-model
> question out of scope for a JSON-builder fix — it converts a silently-wrong number into a loud,
> actionable error surfaced cleanly as HTTP 400/422 by both call sites (`app/routers/itr.py`'s
> existing `except ValueError` handler and `filing_gateway_v2.py`'s existing
> `except Exception` → `FilingGatewayV2Error` handler; neither needed changes). Regression test
> `test_schedule_s_standard_deduction_does_not_silently_zero_on_mismatch` in
> `tests/test_itr2_itd_builder.py`, confirmed via `git stash` to fail (silently, with no
> exception) pre-fix.

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

> **Fix status (2026-09-05): partially fixed and verified — a genuine correctness bug found and
> closed; the disclosure-completeness gap (lender/loan/co-owner/tenant detail rows) remains open,
> tracked below.** Re-auditing this finding at implementation time (Phase 5 of
> `C:\Users\Devansh\.claude\plans\zippy-juggling-sprout.md`) surfaced something more severe than
> the original "missing detail" framing: `_schedule_hp()` was not just omitting loan/co-owner/
> tenant rows, it was silently **recomputing** `IntOnBorwCap`/`IncomeOfHP`/`BalanceALV`/
> `RentNotRealized`/`ArrearsUnrealizedRentRcvd` from raw input fields instead of using the real
> per-property `HPResult` the calculator (`app/engine/schedules/house_property.py::compute()`)
> already produces — the exact "schema-valid but wrong number" bug class this file's own
> introduction warns about (see the `NetTaxLiability` precedent). Three concrete defects, each
> confirmed with a dedicated regression test in `tests/test_itr2_itd_builder.py` (`git stash`-
> verified to fail pre-fix):
>
> 1. **Self-occupied home-loan interest was reported uncapped.** The interest-selection line read
>    `hp_res.interest_deduction if hasattr(hp_res, "interest_deduction") else
>    source.home_loan_interest_paid` — `HPResult`'s real field is named `interest_on_loan`, not
>    `interest_deduction`, so the `hasattr` check always failed and the code silently fell through
>    to the *raw, uncapped* interest every time. For a self-occupied property with interest paid
>    above the Section 24(b) old-regime ceiling (₹2,00,000, or ₹30,000 pre-1999-loan), the JSON's
>    `IntOnBorwCap`/`Section24B.TotalInterestUs24B` would disagree with the calculator's actual
>    allowed deduction and with `result.house_property_income` itself.
> 2. **`RentNotRealized` was hardcoded to `0`**, ignoring `source.rent_not_realized` — a real,
>    user-suppliable schema field the calculator already subtracts from Gross Annual Value
>    (`house_property.py:125`). `ArrearsUnrealizedRentRcvd` was likewise always `0`, even though
>    Section 25A arrears (taxed at the statutory 70%, `house_property.py:139`) are already fully
>    computed and included in `income_chargeable` — they were simply never surfaced in the JSON.
> 3. **Per-property `IncomeOfHP` was independently re-derived** (`alv - std_ded - interest`) from
>    a locally recomputed `alv`/`std_ded` that omitted `rent_not_realized`/arrears entirely,
>    instead of reading `hp_res.income_chargeable` directly — so a property with any of the above
>    inputs set could show a per-row income figure that disagreed with the very `HPResult` the
>    calculator computed for it.
>
> **Fix**: every Rentdetails field now reads directly from the real per-property `HPResult`
> (`rent_not_realized`, `municipal_taxes`, `net_annual_value`, `annual_value_owned`,
> `standard_deduction_30pct`, `arrears_unrealised_rent`, `income_chargeable`), eliminating the
> local re-derivation entirely. Self-occupied interest is special-cased: `HPResult.interest_on_loan`
> stores the *raw* interest paid for self-occupied property (not the allowed/capped amount) by the
> shared calculator's own design, so `IntOnBorwCap` is derived as `-income_chargeable` instead —
> which equals exactly the allowed/capped interest under the old regime, and `0` under the new
> regime (where Section 24(b) disallows the self-occupied deduction entirely), by construction of
> `house_property.py`'s own formula, with no cap logic duplicated in the serializer.
>
> **Still open** (genuinely a completeness gap, not re-verified away): lender identity/PAN,
> loan account number, sanction date, and outstanding balance (`Section24BDtls[]`, still emitted
> empty — the official schema's own `LoanTknFrom`/`BankOrInstnName`/`LoanAccNoOfBankOrInstnRefNo`/
> `DateofLoan`/`TotalLoanAmt`/`LoanOutstndngAmt`/`InterestUs24B` fields have no backing input model
> at all yet); `CoOwners[]` and `TenantDetails[]` detail rows (both schema-optional arrays,
> similarly unbacked); pre-construction interest amortization; property completion date/status.
> These require new input schema fields (on `PropertyFilingDetail` or a new per-property model) and
> frontend UI, not just a builder fix, and are deferred to a follow-up sub-phase of Phase 5 rather
> than folded into this fix — matching this file's own established practice of not silently
> expanding a fix's scope mid-fix.
>
> **Separately noted, not fixed here**: `app/engine/calculators/itr2.py` calls
> `compute_hp(prop, regime)` for every house property without passing
> `ownership_share_percentage` (the calculator's `compute()` accepts it but defaults to 100), even
> though `PropertyFilingDetail.assessee_share_percent` is captured and *disclosed* in the JSON's
> `AsseseeShareProperty` field. This means co-ownership share currently affects only the
> disclosure, not the actual computed income — a genuine, separate bug, but a calculator-level one
> (shared by every consumer of `compute_hp`), not a JSON-builder bug, and out of scope for this
> fix. Logged here so it isn't lost; a fix would need to thread `assessee_share_percent` from
> `ITR2Input.property_filing_details` into the `compute_hp()` call site in
> `app/engine/calculators/itr2.py`.

## 6.2 Self-occupied property is over-simplified

The serializer calculates ALV and standard deduction using simplified logic around `itr2.py:434–438`, which does not guarantee that the official self-occupied-property and loan fields are correctly represented.

**Severity: High**

> **Fix status (2026-09-05): the interest-cap portion is fixed — see §6.1's fix write-up (item 1
> and the self-occupied interest special-case).** The "over-simplified" framing here referred to
> the same recomputation the §6.1 fix removed; self-occupied ALV/standard-deduction were already
> correctly zero by construction (no separate bug there). The loan-detail-array gap this finding
> also implies is the same open item tracked in §6.1's "Still open" note, not duplicated here.

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

> **Status (2026-09-05): superseded by §3.4, fully closed.** This is the same underlying finding
> as §3.4 (Schedule OS), restated here at summary level. Every category named above -- winnings,
> gifts, DTAA, 89A, PF, unexplained income, special-rate income, and PTI -- is now wired end-to-end
> (disclosure and, where applicable, taxation); PTI's HP/OS-head GTI-inclusion gap (the last item
> here) was fixed 2026-09-05. See §3.4's fix write-ups for the full evidence trail; this entry is
> kept for cross-reference, not as an independent open finding.

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

> **Correction (2026-09-05, dead-code audit): the finding's subject no longer exists.**
> `frontend/src/api/itr2Mapper.ts` was itself confirmed dead code (zero importers) and deleted in
> commit `45d3f10`, alongside the legacy `_compute_itr2_from_flat_payload` backend path it fed.
> This finding is now moot — there is no legacy mapper left to have an incomplete Schedule EI
> mapping. Kept here (rather than deleted) only as a historical record; no action needed.

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

> **New finding (2026-09-05, Phase 5 investigation): the backend `_schedule_amtc()`
> (`itr2.py:1876`) has a credit-utilization direction bug more severe than "the ledger UI is
> missing" — it is not clear the utilization figures it computes are ever correct, and
> deliberately left unfixed pending tax-law verification rather than rushed. Documented here in
> full per this project's own established practice (see the CLAUDE.md-cited section 112(1)(a)
> precedent) rather than shipping an uncertain fix.**
>
> **Evidence.** `_schedule_amtc()` computes each brought-forward credit row's
> `AmtTaxCreditUtilisedCY` as `min(credit.credit_brought_forward, result.amt_tax)`.
> `result.amt_tax` (`ITR2Result.amt_tax`, set in `app/engine/calculators/itr2.py:991-993`) is
> **not** "this year's AMT liability" — it is the *top-up delta* added to total tax only when AMT
> applies this year (`amt_result.amt_tax - tax_before_cess`), and is exactly `Decimal("0")` in
> every year AMT does **not** apply. Section 115JD credit, by contrast, can only ever be
> *consumed* in a year AMT does **not** apply (a year AMT applies is a year generating *new*
> credit, not consuming old credit — `amt.py`'s own `amt_credit` field, computed as
> `amt_total - regular_tax` only `if amt_applies`, is precisely the newly-generated amount, and is
> a completely different quantity from brought-forward-credit consumption).
>
> Tracing through a concrete case: a taxpayer with a brought-forward credit of ₹1,00,000 files a
> return in a year where AMT does **not** apply (`result.amt_tax == 0`, the normal case in which
> credit *should* be usable) — the code computes `AmtTaxCreditUtilisedCY = min(100000, 0) = 0`
> for every row, **every time**, regardless of how much headroom (regular tax minus this year's
> AMT floor) actually exists. Conversely, in a year AMT *does* apply (`result.amt_tax > 0` — the
> one case where, per Section 115JD, credit should **not** be consumable at all, since AMT ≥
> regular tax by definition that year), the code reports nonzero "utilization." The condition
> under which the code reports any utilization at all is the exact opposite of the condition
> under which Section 115JD permits it.
>
> **Separately, when more than one brought-forward-credit row exists** (`amt_in.amt_credits`
> is a list — the official schema's `ScheduleAMTCDtls` explicitly supports multiple
> assessment-year rows, and a taxpayer with several years of AMT history could legitimately have
> more than one), each row independently computes `min(credit.credit_brought_forward,
> result.amt_tax)` against the **same, full** `result.amt_tax` rather than allocating a single
> shared utilization pool across rows (in statutory FIFO order — the earliest assessment year's
> credit must be exhausted first, since credit expires after 15 years). With two rows of
> ₹50,000 and ₹30,000 brought forward and `result.amt_tax = 40000` (itself the wrong quantity per
> above, but illustrating the row-independence bug on its own terms), each row separately claims
> up to ₹40,000 utilized -- a combined ₹70,000 "utilized" against a single year's ₹40,000 figure.
>
> **Why this is left unfixed rather than corrected now**: a correct fix requires knowing, for a
> year where no AMT-triggering deduction is claimed at all (`addition_total == 0` in
> `app/engine/schedules/amt.py::compute()`), whether Section 115JD credit remains consumable that
> year and against what comparison figure -- `compute_amt()` deliberately short-circuits and
> never computes a real `amt_tax`/`regular_tax` comparison in that case (returning
> `AMTResult(regular_tax=regular_tax, final_tax=regular_tax)` with every AMT-specific field at its
> zero default), because Section 115JC's own applicability condition requires a specified
> deduction claim in that year. Whether the ₹115JD credit-consumption comparison is legally
> required to run independently of that short-circuit is a genuine tax-law question this audit
> is not confident enough to resolve by inference alone -- it needs either the official ITR-2
> form instructions/Section 115JD case law, or a live Type-2 UAT `validateItr` test with a
> populated `ScheduleAMTCDtls` array, the same standard this project's Digest off-by-one and
> ITR-4 builder-bug fixes were held to (CLAUDE.md's own "static cross-referencing... does not
> prove correctness, only a live call does" standard). Rushing a plausible-looking formula here
> risks replacing one wrong-number bug with a different, equally confident-looking wrong one.
>
> **Blast radius check performed**: `app/engine/calculators/itr3.py` also calls
> `app.engine.schedules.amt.compute()` with the identical applicability-gated-storage pattern
> (`itr3.py:517-521`), but `app/engine/itd/itr3.py` has no `_schedule_amt`/`_schedule_amtc`
> functions at all yet -- ITR-3 does not serialize either schedule today, so this finding and any
> future fix are isolated to `app/engine/calculators/itr2.py` and `app/engine/itd/itr2.py`; no
> other form is affected.

## 9.4 CFL is backend-only with no reconciliation display

The frontend states around `ITR2SchedulesWorkspace.tsx:116` that Schedule CFL is computed by the backend and has nothing to enter. Computation can remain backend-authoritative, but the preparer needs a read-only year-by-year reconciliation showing current-year losses, set-off, and carry-forward.

**Severity: Medium to High**

> **Fix status (2026-09-05): three real correctness/schema-validity bugs found and fixed in
> `_schedule_cfl()` (`itr2.py:416`) while investigating this item; the frontend reconciliation
> display itself remains unbuilt.**
>
> 1. **`DateOfFiling` was silently omitted whenever `date_of_filing` was unset.** The official
>    schema requires `DateOfFiling` unconditionally for every one of the 8 year-slot objects
>    (both the `CarryFwdLossDetail` type used for AY2022-23 onward and the
>    `CarryFwdWithoutLossDetail` type used for AY2018-19 through AY2021-22) — since
>    `BFLossItem.date_of_filing` is `Optional` in the Pydantic schema, any taxpayer with a
>    brought-forward loss and no filing date entered would produce schema-invalid JSON, discovered
>    only at validation time with no indication of which field was missing or why. Fixed to raise
>    a clear `ValueError` naming the assessment year and the reason (filing date is a genuine
>    carry-forward eligibility precondition under Section 80, not an arbitrary schema requirement).
> 2. **`OthSrcLossRaceHorseCF` was hardcoded to `0`**, dropping any real Section 74A race-horse
>    brought-forward loss from every total it should have appeared in — including the field
>    literally named for it. Traced through `app/engine/schedules/loss_setoff/bfla.py:120-174`:
>    a `LossHead.RACE_HORSE`-headed entry matches none of that function's head branches, so the
>    full brought-forward amount passes through unset-off as a genuine `CFLossEntry` with
>    `head="RaceHorse"` — `_schedule_cfl()`'s `summary()` helper simply never looked for it. Fixed
>    to sum real race-horse `loss_remaining` into the field.
> 3. **`OthSrcLossRaceHorseCF` was also being emitted for year-slots whose schema type doesn't
>    have that property at all** (`CarryFwdWithoutLossDetail`, AY2018-19 through AY2021-22 —
>    structurally excluded from the schema itself, since Section 74A's 4-year cap means a
>    race-horse loss should never legitimately survive to that age) — with
>    `additionalProperties: false` on that type, this was an independent schema violation any time
>    a taxpayer had ANY brought-forward loss (of any head) that old. Fixed by making
>    `include_race_horse` conditional on which of the two schema types the target year-slot uses.
>
> **Separately noted, not fixed here**: `app/engine/schedules/loss_setoff/bfla.py`'s
> `_MAX_CARRY_FWD` dict (line 12) has no entry for `"RaceHorse"`, so a race-horse loss never
> expires under this engine's carry-forward logic at all — Section 74A caps it at 4 years, same
> as speculative business loss. This is a shared-module bug (used by ITR-2's and ITR-3's
> calculators) independent of the three JSON-builder bugs above, and touching a shared module
> needs its own dedicated fix-and-regression cycle across every form that consumes it — deferred
> rather than folded into this fix.
>
> Three regression tests added to `tests/test_itr2_itd_builder.py`
> (`test_schedule_cfl_reports_race_horse_loss_instead_of_dropping_it`,
> `test_schedule_cfl_requires_date_of_filing_instead_of_silently_omitting_it`,
> `test_schedule_cfl_omits_race_horse_field_for_older_year_slots`), each confirmed via `git stash`
> to fail pre-fix. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite green (627 passed), plus
> every other test file referencing `bf_losses`/`BFLossItem` (`test_bfla.py`,
> `test_capital_gains_loss_foundation.py`, `test_draft_to_itr2_input.py`, `test_itr2_integration.py`,
> `test_itr2_validators.py`, `validate_schemas.py`) checked directly — the only 2 failures there
> (`validate_schemas.py::test_itr2`/`test_itr3`) confirmed via `git stash` to pre-date this fix.

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

> **Fix status (2026-09-05): a real data-loss bug found and fixed; the event-level/multi-employer
> completeness gap this item describes remains open.** "Serializes from the first entry" undersold
> the actual defect: `_schedule_esop()`'s per-AY ledger built `entry_by_ay = {e.assessment_year: e
> for e in input_data.esop_deferrals}` — a plain dict comprehension keyed by assessment year, which
> keeps only the LAST entry for a given year. Two ESOP grants vesting in the same assessment year
> (a realistic scenario — more than one qualifying tranche from the same eligible startup, or a
> second grant, in one year) meant the earlier entry's `tax_deferred_brought_forward`/
> `tax_payable_current_year`/`balance_tax_carried_forward` were silently dropped entirely, not
> merely under-detailed. Separately, the running AY2026-27 carry-forward balance
> (`ScheduleESOP2627_Type.BalanceTaxCF`) used `first.balance_tax_carried_forward` — literally the
> first entry in the whole list, regardless of how many other entries existed — dropping every
> other entry's outstanding deferred-tax balance from the one field meant to show the taxpayer's
> total remaining ESOP tax liability. (`DPIITRegNo`/`PanofStartUp` legitimately use the first
> entry only — the official schema defines these as single top-level scalars, not per-entry, since
> Section 80-IAC's "eligible start-up" ESOP deferral is inherently a one-employer relationship;
> that part was not a bug.)
>
> **Fix**: entries are now aggregated (summed) per assessment year before building each AY block,
> and the AY2026-27 balance is the sum of every entry's `balance_tax_carried_forward`, not just
> the first. Regression test `test_schedule_esop_aggregates_same_year_entries_instead_of_dropping_them`
> in `tests/test_itr2_itd_builder.py`, confirmed via `git stash` to fail pre-fix. Full
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite green (628 passed).
>
> **Still open** (the completeness gap this item originally described): `ScheduleESOPEventDtls`
> (`esop_event`, shared unchanged across every AY block) is hardcoded to `{"SecurityType": "NS",
> "ScheduleESOPEventDtlsType": [], "CeasedEmployee": "N"}` regardless of the taxpayer's actual
> security type, individual vesting/allotment events, or cessation-of-employment status — this
> requires new event-level input fields and frontend UI, not just an aggregation fix, and remains
> exactly as the original finding described.

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

> **Fix status (2026-09-05): the confirmed-dead portion is removed.** See §2.2's fix write-up —
> `itr2Mapper.ts` (the file this whole section describes) is deleted outright, along with its
> `itrCompute.ts` wrapper and the equally-dead `_compute_itr2_from_flat_payload` legacy
> flat-payload path in `app/routers/tax.py`. The category-by-category gaps documented above
> (Salary/House property/Other sources/Capital gains/Deductions/TDS-TCS) described exactly what
> this now-deleted file failed to map — they are moot now that the file no longer exists as a
> reachable path; the canonical v2 (`ReturnDraft`) pipeline this section contrasts it against
> already has its own, separately-tracked completeness findings elsewhere in this document (§3-§14).

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

1. ~~**Establish one canonical path**~~ — **fixed 2026-09-05**, see §2.2's fix write-up:
   `itr2Mapper.ts` deleted (zero importers), its `itrCompute.ts` wrapper functions removed, and
   the dead `_compute_itr2_from_flat_payload` flat-payload path in `app/routers/tax.py` retired
   (an ITR-2 request to that legacy endpoint now correctly falls through to the same
   "provisional preview" status ITR-3 already receives, rather than computing a real-looking but
   unreachable-from-the-frontend result). `/itr2/compute`/`/itr2/compute-json` in
   `app/routers/itr.py` were investigated and found to be real, tested, typed direct-input API
   surface — NOT the dead legacy mapper this item's original scoping assumed — and were
   deliberately left in place.

2. **Complete capital-gains serialization**
   - ~~dedicated Schedule 115AD~~ — **fixed 2026-09-05**, see §3.1's fix write-up: the "needs a new
     `CGAssetType`/FII-flag addition" conclusion from the 2026-09-04 re-verification was itself
     wrong — `ITR2FilingProfile.is_fii_fpi` (already implemented) is the correct, sufficient
     discriminator, since 115AD is a whole-taxpayer classification, not per-transaction. Also fixed
     a genuinely separate, non-FII-specific bug found in the same pass: `SaleOfEquityShareUs112A`
     was hardcoded to zero for every taxpayer, FII or not.
   - ~~land/building STCG/LTCG detail~~ — **fixed 2026-09-04**, see §3.2's fix write-up (was a
     schema-blocking wrong-field-name bug, not just missing detail; §50C deeming added as a new
     capability).
   - ~~all OTHER CG categories (`unlisted_shares`, `listed_security`, `debt_mutual_fund`,
     `specified_mutual_fund_50aa`, `market_linked_debenture_50aa`, `bonds_debentures`,
     `depreciable_asset`, `jewellery`, `foreign_asset`, `other`)~~ — **fixed 2026-09-04**, see
     §3.2's fix write-up update (mapped into the generic `SaleOnOtherAssets`/`SaleofAssetNADtls`
     bucket per the official form's Schedule CG items 5/8, with section 50CA deeming for
     unquoted shares).
   - ~~section-specific exemptions~~ — **fixed 2026-09-05**, see §3.2's fix write-up: per-row
     `ExemptionOrDednUs54Dtls`/`DeductionUs54F` disclosure and all five `DeducClaimDtlsUs*` detail
     arrays now populated from `CGTransaction.exemptions`, disclosure-only (the actual tax total
     was already correct via the pre-existing aggregate mechanism, unchanged by this fix).
   - ~~signed loss handling for the other 10 categories~~ — **confirmed already resolved
     2026-09-05** (stale bullet, never marked closed): the same 2026-09-04 "generic other assets"
     fix (§3.2's own earlier "Update" note) already made `_other_assets_block()`'s
     `BalanceCG`/`CapgainonAssets` genuinely signed (verified live: a loss transaction emits
     `-200000`, not a `max(0, ...)`-clamped `0`; both fields' schema definitions permit negative
     values). No code change was needed for this bullet specifically -- only the tracking list was
     out of date.
   - **CYLA/BFLA/CFL reconciliation — reviewed 2026-09-05, no arithmetic bug found; one
     discretionary-ordering observation flagged, not treated as a defect.**
     `app/engine/schedules/loss_setoff/{cyla,bfla,cfl}.py` were read in full. CYLA's six-sub-basket
     intra-head STCL-before-LTCL set-off, and BFLA's oldest-brought-forward-loss-first FIFO
     ordering (respecting each head's own carry-forward expiry — 8 years for HP/business-non-
     speculative/STCG/LTCG, 4 years for speculative business, matching `_MAX_CARRY_FWD`), both
     match the statutory requirements checked against. CFL's carry-forward totals derive from the
     same CYLA/BFLA remaining-loss fields the builder also reads, so no independent drift was
     found. One observation: CYLA processes non-speculative-business loss against pools in the
     order `nsb → hp → cg → other`, while house-property loss (capped at ₹2L per section 71B) is
     processed `other → nsb → spec → cg` — a different traversal order for different loss types
     drawing on shared pools. This can affect which specific loss category's carry-forward balance
     is smaller in a scarce-pool scenario, but does NOT affect the aggregate current-year loss
     set-off total or resulting GTI (a basic invariant of sequential pool-draining: total consumed
     from a pool is `min(pool, sum of demands)` regardless of draw order). No statute text found
     that prescribes an exact head-vs-head priority here beyond "intra-head first, then
     inter-head," so this is treated as a discretionary implementation choice, not a proven defect
     — flagged for a live ITD Type-2 UAT cross-check (Phase 12) rather than a speculative rewrite,
     matching this project's "static review doesn't prove correctness, only a live call does"
     discipline (already established for the Digest computation and the NRI special-rate module's
     7 lower-confidence tax rates).
   - ~~**Section 112(1)(a) indexed-cost-primacy defect** (found 2026-09-04)~~ — **fixed
     2026-09-05**, see §3.2's fix write-up: primary balance now always uses non-indexed cost; the
     full second-proviso dual tax-comparison (`TaxSec1121a`/`TaxSec1121aiiB`/`ExcessAmtSec1121a`)
     is implemented and its relief actually reduces the Schedule SI section-112 tax, capped
     (documented, not exact-to-the-rupee) at that bucket's own computed tax when losses/exemptions
     also apply to it.
   - no silent zero placeholders for populated data — resolved for land/building; open elsewhere.

3. **Complete Schedule OS**
   - ~~winnings, accumulated PF~~ — **fixed 2026-09-04**, see §3.4's fix write-up (also fixed a
     pre-existing bug where this SI-dispatched income was taxed but never added to Total Income).
   - ~~gifts (section 56(2)(x))~~ — **fixed 2026-09-04**, see §3.4's fix write-up (relative/marriage
     exemption and the correct aggregate/per-property thresholds applied).
   - ~~DTAA disclosure and taxation, 89A, unexplained income, special-rate-income entries
     (disclosure + taxation), deductions, and dividend sub-categories~~ — **fixed
     2026-09-04/05**, see §3.4's fix write-up, its "NRI special-rate income module" update, and
     its DTAA-computation correction note (the "separate, larger undertaking" originally assumed
     for DTAA tax computation turned out to be a pre-existing unused helper function plus the
     same GTI-inclusion wiring gap as everything else in this list).
   - ~~PTI (pass-through income) HP/OS-head GTI inclusion~~ — **fixed 2026-09-05**: a real bug,
     not just missing detail -- `_schedule_pti()` already disclosed HP-head and OS-head
     `pti_entries` correctly in `SchedulePTIDtls`, but `compute()`'s PTI dispatch loop only handled
     STCG/LTCG heads (routing them to Schedule SI); HP/OS-head entries had NO calculator path at
     all, so that income was disclosed but never reached GTI. Fixed by adding HP-head PTI income
     to `r.house_property_income` (before CYLA/BFLA, so a passed-through HP loss shares the same
     inter-head set-off cap as the assessee's own HP loss) and OS-head PTI income to
     `r.other_sources_income`. Regression tests:
     `test_pti_hp_and_os_head_entries_reach_gti_and_schedule_pti` (`tests/test_itr2_itd_builder.py`)
     and `test_pti_hp_and_os_head_income_reaches_gti` (`tests/test_draft_to_itr2_input.py`),
     confirmed via `git stash` to fail on pre-fix code. Remaining open: per-entry PTI TDS linkage
     beyond the flat `tds_credit` field already wired (no deeper category-specific detail attempted
     here).
   - ~~`RACE_HORSE_ACTIVITY` winnings~~ — **fixed 2026-09-04**, see §3.4's "Update (2026-09-05)"
     write-up: net profit now flows to `IncFromOwnHorse` and GTI, per section 74A(3)'s no-loss-
     set-off rule (this bullet was stale — the fix landed before this list was last touched).
   - category-specific detail and TDS linkage (beyond what's now wired: dividend/DTAA/winnings/
     PF/89A/unexplained-income/special-rate/deductions detail) — still open.
   - populated-category preservation tests — added for winnings/PF/gifts/unexplained-income/89A/
     dividend/DTAA/deductions/race-horse/machinery-rent/special-rate/DTAA-tax; still open for PTI.

4. ~~**Correct TDS/TCS credits**~~ — **fixed 2026-09-04**, see §3.6/§3.7's fix write-ups: ownership,
   spouse/other-person PAN, brought-forward and carry-forward, correct head of income, and total
   reconciliation are all now real. Also fixed four crash-bug typos found along the way
   (`TDS3Entry.tds_claimed_this_year`/`financial_year`/`gross_amount` misreads). Partial-claims
   handling was already correct before this fix (unaffected).

5. ~~**Correct negative HP handling**~~ — **re-verified 2026-09-04, not a defect**: see §3.5's
   and §6.3's re-verification notes. `PartB-TI.IncomeFromHP`'s non-negative constraint is
   schema-mandated; the loss is correctly tracked via `_schedule_cyla()`'s dedicated fields, not
   silently dropped.

6. ~~**Complete filing profile**~~ — **all items fixed 2026-09-04**, closing the last of Phase 3's
   filing-profile gaps:
   - ~~current-account deposit seventh-proviso field for ITR-2~~ — see §4.6 (backend was already
     correct; the frontend control was simply gated to ITR-4 only).
   - ~~92CD~~ — see §4.5 (was unreachable at three layers: draft schema, `FILING_SECTION_CODES`
     map, and the frontend dropdown).
   - ~~115H~~ — see §4.4 (implemented alongside §4.1 in the same schema block).
   - ~~residential-status facts~~ — see §4.1 (re-audit found the frontend had no residential-status
     *selector* at all, a more basic gap than originally documented).
   - ~~FII/FPI and SEBI~~ — see §4.2 (backend was already fully wired; found and fixed a
     schema-blocking `SEBIRegNo`/`SebiRegnNo` key-name bug along the way).
   - ~~director details~~ — see §4.3 (found `CompDirectorPrvYrFlg` was never emitted at all; added
     a model validator requiring backing detail rows whenever the flag is true).
   - ~~unlisted-equity details~~ — see §4.3 (the official-schema-required flag had no backing
     detail array ever built).
   - ~~LEI~~ — see §4.7 (confirmed fully greenfield before this fix).

## P1 — Required for broad taxpayer coverage

7. Expand Schedule HP with section 24(b), pre-construction interest, ownership, co-owner, tenant, unrealized-rent, and complete property details.

   > **Partially fixed 2026-09-05** — see §6.1/§6.2's fix write-ups. The correctness bug (self-
   > occupied interest reported uncapped; `RentNotRealized`/`ArrearsUnrealizedRentRcvd`/per-row
   > `IncomeOfHP` silently recomputed instead of read from the real calculator result) is fixed
   > and regression-tested. Still open: section 24(b) loan-lender detail rows, co-owner rows,
   > tenant rows, pre-construction interest, and complete property/completion-status fields — all
   > genuinely missing input models, not builder bugs.

8. Replace generic Schedule FA rows with category-specific foreign bank, custodial, equity/debt, insurance, trust, signing-authority, property, and other-asset editors and serializers.

9. Separate AMT and AMTC in the UI and add the historical AMTC ledger.

   > **Investigated 2026-09-05, not fixed — see §9.3's new finding.** The backend AMTC
   > credit-utilization logic has a direction bug (uses the wrong-year's comparison figure,
   > backwards) plus a multi-row double-counting bug, deliberately left unfixed pending tax-law
   > verification of the correct year-with-no-AMT-trigger comparison rather than shipping an
   > uncertain formula. This is a real correctness defect, not just a missing UI ledger — treat
   > "AMT/AMTC history" cases as unsafe for production filing until this is resolved (already
   > listed under "Not safe for broad production use today").

10. Add a read-only Schedule CFL year-by-year reconciliation.

    > **Backend correctness fixed 2026-09-05** — see §9.4's fix write-up: a missing `DateOfFiling`
    > (schema-invalid JSON on any brought-forward loss with no filing date), a hardcoded-zero
    > `OthSrcLossRaceHorseCF` (real race-horse losses silently dropped), and that same field being
    > emitted where the schema forbids it (a second, independent schema violation) are all fixed
    > and regression-tested. The frontend reconciliation display itself remains unbuilt.

11. Expand Schedule S with employer, salary nature, perquisite, section 10, HRA, retirement, arrears, and section 89A structures.

    > **Partially fixed 2026-09-05** — see §5.4's new finding and fix write-up: a real
    > silent-wrong-number risk (standard deduction clamped to 0 on a tds1_entries/salary_income
    > mismatch) is now a loud, fail-closed error instead. The completeness gaps this item lists
    > (salary nature, perquisite categories, section 10 detail rows, HRA structure, retirement
    > detail, section 89A) remain open — unaffected by this fix.

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

That success does not establish ITR-2 filing completeness. The implementation currently has a material gap between UI/model coverage and official JSON output. Before real ITR-2 filing, the project must complete the canonical serialization path and resolve the remaining P0 findings.

> **Update (2026-09-05): substantial P0 progress since this assessment was first written.**
> Of the P0 list in §18: filing-profile completeness (item 6, all seven sub-items), TDS/TCS
> credits (item 4), Schedule IT (§3.8), and negative-HP handling (item 5, retracted as never a
> defect) are all closed with verified fixes. Schedule OS (item 3) is closed except deeper PTI
> TDS-linkage detail (the PTI HP/OS-head GTI-inclusion bug is now fixed too). The section 112(1)(a)
> indexed-cost-primacy defect (found 2026-09-04) is fixed, including the full second-proviso
> relief; signed-loss handling for the generic-other CG categories was confirmed already correct;
> CYLA/BFLA/CFL was reviewed with no arithmetic bug found. **All of item 1 (legacy-mapper
> duplication), item 2's Schedule 115AD (turned out to need only FII/FPI-flag-based routing off
> the already-existing `is_fii_fpi` filing-profile flag, not a schema extension as first assumed),
> and item 2's per-transaction §54/54B/54EC/54F/115F exemption attribution are now also fixed.**
> What remains open in the capital-gains cluster: the section-94(7)/94(8) dividend-stripping
> loss-disallowance figure (no input field captures it at all — a distinct, smaller gap). See the
> consolidated open-findings list this update maintains for the complete current picture (P1 items
> in §5-§13 remain the largest body of open work).
>
> **Final classification: broadly implemented, meaningfully more complete than the original
> audit found, but still not fully production-ready for complete AY 2026–27 ITR-2 filing** — every
> P0 finding this audit originally identified is now closed except the narrow §94(7)/94(8)
> disclosure gap noted above; the remaining path to production readiness runs primarily through
> the P1 findings (§5-§13: Schedule HP detail, Schedule FA category-specific structures, AMT/AMTC
> UI separation, Schedule CFL reconciliation, Schedule S detail, and several smaller frontend-
> compression findings), not the broad P0 surface area the original audit identified as
> highest-risk.
