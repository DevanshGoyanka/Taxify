# ITR-3 — v2 Canonical Pipeline Production Implementation Plan

**Status:** Active implementation tracker for ITR-3 on the shared complete-preparation
contract (Phase 8 of `ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`, broken out as its own
schedulewise-ordered plan per the user's explicit instruction).
**Date:** 2026-09-15 (created) · verified against **both** the notified ITR-3 PDF for AY
2026-27 **and** the official ITR-3 JSON schema for AY 2026-27.
**Authority:** This is the single source of truth for building ITR-3 on the same
complete-preparation standard now established by ITR-1, ITR-2, and ITR-4. It is verified
against `Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` and
`Docs/design/CANONICAL_RETURN_PIPELINE_MIGRATION_PLAN.md` at every step — nothing here is
guessed from an older doc's claims. It supersedes the high-level Phase 8 outline in
`ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` (which is left untouched) only for ITR-3.
**Ordering rule (non-negotiable, per user instruction):** the implementation phases below
are numbered strictly in the order Parts and Schedules appear in the notified ITR-3 PDF
(`Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf`). The official ITR-3
JSON schema (`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-3_2026_Main_V1.1 (2).json`,
69 schedule blocks, 287 definitions) is reconciled against that PDF order in §0B below, and
each phase names the schema block(s) it emits so **both** sources are honored
simultaneously. Cross-cutting technical prerequisites (typed draft fields, the mapper,
gateway dispatch, the builder signature fix, schema validation, the validator suite,
frontend wiring) are **not** pulled forward into their own pre-phases; each is listed as a
gate **inside the schedule phase that first needs it**, so the phase order on the page
matches the form order on the PDF.

---

## 0A. Verified official ITR-3 PDF schedule order, reconciled with the JSON schema (AY 2026-27)

Two official sources, read together:

- **PDF:** `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf`, extracted
  via `pdftotext -layout`. Line numbers are the PDF text-extraction line where each heading
  first appears, kept here as evidence so future re-audits don't have to re-derive the sequence.
- **Schema:** `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-3_2026_Main_V1.1 (2).json`.
  69 schedule blocks on the `ITR3` document node, 287 definitions. The schema's 12
  **required** top-level blocks are marked REQ below; the other 57 are optional (emitted
  only when the return carries that schedule's data).

The form prints these Parts and Schedules in exactly this sequence. The 60 PDF-position
phases/checkpoints in §4 preserve this order exactly: Phases 1–10 and 12–60 implement the 59
printed form sections, and Phase 11 records the documentary "SCHEDULES TO THE RETURN FORM"
banner as a non-emitting traceability checkpoint. There are **no bundled PDF sections** —
every printed section is its own phase. Each row names the PDF section **and** the schema block
the builder emits for it, so both sources are satisfied simultaneously.

| # | PDF section (as printed) | PDF line | Schema block(s) | REQ? | Notes |
|---:|---|---:|---|:---:|---|
| 1 | Personal Information (A1–A18) | 36 | `PartA_GEN1` | REQ | Identity, addresses, status, DOB/formation, Aadhaar, contact serialize into `PartA_GEN1` |
| 2 | Filing Status (A19) | 66 | `PartA_GEN1` + `PartA_GEN2` | REQ | Due date, filed-u/s, 10IEA regime cascade, seventh-proviso thresholds, residential status, director/partner/unlisted-equity, PE/SEP, IFSC, FPI, LEI |
| 3 | Audit Information (A20) | 272 | `PartA_GEN2.AuditInfo` | REQ | 44AA / 44AB / 92E / other-audit, auditor details |
| 4 | Nature of Business or Profession | 320 | `PartA_GEN2.NatOfBus` | REQ | Up to three main activities (code + description) |
| 5 | Part A-BS (Balance Sheet as on 31-Mar-2026) | 341 | `PARTA_BS` | REQ | `FundSrc` + `FundApply` + `NoBooksOfAccBS` |
| 6 | Part A-Manufacturing Account (FY 2025-26) | 498 | `ManufacturingAccount` | opt | `OpeningInventory`/`ClosingStock`/`CostOfGoodsPrdcd` |
| 7 | Part A-Trading Account (FY 2025-26) | 536 | `TradingAccount` | opt | `SaleOfGoods`/`SaleOfServices`/`OtherOperatingRevenueDtls`/`OperatingRevenueTotal`/… |
| 8 | Part A-P&L (Profit & Loss Account FY 2025-26) | 618 | `PARTA_PL` | REQ | `CreditsToPL`/`DebitsToPL`/`TaxProvAppr`/`NatOfBus44AD`/`PersumptiveInc44AD`/… |
| 9 | Part A-OI (Other Information) | 912 | `PARTA_OI` | opt | `MethodOfAcct`/`ProfDeviatDueAcctMeth`/`MethodOfValClgStk`/`NoCredToPLAmt`/`AmtDisallUs36`/`AmtDisallUs37` — **mandatory if 44AB-audit** |
| 10 | Part A-QD (Quantitative Details) | 1191 | `PARTA_QD` | opt | `TradingConcern`/`ManfactrConcern` — **mandatory if 44AB-audit** |
| 11 | **SCHEDULES TO THE RETURN FORM (FILL AS APPLICABLE)** | 1233 | (banner) | — | PDF banner before the return schedules begin |
| 12 | Schedule S — Income from Salary | 1235 | `ScheduleS` | opt | `Salaries`/`TotalGrossSalary`/`AllwncExemptUs10`/`Section10_13A`/`Increliefus89A`/`NetSalary`/`DeductionUS16` |
| 13 | Schedule HP — Income from House Property | 1283 | `ScheduleHP` | opt | `PropertyDetails`/`PassThroghIncome`/`TotalIncomeChargeableUnHP` |
| 14 | Schedule BP — Income from Business or Profession | 1411 (implied after HP) | `ITR3ScheduleBP` | REQ | `BusinessIncOthThanSpec`/`SpecBusinessInc`/`SpecifiedBusinessInc`/`IncChrgUnHdProftGain`/`BusSetoffCurrYr` |
| 15 | Schedule DPM — Depreciation on Plant and Machinery | 1549 | `ScheduleDPM` | opt | `PlantMachinery` |
| 16 | Schedule DOA — Depreciation on Other Assets | 1626 | `ScheduleDOA` | opt | `Land`/`Building`/`FurnitureFittings`/`IntangibleAssets`/`Ships` |
| 17 | Schedule DEP — Summary of Depreciation | 1695 | `ScheduleDEP` | opt | `SummaryFromDeprSch` (derived from DPM-17/18 + DOA-14/15) |
| 18 | Schedule DCG — Deemed Capital Gains on sale of depreciable assets | 1723 | `ScheduleDCG` | opt | `SummaryFromDeprSchCG` (derived from DPM-20 + DOA-17) |
| 19 | Schedule ESR — Expenditure on Scientific Research (S.35/35CCC/35CCD) | 1754 | `ScheduleESR` | opt | `DeductionUs35` |
| 20 | Schedule CG — Capital Gains | 1776 | `ScheduleCGFor23` | opt | `ShortTermCapGainFor23`/`LongTermCapGain23`/`SumOfCGIncm`/`IncmFromVDATrnsf`/`TotScheduleCGFor23`/`DeducClaimInfo`/`CurrYrLosses` |
| 21 | Schedule 112A (within CG) | 2535 | `Schedule112A` | opt | `Schedule112ADtls`/`SaleValue112A`/`CostAcqWithoutIndx112A`/`AcquisitionCost112A`/… |
| 22 | Schedule 115AD(1)(b)(iii) (within CG) | 2604 | `Schedule115AD` | opt | `Schedule115ADDtls`/`SaleValue115AD`/`CostAcqWithoutIndx115AD`/… |
| 23 | Schedule VDA — Virtual Digital Asset | 2667 | `ScheduleVDA` | opt | `ScheduleVDADtls`/`TotIncBusiness`/`TotIncCapGain` |
| 24 | Schedule OS — Income from Other Sources | 2690 | `ScheduleOS` | opt | `IncOthThanOwnRaceHorse`/`TotOthSrcNoRaceHorse`/`IncFromOwnHorse`/`IncChargeable`/`IncFrmLottery`/…/`DividendIncUs115BBDA` |
| 25 | Schedule CYLA — Set-off of current-year losses | 3005 | `ScheduleCYLA` | REQ | `Salary`/`HP`/`BusProfExclSpecProf`/`SpeculativeInc`/`SpecifiedInc`/`STCG20Per`/`STCG30Per`/`STCGAppRate` |
| 26 | Schedule BFLA — Set-off of brought-forward losses | 3073 | `ScheduleBFLA` | REQ | same head-breakdown as CYLA |
| 27 | Schedule CFL — Losses carried forward | 3165 | `ScheduleCFL` | opt | `LossCFFromPrev9thYearFromAY` … `LossCFFromPrev2ndYearFromAY` (AY-wise buckets) |
| 28 | Schedule UD — Unabsorbed depreciation & S.35(4) allowance | 3228 | `ITR3ScheduleUD` | opt | `CurrAssYr`/`CurBalCFNY`/`CurAllowBalCFNY`/`ScheduleUD`/`TotBFUDepritAmt`/… |
| 29 | Schedule ICDS — Effect of ICDS on profit | 3246 | `ScheduleICDS` | opt | `AccPolicyAmtDetl`/`InventoriesValueDetl`/`ConstContractsAmtDetl`/`RevenueRcgAmtDetl`/`TangibleFixedAssetDetl`/`ForeignExgRatesDetl`/`GovtGrantsDetl`/`SecuritiesDetl` |
| 30 | Schedule 10AA — Deduction under S.10AA | 3271 | `Schedule10AA` | opt | `DeductSEZ` |
| 31 | Schedule 80G — Donations (with/without qualifying PAN) | 3291 | `Schedule80G` | opt | `Don100Percent`/`Don50PercentNoApprReqd`/`Don100PercentApprReqd`/`Don50PercentApprReqd`/`TotalDonationsUs80G`/`TotalEligibleDonationsUs80G` |
| 32 | Schedule 80GGA — Donations for scientific research/rural development | 3361 | `Schedule80GGA` | opt | `DonationDtlsSciRsrchRuralDev`/… |
| 33 | Schedule 80GGC — Contributions to political parties | 3378 | `Schedule80GGC` | opt | `Schedule80GGCDetails`/… |
| 34 | Schedule 80DD — Maintenance/medical of disabled dependent | 3394 | `Schedule80DD` | opt | `NatureOfDisability`/`TypeOfDisability`/`DeductionAmount`/`DependentType`/`DependentPan`/`Form10IAFilingDate`/`Form10IAAckNum` |
| 35 | Schedule 80U — Deduction for person with disability | 3423 | `Schedule80U` | opt | `NatureOfDisability`/`TypeOfDisability`/`DeductionAmount`/`Form10IAFilingDate`/`Form10IAAckNum`/`UDIDNum` |
| 36 | Schedule RA — Donations to research associations | 3452 | `Schedule80RA` | opt | `DonationDtlsRsrchAssctn`/`TotalDonationAmtCash80RA`/`TotalDonationAmtOtherMode80RA`/`TotalDonationsUs80RA`/`TotalEligibleDonationAmt80RA`. S.35(1)(ii)/(iia)/(iii)/35(2AA) detail — distinct from `Schedule80GGA` (which holds `DonationDtlsSciRsrchRuralDev`). |
| 37 | Schedule 80-IA — Deductions for specified business profits | 3469 | `Schedule80_IA` | opt | `Sch80SectionCode`/`DeductUs80_IA_4_iv`/`TotSchedule80_IA` |
| 38 | Schedule 80-IB — Deductions under S.80-IB | 3485 | `Schedule80_IB` | opt | `Sch80SectionCode`/`DeductMinOilUs80_IB_9_Und`/`DeductHousUs80_IB_10_Und`/…/`TotSchedule80_IB` |
| 39 | Schedule 80-IE — Deductions under S.80-IE (North-East) | 3517 | `Schedule80_IC` | opt | **Naming divergence:** the PDF prints "80-IE"; the schema block is `Schedule80_IC` carrying `DeductInNorthEast`/`TotSchedule80_IC`. Phase 39 emits `Schedule80_IC` from the PDF's 80-IE data. (`Schedule80_IE` does not exist in the schema — confirmed: `defs["Schedule80_IE"]` is MISSING.) |
| 40 | Schedule VI-A — Chapter VI-A deductions | 3579 | `ScheduleVIA` + sub-blocks `Schedule80C`/`Schedule80D`/`Schedule80DD`/`Schedule80U`/`Schedule80E`/`Schedule80EE`/`Schedule80EEA`/`Schedule80EEB` | opt | `UsrDeductUndChapVIA`/`DeductUndChapVIA`. The 80C-family each have their own optional schema block emitted alongside `ScheduleVIA`; `Schedule80RA` is the separate top-level block for PDF Schedule RA at position 36. |
| 41 | Schedule AMT — Alternate Minimum Tax (S.115JC) | 3664 | `ScheduleAMT` | opt | `TotalIncItem11`/`AdjustmentSec115JC`/`AdjustedUnderSec115JC`/`AdjustedUnderSec115JCIFSC`/`AdjustedUnderSec115JCOther`/`TaxPayableUnderSec115JC` |
| 42 | Schedule AMTC — AMT credit (S.115JD) | 3690 | `ScheduleAMTC` | opt | `TaxSection115JC`/`TaxOthProvisions`/`AmtTaxCreditAvailable`/`ScheduleAMTCDtls`/… |
| 43 | Schedule SPI — Income of specified persons (S.64) | 3737 | `ScheduleSPI` | opt | `SpecifiedPerson` |
| 44 | Schedule SI — Income chargeable at special rates | 3748 | `ScheduleSI` | opt | `SplCodeRateTax`/`TotSplRateInc`/`TotSplRateIncTax` |
| 45 | Schedule IF — Income from firms in which partner | 3864 | `ScheduleIF` | opt | `PartnerFirmDetails`/`TotalProfitShareAmt`/`TotalIntrstAmtDueOrRecv`/`TotalRemunernAmtDueOrRecv`/`TotalFirmCapBalOn31Mar` |
| 46 | Schedule EI — Exempt Income | 3885 | `ScheduleEI` | opt | `InterestInc`/`GrossAgriRecpt`/`ExpIncAgri`/`UnabAgriLossPrev8`/`AgriIncRule7and8`/`NetAgriIncOrOthrIncRule7`/`ExcNetAgriInc`/`OthersInc` |
| 47 | Schedule PTI — Pass-Through Income (S.115U/UA/UB) | 3924 | `SchedulePTI` | opt | `SchedulePTIDtls` |
| 48 | Schedule TPSA — Tax on secondary adjustments under S.92CE(2A) | 3988 | `ScheduleTPSA` | opt | `AmtPrimaryAdjUs92CE_2A`/`AdditionalIncTax18PercAbove`/`Surcharge12Perc`/`HealthEducationCess`/`TotalAdditionalTax`/`TaxesPaid`/`NetTaxPayable`/`DtlsTaxesPaid`; triggered by Part A-OI item 18 |
| 49 | Schedule FSI — Income from outside India & tax relief | 4026 | `ScheduleFSI` | opt | `ScheduleFSIDtls`; resident-only |
| 50 | Schedule TR — Summary of tax relief for taxes paid outside India | 4058 | `ScheduleTR1` | opt | **Naming divergence:** PDF "Schedule TR" ↔ schema `ScheduleTR1`; `ScheduleTR`/`TotalTaxPaidOutsideIndia`/`TotalTaxReliefOutsideIndia`/`TaxReliefOutsideIndiaDTAA`/`TaxReliefOutsideIndiaNotDTAA`/`AmtTaxRefunded`/`AssmtYrTaxRelief` |
| 51 | Schedule FA — Foreign Assets & income from any source outside India | 4091 | `ScheduleFA` | opt | `DetailsForiegnBank`/`DtlsForeignCustodialAcc`/`DtlsForeignEquityDebtInterest`/`DtlsForeignCashValueInsurance`/`DetailsFinancialInterest`/`DetailsImmovableProperty`/`DetailsOthAssets`/`DetailsOfAccntsHvngSigningAuth`; resident-only |
| 52 | Schedule 5A — Apportionment of income (Portuguese Civil Code, S.5A) | 4227 | `Schedule5A2014` | opt | **Naming divergence:** PDF "Schedule 5A" ↔ schema `Schedule5A2014`; `NameOfSpouse`/`PANOfSpouse`/`AadhaarOfSpouse`/`BooksSpouse44ABFlg`/`BooksSpouse92EFlg`/`HPHeadIncome`/`BusHeadIncome`/`CapGainHeadIncome` |
| 53 | Schedule AL — Assets & Liabilities at year-end (other than Part A-BS) | 4248 | `ScheduleAL` | opt | `ImmovableDetails`/`MovableAsset`/`InterstAOPFlag`/`InterestHeldInaAsset`/`LiabilityInRelatAssets`; applies where income > ₹50 lakh |
| 54 | Schedule GST — Turnover/Gross Receipt reported for GST | 4288 | `ScheduleGST` | opt | `TurnoverGrsRcptForGSTIN` array of `{GSTINNo, AmtTurnGrossRcptGSTIN}` |
| 55 | ESOP (employee stock-option tax deferral) | 4314 | `ScheduleESOP` | opt | `PanofStartUp`/`DPIITRegNo`/year-wise ESOP type fields/`TotalTaxAttributedAmt` |
| 56 | Part B-TI — Computation of Total Income | 4394 | `PartB-TI` | REQ | `Salaries`/`IncomeFromHP`/`ProfBusGain`/`CapGain`/`IncFromOS`/`TotalTI`/`CurrentYearLoss`/`BalanceAfterSetoffLosses` |
| 57 | Part B-TTI — Computation of Tax Liability on Total Income | 4491 | `PartB_TTI` | REQ | `ComputationOfTaxLiability`/`TaxPaid`/`Refund`/`AssetOutIndiaFlag` |
| 58 | Tax Return Preparer (TRP) details | 4617 | `TaxReturnPreparer` | opt | `IdentificationNoOfTRP`/`NameOfTRP`/`ReImbFrmGov` |
| 59 | Section 17 — Tax Payments (A/B/C/D) | 4622 | `ScheduleIT` (A) + `ScheduleTDS1` (B) + `ScheduleTDS2` (C) + `ScheduleTDS3` (C, non-salary) + `ScheduleTCS` (D) | opt | The PDF prints these as Section 17 lettered subsections. `ScheduleIT.TaxPayment`/`TotalTaxPayments`; `ScheduleTDS1.TDSonSalary`/`TotalTDSonSalaries`; `ScheduleTDS2.TDSOthThanSalaryDtls`/`TotalTDSonOthThanSals`; `ScheduleTDS3.TDS3onOthThanSalDtls`/`TotalTDS3OnOthThanSal`; `ScheduleTCS.TCS`/`TotalSchTCS` |
| 60 | Verification | 4715 | `Verification` | REQ | `Declaration`/`Capacity`/`Date`/`Place` |

## 0B. Schema-only blocks with no standalone PDF schedule (emitted by the builder, not their own phases)

These schema blocks have **no printed section heading** in the notified PDF — they are
envelope or sub-schedule structures emitted by the builder in the phase that owns their PDF
data. They do not create extra phases; the implementation phase order remains the PDF order
in §0A.

| Schema block | REQ? | Where its data comes from | Emitting phase |
|---|:---:|---|---|
| `CreationInfo` | REQ | Schema envelope (Digest, schema version, mode) | Phase 60 (final Verification serialization gate) |
| `Form_ITR3` | REQ | Schema envelope (form name, AY) | Phase 60 |
| `Schedule80C` / `Schedule80D` / `Schedule80E` / `Schedule80EE` / `Schedule80EEA` / `Schedule80EEB` | opt | PDF Schedule VI-A (line 3579), broken out into per-section schema blocks | Phase 40 (`ScheduleVIA`) — emit each sub-block alongside `ScheduleVIA`; standalone PDF Schedule 80DD and 80U are emitted at Phases 34 and 35 respectively |
| `Schedule80_IE` | — | No such schema block. PDF Schedule 80-IE is represented by schema block `Schedule80_IC` (`DeductInNorthEast`/`TotSchedule80_IC`) | Phase 39 (`Schedule80_IC`) |
| `ScheduleRA` | — | No such schema block. The PDF label "Schedule RA" is represented by the actual schema block `Schedule80RA` (`DonationDtlsRsrchAssctn` rows, distinct from `Schedule80GGA`) | Phase 36 (`Schedule80RA`) |

> **Net reconciliation:** the 60 PDF-position phases/checkpoints in §4 preserve the official
> order and emit every official ITR-3 schema block. PDF-only labels (Personal Information,
> Filing Status, Audit Information, Nature of Business) map into `PartA_GEN1`/`PartA_GEN2`.
> The documentary banner at PDF position 11 is Phase 11 and emits no JSON. Schema-only naming
> is explicitly handled: PDF Schedule TR → `ScheduleTR1`, PDF Schedule 5A → `Schedule5A2014`,
> PDF Schedule 80-IE → `Schedule80_IC`, PDF Schedule RA → `Schedule80RA` (distinct from
> `Schedule80GGA`). `ScheduleGST`, `ScheduleESOP`, `ScheduleTPSA`, and the tax-payment blocks
> are all printed form sections and therefore have their own phases in the corrected order.
> `CreationInfo` and `Form_ITR3` are the only true schema-envelope blocks with no PDF section;
> they emit in Phase 60. Phases 61–63 are post-form integration (legacy cleanup, frontend
> wiring, final verification) and do not map to PDF positions.

---

## 1. Background — why this plan exists

`Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` §6 states the exact checklist a
production-ready form satisfies: one canonical mapper, dispatch added to
`filing_gateway_v2.py` (never the dead `filing_gateway.py`), CBDT validators actually wired
in before JSON emission, frontend hitting only `/v2/*` and `/api/v1/filing/*`, persistence
via `ClientITR.form_data` as serialized `ReturnDraft`, Digest via `app/eri/digest.py`, and
Type-3 submission working via the existing form-agnostic uploader. ITR-1, ITR-2, and ITR-4
already satisfy this contract. ITR-3 does not. Verified current state (read this session,
cross-checked against actual code):

| Layer | ITR-3 state today |
|---|---|
| `app/schemas/itr3.py` | 264 lines. Imports ITR-2's CG/VDA/FSI/TR/SPI/AMT types + ITR-1's salary/HP/OS/Chapter6A/TDS/TCS. Adds `BusinessIncome` (flat `net_profit_before_tax` scalar — **does not mirror the full Schedule BP tree**), `BalanceSheet`, `AuditInfo`, `PartnerInFirm`, `UDEntry`, `NatureOfBusiness`. |
| `app/engine/calculators/itr3.py` | 581 lines, substantively complete (PGBP, salary, HP, CG, OS, SPI, IF, CYLA/BFLA/CFL, deductions, special rates, AMT, relief, interest, credits, payable/refund). **Defects:** consumes the flat `BusinessIncome.net_profit_before_tax` scalar instead of the full Schedule BP structure; stubs unabsorbed-depreciation setoff to `Decimal("0")` despite `ud_entries`; AMT recompute is order-dependent; CFL has a dead conditional branch. |
| `app/engine/itd/itr3.py` | 1131 lines. **`build_itr3_json(result, pan=..., first_name=..., ...)` — 15+ loose string params, NOT the canonical `(result, typed_input)` contract** used by `build_itr{1,2,4}_json`. Hardcodes `"Verification"["Date"]="2026-07-31"`. Fabricates zero-block schedules (`_schedule_dep()`/`_schedule_dcg()`/`_schedule_icds()`/`_schedule_esr()`/`_schedule_80ia()` etc.) instead of reading real values from the typed input / result. `_schedule_cfl()` emits `float(...)` values (not `_to_rupees()`) — risks schema-invalid `Decimal` vs. `type: integer` failures. |
| `app/engine/itd/itr3_schema.py` | **Does not exist.** `itr1/itr2/itr4_schema.py` all exist; no `validate_itr3_json`. |
| `app/engine/validators/itr3/` | 57 lines total — stubs. `input_rules.py` returns an empty successful `ValidationReport`; `calc_rules.py` always returns `can_upload=True`. |
| `app/engine/draft_to_itr3_input.py` | **Does not exist.** Zero references anywhere in the codebase. |
| `app/engine/filing_gateway_v2.py` | Rejects ITR-3 at both `compute_canonical` and `generate_cbdt_json`. No `ITR3PipelineResult`, no `compute_canonical_itr3`, no `_generate_cbdt_json_itr3`, no `_itr3_filing_profile`. |
| `app/engine/filing_orchestrator.py` | Explicitly raises `FilingOrchestratorError("ITR-3 filing is not supported...")`. |
| `app/routers/itr.py` | Legacy `/itr3/compute` and `/itr3/compute-json` routes call `compute_itr3(body)` / `build_itr3_json(result)` directly on `ITR3Input` — no `ReturnDraft`, no ITR-3 validators, no filing profile, all identity fields default to placeholders. |
| `app/routers/filing.py` | `_normalize_form()` rejects ITR-3; both Type-2 and Type-3 submission paths blocked. |
| `app/schemas/return_draft.py` | Has all ITR-2/3 additive schedule types (CFL/SI/FSI/TR/FA/SPI/PTI/AMT/AL/5A/ESOP/`bpNetProfit`/`businesses`); **no typed ITR-3 core-schedule fields** (PartA_GEN2 audit/nature-of-business, PartA_BS, PartA_PL, ITR3ScheduleBP full tree, DPM/DOA/DEP/DCG, UD, IF, GST, ICDS, ESR, 80-IA/IB/IE/10AA, Manufacturing/Trading). |
| `frontend/src/components/business/ITR3BusinessWorkspace.tsx` | Five-step workflow exists. `ITR3BusinessCoreManager`/`ITR3BusinessAuxiliaryManager` edit ITR-3 core schedules as generic `CanonicalObject` blobs. State cached in **`localStorage`** under `ITR3Core`/`ITR3Auxiliary` — **never written to `draft`**, so never persisted, never reaches the backend mapper, never appears in generated CBDT JSON. |
| `frontend/src/pages/ITRComputationPage.tsx` | ITR-3 selectable in form dropdown, but gates ITR-3 out of CBDT JSON generation (`handleGenerateCbdtJson`), Direct Submit (`handleDirectSubmit`), and PDF download. `PersonalInfoTab.tsx` gates the director/unlisted-equity block to ITR-2 only. |
| `frontend/src/domain/scheduleRegistry.ts` | Lists every ITR-3 schedule — all marked `status: 'missing'`. |
| Tests | No canonical ITR-3 mapper/gateway/builder/validator/filing test suite. Existing ITR-3 references mostly assert that ITR-3 is rejected. |

This plan closes every one of these gaps, **in official PDF schedule order**, with the same
rigor `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` used to bring ITR-4 to parity.

---

## 2. Guiding principles (non-negotiable — copied from the ITR-4/ITR-2 plan, still binding)

1. **ITR-1, ITR-2, and ITR-4 must not break.** No commit lands that turns any regression suite red.
2. **One phase at a time**, each independently testable, each ending with a green-test gate.
3. **Tests first.** Every phase has a test list; not complete until its own tests pass **and** the ITR-1/2/4 suites stay green.
4. **Commit per phase**, referencing this doc; this doc's status flips ⬜→✅ after tests pass.
5. **Preparation before calculation.** ITR-3 must construct one complete typed input — including filing profile, property profile, bank accounts, verification, representative/Karta details, TRP where applicable, and **all core business schedules** (Part A-BS, Manufacturing, Trading, P&L, Part A-OI, Part A-QD, Schedule BP, depreciation, IF, UD, etc.) — before invoking its calculator. JSON generation may only serialize the prepared input.
6. **No shortcut code.** Everything touched in `app/eri/`, `app/engine/`, or the filing pipeline is production-grade and reused unchanged later.
7. **Never route through `app/engine/filing_gateway.py`.** `filing_gateway_v2.py`'s dispatch is the only place ITR-3 gets added.
8. **Schedulewise order.** Phases are numbered in official PDF order. A cross-cutting prerequisite is listed as a gate inside the phase that first needs it — never pulled forward into a standalone pre-phase.

---

## 3. Target architecture (after this plan)

The invariant is the same one ITR-1, ITR-2, and ITR-4 satisfy:

```text
One persisted ReturnDraft
    → one complete ITR-3 prepared input (identity + filing profile + all schedules)
        → input validation
        → one calculation result
            ├── compute summary
            └── CBDT JSON
                → official schema validation (itr3_schema.py)
                → digest / submission
```

```text
ClientITR.form_data = JSON(ReturnDraft)
  └─ ITR-3: draft_to_itr3_input → complete ITR3Input → compute_itr3 → build_itr3_json
```

The serializer (`build_itr3_json`) reads only the prepared typed input — it must not
reconstruct identity/address/verification/TDS/bank from `ReturnDraft` or perform
`model_copy(update={...})` enrichment after calculation. This is the Phase 5G standard
ITR-2 now meets; ITR-3 inherits it.

---

## 4. Phase-wise plan (in official PDF schedule order)

Each phase below carries: **PDF anchor** (the section it implements), **draft schema gate**
(new typed fields on `ReturnDraft` / `types.ts`, required before this phase can map), **input
schema gate** (new typed fields on `ITR3Input`), **mapper gate** (`draft_to_itr3_input.py`
extension), **calculator gate** (`app/engine/calculators/itr3.py` consumer), **builder gate**
(`build_itr3_json` emitter), **validator gate** (`app/engine/validators/itr3/` rule), and
**frontend gate** (UI editing + `scheduleRegistry` status flip). A gate is only listed when
it first fires for that schedule; later phases that merely reuse the same gate are silent.

Phases marked **[cross-cutting]** are the four prerequisites that do not map to a single PDF
field but must land **at** the PDF section that first needs them (not before all sections):
the `ReturnDraft` typed-field extension and frontend `localStorage`→`draft` migration land at
Phase 1 (Personal Information), the canonical mapper + gateway dispatch land at Phase 2
(Filing Status, the first phase that needs canonical mapping), and the builder signature fix +
`itr3_schema.py` land at Phase 60 (Verification, the final serialization gate). They are
**not** pulled forward.

> **Phase-numbering note.** The §0A table and §4 use the same canonical numbering:
> positions 1–60 follow the printed PDF exactly, including the documentary "SCHEDULES TO
> THE RETURN FORM" banner at position 11. Phases 1–10 and 12–60 implement the corresponding
> printed sections; Phase 11 is a non-emitting traceability checkpoint for the banner. There
> are no bundled PDF sections. Phases 61–63 are explicitly post-form integration phases
> (legacy cleanup, frontend wiring, and final verification), and do not correspond to PDF
> positions.

### Phase 1 — Personal Information (A1–A18)  [cross-cutting: draft fields + frontend migration]

**PDF anchor:** PDF line 36. Identity, address, contact, Aadhaar, status, and DOB/formation fields.

This is the first PDF section and the first thing the user edits, so the two cross-cutting
prerequisites that the rest of the plan depends on land here:

**Gate 1A — Extend `ReturnDraft` with ITR-3 core-schedule typed fields.** Additive,
nullable/optional, `extra="forbid"` preserved. This phase creates the typed storage surface
for all ITR-3 sections; the content-specific mapper and builder work remain at the matching
PDF phases below:
- `app/schemas/return_draft.py`: `itr3_part_a_gen2` (audit information, nature-of-business
  list, filing-status disclosures, unlisted-equity share holdings, director/partner/PE/SEP/
  IFSC/FPI/LEI disclosures). The remaining core-schedule fields (`itr3_part_a_bs`,
  `itr3_part_a_pl`, `itr3_schedule_bp`, `itr3_manufacturing_account`, `itr3_trading_account`,
  `itr3_part_a_oi`, `itr3_part_a_qd`, `itr3_depreciation` (DPM/DOA/DEP/DCG), `itr3_schedule_ud`,
  `itr3_schedule_if`, `itr3_schedule_icds`, `itr3_schedule_esr`, `itr3_business_deductions` (10AA/80G/80GGA/
  80GGC/80DD/80U/RA/80-IA/80-IB/80-IE), `itr3_schedule_tpsa`) are declared here too (as
  `None` defaults) so every later phase only fills its own field — no schema churn later.
- `frontend/src/domain/returns/types.ts`: mirror types exactly.
- `frontend/src/domain/returns/factory.ts`: `createEmptyReturnDraft` seeds the new fields.
- `frontend/src/domain/returns/canonicalRepository.ts`: `normalizeLoadedDraft` backfills.
- `frontend/src/domain/returns/editorModelV2.ts`: typed updaters.

**Gate 1B — Frontend `localStorage` → `draft` migration.** The `ITR3Core`/`ITR3Auxiliary`
`localStorage` blobs become typed `draft.itr3_*` fields. `ITR3BusinessCoreManager` and
`ITR3BusinessAuxiliaryManager` read/write through `editorModelV2` updaters instead of
`localStorage`. `PersonalInfoTab.tsx` opens the director/unlisted-equity block to ITR-3
(currently ITR-2-only). Verification capacity options extended for Karta/representative.
`scheduleRegistry.ts` flips Personal Info / Filing Status statuses to `'available'`.

**Exit criteria:** `ReturnDraft(form="ITR-3")` validates; `tsc -b` + `vitest` green; ITR-1/2/4
regression green; ITR-3 personal-info edits persist through `PUT /v2/clients/{id}/itr/{year}`.

### Phase 2 — Filing Status (A19)

**PDF anchor:** PDF line 66. Return-type, section (139(1)/139(4)/139(5)/139(3)/119), audit
trigger, Form 10-IEA new-regime/old-regime cascade, seventh-proviso thresholds, residential
status, director / unlisted-equity-shareholder / partner / PE / SEP / IFSC-unit / FPI / LEI
disclosures. ITR-2 shares this section's residential-status + director + unlisted-equity +
partner + PE/SEP + IFSC + FPI + LEI sub-blocks; ITR-3's filing-status field on `ReturnDraft`
already exists from ITR-2's build-out. Phase 2 maps the ITR-3-unique Form 10-IEA cascade and
seventh-proviso rows into `PartA_GEN1`/`PartA_GEN2`.

**Gate 2A — Mapper.** `draft_to_itr3_input.py` is created here [cross-cutting: canonical
mapper] as `draft_to_itr3_input(draft) -> tuple[ITR3Input, dict[str, Any]]`, reusing every
shared head mapper from `draft_to_itr1_input.py` (salary/HP/OS/CG/TDS/TCS/tax-payments/bank/
dates) and `draft_to_itr2_input.py` (BF losses/SI/FSI/TR/SPI/AMT/AL/5A/ESOP). Phase 2 maps
`draft.filing_status` → `ITR3Input` filing-status sub-blocks, including the ITR-3-unique
Form 10-IEA regime-cascade fields and seventh-proviso turnover/gross-receipt thresholds.
It also reuses ITR-2's residential-status / director / partner / PE-SEP / IFSC / FPI / LEI
head mappers from `draft_to_itr2_input.py`.

**Gate 2B — `filing_gateway_v2.py` dispatch wired here** [cross-cutting: gateway]. Adds
`ITR3PipelineResult`, `compute_canonical_itr3(draft)`, `_itr3_filing_profile(draft)`
(adapter over `normalize_personal_profile` — ITR-3 supports SELF/REPRESENTATIVE/KARTA like
ITR-2, plus PARTNER for firm returns), `_generate_cbdt_json_itr3(draft)`. `compute_canonical`
dispatches ITR-3 → `compute_canonical_itr3`; `generate_cbdt_json` dispatches →
`_generate_cbdt_json_itr3`. `filing_orchestrator.py` removes the explicit ITR-3 rejection.
CBDT Category A/B/D validation runs only inside `_generate_cbdt_json_itr3`.
`compute_canonical_itr3` attaches the complete filing profile via `model_copy` **before**
`compute_itr3` (Phase 5G parity).

**Gate 2C — Builder** emits the `PartA_GEN1` filing-status fields and `PartA_GEN2`
filing-status fields from `typed_input` (not placeholders).

**Gate 2D — Validator** adds Form 10-IEA single-regime-answer + 139(1)-vs-139(4)/5/3 mutual
exclusivity rules.

**Exit criteria:** a filing-status fixture round-trips draft → input → JSON
`PartA_GEN1`/`PartA_GEN2` filing-status fields; ITR-1/2/4 regression green.

### Phase 3 — Audit Information (A20)

**PDF anchor:** PDF line 272. 44AA/44AB/92E/other-audit applicability, auditor details,
audit-report date & acknowledgement, 44AB turnover-range + cash-receipts/payments
percentages. First ITR-3-unique Part A block.

**Gate 3A — `ITR3Input.part_a_gen2`** gains the audit-info sub-block (audit applicability 44AA/
44AB/92E/other, auditor details, audit-report date & acknowledgement). The canonical mapper
created in Phase 2 extends its mapping with `draft.itr3_part_a_gen2.audit_info` →
`ITR3Input.part_a_gen2.audit_info`.

**Gate 3B — Builder** emits `PartA_GEN2.AuditInfo` from
`typed_input.part_a_gen2.audit_info` (not a placeholder).

**Gate 3C — Validator** adds 44AA/44AB/92E applicability, auditor acknowledgement, and
44AB turnover-range/cash-receipts/payments consistency rules.

**Exit criteria:** `compute_canonical_itr3` returns a populated summary for an audit fixture;
ITR-1/2/4 regression green.

### Phase 4 — Nature of Business or Profession

**PDF anchor:** PDF line 320. Up to three main business/profession activities (code + description).

**Gate 4A — `ITR3Input.part_a_gen2.nature_of_business: list[NatureOfBusiness]`** (already
exists on the schema — verify against PDF). **Mapper** maps `draft.itr3_part_a_gen2.nature_of_business`.
**Builder** emits `PartA_GEN2.NatOfBus` from `typed_input`.

**Exit criteria:** a nature-of-business fixture round-trips draft → input → JSON
`PartA_GEN2.NatOfBus`; ITR-1/2/4 regression green.

### Phase 5 — Part A-BS (Balance Sheet)

**PDF anchor:** PDF line 341. Sources of funds + Application of funds + No-Account-Case.

**Gate 5A — `ITR3Input.part_a_bs: ITR3PartABSInput`** (proprietor's fund, reserves breakdown,
secured/unsecured loans, deferred tax liability, advances, fixed assets, investments, current
assets, loans & advances, current liabilities & provisions, misc expenditure, P&L accumulated
balance, no-account-case totals).

**Gate 5B — `draft_to_itr3_input.py`** maps `draft.itr3_part_a_bs` → `part_a_bs`.

**Gate 5C — `build_itr3_json`** emits `PARTA_BS` from `typed_input.part_a_bs` (not a placeholder).

**Exit criteria:** a balance-sheet fixture round-trips draft → input → JSON `PARTA_BS`; ITR-1/2/4 green.

### Phase 6 — Part A-Manufacturing Account

**PDF anchor:** PDF line 498. Opening inventory, purchases, direct wages/expenses, factory
overheads, closing stock, cost of goods produced.

**Gate 6A — `ITR3Input.manufacturing_account: ITR3ManufacturingAccountInput`.**
**Gate 6B — Mapper** maps `draft.itr3_manufacturing_account`.
**Gate 6C — Builder** emits `ManufacturingAccount` from `typed_input` (conditional on presence).

**Exit criteria:** manufacturing fixture round-trips; ITR-1/2/4 green.

### Phase 7 — Part A-Trading Account

**PDF anchor:** PDF line 536. Credits (revenue from operations, duties/taxes, closing stock),
debits (opening stock, purchases, direct expenses, duties/taxes, cost of goods produced),
gross profit, intraday & F&O turnover/income.

**Gate 7A — `ITR3Input.trading_account: ITR3TradingAccountInput`** (including intraday & F&O line items).
**Gate 7B — Mapper** maps `draft.itr3_trading_account`.
**Gate 7C — Builder** emits `TradingAccount`.

**Exit criteria:** trading fixture round-trips; ITR-1/2/4 green.

### Phase 8 — Part A-P&L (Profit & Loss Account)

**PDF anchor:** PDF line 618. Credits (gross profit, other income), debits (freight, stores,
power, rents, repairs, compensation, insurance, welfare, entertainment, advertisement,
commission, royalty, professional fees, hotel, travel, conveyance, telephone, guest house,
club, festival, scholarship, gift, donation, rates & taxes, audit fee, other expenses, bad
debts, provisions), net profit before tax (item 53), presumptive cases (items 61–66).

**Gate 8A — `ITR3Input.part_a_pl: ITR3PartAPLInput`** with full line-item granularity and the
presumptive sub-tables (44AD/44ADA/44AE/no-account-case/non-resident 44B-family).
**Gate 8B — Mapper** maps `draft.itr3_part_a_pl`.
**Gate 8C — Builder** emits `PARTA_PL`.

**Exit criteria:** P&L fixture round-trips; ITR-1/2/4 green.

### Phase 9 — Part A-OI (Other Information)

**PDF anchor:** PDF line 912. **Mandatory if 44AB-audit.** Accounting method, ICDS deviations,
stock valuation, S.28/36/37/40/40A/43B/14A/41/33AB/33ABA/92CE(2A) disallowances.

**Gate 9A — `ITR3Input.part_a_oi: ITR3PartAOIInput`** with every sub-table (S.36(1)(a)–(xviii),
S.37(1)/(2B), S.40(a)/(b)/(ba), S.40A(2)(b)/(3)/(7)/(9), S.43B, S.14A, S.41, S.33AB/33ABA,
92CE(2A) option).
**Gate 9B — Mapper** maps `draft.itr3_part_a_oi`.
**Gate 9C — Builder** emits `PARTA_OI` (conditional on 44AB applicability — Phase 3 audit gate).

**Exit criteria:** Part A-OI fixture round-trips; ITR-1/2/4 green.

### Phase 10 — Part A-QD (Quantitative Details)

**PDF anchor:** PDF line 1191. **Mandatory if 44AB-audit.** Trading concern + manufacturing
concern stock movement.

**Gate 10A — `ITR3Input.part_a_qd: ITR3PartAQDInput`.**
**Gate 10B — Mapper** maps `draft.itr3_part_a_qd`.
**Gate 10C — Builder** emits `PARTA_QD`.

**Exit criteria:** Part A-QD fixture round-trips; ITR-1/2/4 green.

### Phase 11 — SCHEDULES TO THE RETURN FORM banner (traceability checkpoint)

**PDF anchor:** PDF line 1233. Documentary banner: "SCHEDULES TO THE RETURN FORM (FILL AS
APPLICABLE)". This phase has no draft field, input model, calculator, builder, or validator
work and emits no JSON; it is retained so the implementation sequence has an explicit
checkpoint at the exact PDF transition from Part A-QD to the return schedules.

**Exit criteria:** the schedule phase checklist is opened only after Phases 1–10 pass; no
JSON block is emitted for the banner; ITR-1/2/4 regression green.

### Phase 12 — Schedule S (Income from Salary)

**PDF anchor:** PDF line 1235. Gross salary, exempt allowances, S.16 deductions, 89A relief.

**Gate 12A — Mapper** reuses `draft_to_itr1_input._map_salary` (already shared).
**Gate 12B — Builder** emits `ScheduleS` from `typed_input.salary` (already-shaped; ITR-3's
Schedule S mirrors ITR-2's).
**Gate 12C — Validator** adds S.17(1)/(2)/(3) breakdown + S.16 cap rules.
**Exit criteria:** salary fixture round-trips; ITR-1/2/4 green.

### Phase 13 — Schedule HP (Income from House Property)

**PDF anchor:** PDF line 1283. Let-out/self-occupied/deemed let-out, co-ownership, pass-through.

**Gate 13A — Mapper** reuses `_map_house_properties` (shared).
**Gate 13B — Builder** emits `ScheduleHP`.
**Gate 13C — Validator** adds co-ownership-share + 234/24 rules.
**Exit criteria:** HP fixture round-trips; ITR-1/2/4 green.

### Phase 14 — Schedule BP (Income from Business or Profession)  [cross-cutting: calculator PGBP restructure]

**PDF anchor:** PDF line 1411. Full PGBP tree: A (other than speculative/specified), B
(speculative), C (specified 35AD), D (chargeable PGBP), E (intra-head set-off).

**Gate 14A — Replace `BusinessIncome` (flat scalar) with `ITR3ScheduleBPInput`** (structured
`business_inc_oth_than_spec` with the full 1–38 line-item tree: profit before tax,
speculative/specified split-out, income credited to other heads, 44AD/ADA/AE/B-family
split-out, Rule 7/7A/7B(1)/7B(1A)/8 split-out, exempt income, S.14A, depreciation per books
vs. IT-Act, disallowances S.36/37/40/40A/43B, deemed incomes S.41/32AD/33AB/33ABA/35ABA/35ABB/
40A(3A)/72A/80HHD/80-IA, 43CA, ICDS adjustments, S.32(1)(iii) deduction, S.35/35CCC/35CCD
excess, 44AD/ADA/AE/B-family deemed profits, intra-head set-off).
**Gate 14B — Calculator** (`app/engine/calculators/itr3.py`) consumes the structured
`ITR3ScheduleBPInput` instead of `net_profit_before_tax`. Fixes the unabsorbed-depreciation
setoff stub. Fixes the AMT order-dependence. Fixes the CFL dead branch.
**Gate 14C — Mapper** maps `draft.itr3_schedule_bp` → `schedule_bp`.
**Gate 14D — Builder** emits `ITR3ScheduleBP` from `typed_input.schedule_bp` + `ITR3Result.schedules["bp"]`.
**Gate 14E — Validator** adds Schedule BP arithmetic (item 34 = 13+26-33; item D = A37+B42+C48; intra-head set-off E).
**Exit criteria:** a real PGBP fixture round-trips with line-item granularity (not a scalar);
calculator defects fixed; ITR-1/2/4 green.

### Phase 15 — Schedule DPM (Depreciation on Plant & Machinery)

**PDF anchor:** PDF line 1549. Block-wise WDV, additions ≥/<180 days, full/half rate,
additional depreciation, S.38(2), S.50.

**Gate 15A — `ITR3Input.depreciation.dpm: list[DPMBlockInput]`.**
**Gate 15B — Mapper** maps `draft.itr3_depreciation.dpm`.
**Gate 15C — Builder** emits `ScheduleDPM` (conditional on presence — currently a fabricated zero block).
**Gate 15D — Validator** adds block-WDV continuity + S.50 capital-gains sign rules.
**Exit criteria:** DPM fixture round-trips; ITR-1/2/4 green.

### Phase 16 — Schedule DOA (Depreciation on Other Assets)

**PDF anchor:** PDF line 1626. Land/Building/Furniture/Intangibles/Ships.
**Gate 16A–16D** mirror Phase 15 for `DOABlockInput` → `ScheduleDOA`.

### Phase 17 — Schedule DEP (Summary of Depreciation)

**PDF anchor:** PDF line 1695. Pulls from DPM-17/18 + DOA-14/15.
**Gate 17A — Builder** emits `ScheduleDEP` as a pure aggregation of DPM+DOA totals (no new
input — it's a derived schedule). **Validator** checks DEP totals reconcile to DPM+DOA.

### Phase 18 — Schedule DCG (Deemed Capital Gains on sale of depreciable assets)

**PDF anchor:** PDF line 1723. Pulls from DPM-20 + DOA-17.
**Gate 18A — Builder** emits `ScheduleDCG` (derived from DPM/DOA transfer rows). **Validator**
checks DCG pulls correctly from DPM-20/DOA-17. Currently a fabricated zero block.

### Phase 19 — Schedule ESR (Expenditure on Scientific Research)

**PDF anchor:** PDF line 1754. S.35/35CCC/35CCD: debited vs. deductible vs. excess.
**Gate 19A — `ITR3Input.schedule_esr: ITR3ESRInput`.** **Mapper** maps
`draft.itr3_schedule_esr`. **Builder** emits `ScheduleESR` (currently fabricated). **Validator**
checks ESR item x(4) flows to Schedule BP item 28.

### Phase 20 — Schedule CG (Capital Gains)

**PDF anchor:** PDF line 1776. STCG (land/building, slump sale, 111A), LTCG (land/building,
slump sale, 111/112, 112A), VDA, 50C, 54-family exemptions.

**Gate 20A — Mapper** reuses `draft_to_itr2_input._map_capital_gains` (shared — ITR-3's CG
mirrors ITR-2's). **Builder** emits `ScheduleCGFor23` from `typed_input.capital_gains` +
`ITR3Result.schedules["cg"]` (currently `_DummyCG` fabricates an all-zero CG when absent —
replace with conditional omission). **Validator** adds 50C 1.10× rule, 54-family exemption
recapture, 112A cost recapture. `scheduleRegistry.ts` flips CG to `'available'`.

### Phase 21 — Schedule 112A (within CG)

**PDF anchor:** PDF line 2535. STT-paid equity/MF special-rate computation.
**Gate 21A — Mapper** reuses ITR-2's `_map_capital_gains` 112A sub-mapping. **Builder** emits
the 112A sub-schedule within `ScheduleCGFor23`. **Validator** adds 112A ₹1.25L exemption + sliding-scale.

### Phase 22 — Schedule 115AD(1)(b)(iii) (within CG)

**PDF anchor:** PDF line 2604. Non-resident STT-paid special rate.
**Gate 22A — Mapper** reuses ITR-2's 115AD sub-mapping. **Builder** emits 115AD sub-schedule.
**Validator** adds 115AD(1)(b)(iii) rules.

### Phase 23 — Schedule VDA (Virtual Digital Asset)

**PDF anchor:** PDF line 2667. S.2(47A)/115BBH, cost of acquisition, business-income head option.
**Gate 23A — Mapper** reuses ITR-2's `_map_vda`. **Builder** emits `ScheduleVDA`.
**Validator** adds 115BBH 30% rate + COA rules.

### Phase 24 — Schedule OS (Income from Other Sources)

**PDF anchor:** PDF line 2690. Dividend, interest, UTI, machinery, lottery, cross-employment,
RTI, other special-rate.
**Gate 24A — Mapper** reuses `_map_other_sources`. **Builder** emits `ScheduleOS`.
**Validator** adds 2d/2e special-rate + 56(2)(xiii) rules.

### Phase 25 — Schedule CYLA (Set-off of current-year losses)

**PDF anchor:** PDF line 3005. Salary/HP/BP/CG/OS after CYLA.
**Gate 25A — Builder** emits `ScheduleCYLA` from `ITR3Result.schedules["cyla"]` (currently
emits `float(...)` — fix to `_to_rupees()`). **Validator** checks CYLA head-order (Salary→HP→
BP→CG→OS) and sign rules.

### Phase 26 — Schedule BFLA (Set-off of brought-forward losses)

**PDF anchor:** PDF line 3073. After BFLA, per head.
**Gate 26A — Builder** emits `ScheduleBFLA` from `ITR3Result.schedules["bfla"]`. **Validator**
checks BFLA consumes CFL b/f correctly per head.

### Phase 27 — Schedule CFL (Losses carried forward)

**PDF anchor:** PDF line 3165. HP/BP(speculative/specified/other)/CG(STCG/LTCG)/OS/race-horses.
**Gate 27A — Mapper** reuses `_map_bf_losses` (from ITR-2). **Builder** emits `ScheduleCFL`
from `ITR3Result.schedules["cfl"]` — **fix the `float(...)` bug** to `_to_rupees()`. **Validator**
checks CFL head-wise carry-forward + 8-year limit.

### Phase 28 — Schedule UD (Unabsorbed Depreciation & S.35(4) allowance)

**PDF anchor:** PDF line 3228. AY-wise carried-forward unabsorbed depreciation.
**Gate 28A — `ITR3Input.schedule_ud: list[UDEntry]`** (already exists — verify against PDF).
**Mapper** maps `draft.itr3_schedule_ud`. **Builder** emits `ITR3ScheduleUD` (currently
conditional on `result.unabsorbed_dep_setoff > 0` which is stubbed to 0 — fix after Phase 14
calculator fix). **Validator** checks UD set-off against BP.

### Phase 29 — Schedule ICDS (Effect of ICDS on profit)

**PDF anchor:** PDF line 3246. Increase/decrease reconciliation to Part A-OI col. 3a/3b & 4d/4e.
**Gate 29A — `ITR3Input.schedule_icds: ITR3ICDSInput`.** **Mapper** maps `draft.itr3_schedule_icds`.
**Builder** emits `ScheduleICDS` (currently fabricated). **Validator** checks ICDS ties to Part A-OI.

### Phase 30 — Schedule 10AA (Deduction under S.10AA)

**PDF anchor:** PDF line 3271. SEZ undertakings.
**Gate 30A — `ITR3Input.business_deductions.s10aa`.** **Mapper** maps `draft.itr3_business_deductions.s10aa`.
**Builder** emits `Schedule10AA` (currently fabricated). **Validator** checks 10AA cap + sequential-year rule.

### Phase 31 — Schedule 80G (Donations)

**PDF anchor:** PDF line 3291. Four buckets (A–D): with/without qualifying PAN, with/without ARN.
**Gate 31A — Mapper** reuses ITR-1/2 `_map_donations`. **Builder** emits `Schedule80G`.
**Validator** adds 80G qualifying-vs-non-qualifying + 10% of income cap.

### Phase 32 — Schedule 80GGA (Donations for scientific research/rural development)

**PDF anchor:** PDF line 3361. S.35(1)(i)/(iia)/(iii)/35CCC.
**Gate 32A — Mapper** maps. **Builder** emits `Schedule80GGA`. **Validator** checks 80GGA scope.

### Phase 33 — Schedule 80GGC (Contributions to political parties)

**PDF anchor:** PDF line 3378. S.80GGC.
**Gate 33A — Mapper** maps. **Builder** emits `Schedule80GGC`. **Validator** checks 80GGC.

### Phase 34 — Schedule 80DD (Maintenance/medical of disabled dependent)

**PDF anchor:** PDF line 3394. S.80DD.
**Gate 34A — Mapper** reuses shared 80DD mapping. **Builder** emits `Schedule80DD`.
**Validator** adds 80DD cap (₹75k/1.25L/1.5L tiers) + disability-cert rule.

### Phase 35 — Schedule 80U (Deduction for person with disability)

**PDF anchor:** PDF line 3423. S.80U.
**Gate 35A — Mapper** maps. **Builder** emits `Schedule80U`. **Validator** adds 80U tier caps.

### Phase 36 — Schedule RA (Donations to research associations)

**PDF anchor:** PDF line 3452. S.35(1)(ii)/(iia)/(iii)/35(2AA) detail.
**Schema reconciliation:** the PDF label "Schedule RA" maps to schema block `Schedule80RA`
(`DonationDtlsRsrchAssctn`/`TotalDonationAmtCash80RA`/`TotalDonationAmtOtherMode80RA`/
`TotalDonationsUs80RA`/`TotalEligibleDonationAmt80RA`), distinct from `Schedule80GGA`
(which holds `DonationDtlsSciRsrchRuralDev`).
**Gate 36A — Mapper** maps RA rows into the scientific-research donation model. **Builder**
emits `Schedule80RA` (conditional). **Validator** checks RA scope.

### Phase 37 — Schedule 80-IA (Deductions for specified business profits)

**PDF anchor:** PDF line 3469. S.80-IA.
**Gate 37A — `ITR3Input.business_deductions.s80ia`.** **Mapper** maps. **Builder** emits
`Schedule80_IA` (currently fabricated). **Validator** adds 80-IA undertakings + cap rules.

### Phase 38 — Schedule 80-IB (Deductions under S.80-IB)

**PDF anchor:** PDF line 3485. S.80-IB.
**Gate 38A — `ITR3Input.business_deductions.s80ib`.** **Mapper** maps. **Builder** emits
`Schedule80_IB` (currently fabricated). **Validator** adds 80-IB sub-section rules.

### Phase 39 — Schedule 80-IE (Deductions under S.80-IE)

**PDF anchor:** PDF line 3517. North-East undertakings. **PDF prints "80-IE".**
**Schema reconciliation:** the official schema block carrying North-East undertaking
deductions is **`Schedule80_IC`** (`DeductInNorthEast`/`TotSchedule80_IC`); `Schedule80_IE`
does **not** exist in the schema. The PDF's "80-IE" maps to the schema's `Schedule80_IC`.
**Gate 39A — `ITR3Input.business_deductions.s80ie`.** **Mapper** maps. **Builder** emits
`Schedule80_IC` from the PDF's 80-IE data. **Validator** adds 80-IE North-East rules.

### Phase 40 — Schedule VI-A (Chapter VI-A deductions)

**PDF anchor:** PDF line 3579. Part B (80C/CCC/CCD(1)/(1B)/(2)/D/DDB/DD/E/EE/EEA/EEB/G/GG),
Part C (80-IA/80-IAB/80-IB/80-IBA/80-IE/80JJA/80JJAA/80QQB/80RRB), Part CA&D
(80TTA/80TTB/80U/80CCH/other).
**Gate 40A — Mapper** reuses shared Chapter VI-A mappers. **Builder** emits `ScheduleVIA` +
sub-schedules `Schedule80C`/`80D`/etc. **Validator** adds VI-A cap + 80GGA/80GGC inclusion.
`scheduleRegistry.ts` flips VI-A schedules to `'available'`.

### Phase 41 — Schedule AMT (Alternate Minimum Tax, S.115JC)

**PDF anchor:** PDF line 3664. Adjusted total income + AMT computation.
**Gate 41A — Mapper** reuses ITR-2 `_map_amt`. **Builder** emits `ScheduleAMT` from
`ITR3Result.amt`. **Validator** checks AMT = 18.5% of adjusted total income + cess.
**Calculator** fix (Phase 14) ensures AMT is computed once, in order.

### Phase 42 — Schedule AMTC (AMT credit, S.115JD)

**PDF anchor:** PDF line 3690. Credit utilization.
**Gate 42A — Mapper** maps AMT credit b/f. **Builder** emits `ScheduleAMTC`. **Validator**
checks AMTC utilization ≤ available credit.

### Phase 43 — Schedule SPI (Income of specified persons, S.64)

**PDF anchor:** PDF line 3737. Spouse/minor child/etc. includable income.
**Gate 43A — Mapper** reuses ITR-2 `_map_spi`. **Builder** emits `ScheduleSPI`. **Validator**
checks SPI inclusion in total income.

### Phase 44 — Schedule SI (Income chargeable at special rates)

**PDF anchor:** PDF line 3748. 111A/112/112A/115AD/115BBF/115BBG/115BBH/VDA/lottery.
**Gate 44A — Mapper** reuses ITR-2 `_map_si`. **Builder** emits `ScheduleSI`. **Validator**
checks SI special-rate codes + rates.

### Phase 45 — Schedule IF (Income from firms in which partner)

**PDF anchor:** PDF line 3864. Share of profit/interest/remuneration/capital.
**Gate 45A — `ITR3Input.schedule_if: list[PartnerInFirm]`** (already exists — verify). **Mapper**
maps `draft.itr3_schedule_if`. **Builder** emits `ScheduleIF` (currently fabricated). **Validator**
checks IF partner-share reconciliation.

### Phase 46 — Schedule EI (Exempt Income)

**PDF anchor:** PDF line 3885. For 13A/10AA/54/54EC/urban-coop/other exempt.
**Gate 46A — Mapper** reuses shared exempt-income mapping. **Builder** emits `ScheduleEI`.
**Validator** checks EI is excluded from total income.

### Phase 47 — Schedule PTI (Pass-Through Income, S.115U/UA/UB)

**PDF anchor:** PDF line 3924. Business trust / investment fund.
**Schema block:** `SchedulePTI` (`SchedulePTIDtls`).
**Gate 47A — Mapper** reuses ITR-2 `_map_pti`. **Builder** emits `SchedulePTI`. **Validator**
checks PTI inclusion.

### Phase 48 — Schedule TPSA (Tax on secondary adjustments, S.92CE(2A))

**PDF anchor:** PDF line 3988. Triggered by Part A-OI item 18 (the 92CE(2A) option).
**Schema block:** `ScheduleTPSA` (`AmtPrimaryAdjUs92CE_2A`/`AdditionalIncTax18PercAbove`/
`Surcharge12Perc`/`HealthEducationCess`/`TotalAdditionalTax`/`TaxesPaid`/`NetTaxPayable`/
`DtlsTaxesPaid`/`TotalAmountDeposited`).
**Gate 48A — `ITR3Input.schedule_tpsa: Optional[ITR3TPSAInput]`.** **Mapper** maps
`draft.itr3_schedule_tpsa`. **Builder** emits `ScheduleTPSA` (conditional on the Part A-OI
item-18 flag). **Validator** checks TPSA primary/secondary adjustment.

### Phase 49 — Schedule FSI (Income from outside India & tax relief)

**PDF anchor:** PDF line 4026. Resident-only.
**Schema block:** `ScheduleFSI` (`ScheduleFSIDtls`).
**Gate 49A — Mapper** reuses ITR-2 `_map_fsi`. **Builder** emits `ScheduleFSI`. **Validator**
checks FSI resident-only + ties to TR.

### Phase 50 — Schedule TR (Summary of tax relief for taxes paid outside India)

**PDF anchor:** PDF line 4058. Resident-only.
**Schema block:** `ScheduleTR1` (PDF "Schedule TR" ↔ schema `ScheduleTR1`; `ScheduleTR`/
`TotalTaxPaidOutsideIndia`/`TotalTaxReliefOutsideIndia`/`TaxReliefOutsideIndiaDTAA`/
`TaxReliefOutsideIndiaNotDTAA`/`AmtTaxRefunded`/`AssmtYrTaxRelief`).
**Gate 50A — Mapper** reuses ITR-2 `_map_tr1`. **Builder** emits `ScheduleTR1`. **Validator**
checks TR ≤ tax on FSI.

### Phase 51 — Schedule FA (Foreign Assets & income from any source outside India)

**PDF anchor:** PDF line 4091. Resident-only.
**Schema block:** `ScheduleFA` (`DetailsForiegnBank`/`DtlsForeignCustodialAcc`/
`DtlsForeignEquityDebtInterest`/`DtlsForeignCashValueInsurance`/`DetailsFinancialInterest`/
`DetailsImmovableProperty`/`DetailsOthAssets`/`DetailsOfAccntsHvngSigningAuth`).
**Gate 51A — Mapper** reuses ITR-2 `_map_fa`. **Builder** emits `ScheduleFA`. **Validator**
checks FA completeness (resident with foreign income must fill FA — Part B-TTI item 13 gate).

### Phase 52 — Schedule 5A (Portuguese Civil Code apportionment, S.5A)

**PDF anchor:** PDF line 4227. Goa/Daman-Diu.
**Schema block:** `Schedule5A2014` (PDF "Schedule 5A" ↔ schema `Schedule5A2014`;
`NameOfSpouse`/`PANOfSpouse`/`AadhaarOfSpouse`/`BooksSpouse44ABFlg`/`BooksSpouse92EFlg`/
`HPHeadIncome`/`BusHeadIncome`/`CapGainHeadIncome`).
**Gate 52A — Mapper** reuses ITR-2 `_map_schedule_5a`. **Builder** emits `Schedule5A2014`
(conditional on filing-status (h) = Yes). **Validator** checks 5A apportionment = 50/50.

### Phase 53 — Schedule AL (Assets & Liabilities at year-end, other than Part A-BS)

**PDF anchor:** PDF line 4248. Applies where income > ₹50 lakh.
**Schema block:** `ScheduleAL` (`ImmovableDetails`/`MovableAsset`/`InterstAOPFlag`/
`InterestHeldInaAsset`/`LiabilityInRelatAssets`).
**Gate 53A — Mapper** reuses ITR-2 `_map_asset_liability`. **Builder** emits `ScheduleAL`
(conditional on total income > ₹50L). **Validator** checks AL completeness.

### Phase 54 — Schedule GST (Turnover/Gross Receipt reported for GST)

**PDF anchor:** PDF line 4288. GSTIN-wise outward-supply turnover.
**Schema block:** `ScheduleGST` (`TurnoverGrsRcptForGSTIN` — array of
`{GSTINNo, AmtTurnGrossRcptGSTIN}`). Standalone top-level block, not nested under
`PartA_GEN1`/`GEN2`.
**Gate 54A — `ITR3Input.schedule_gst: Optional[ITR3GSTInput]`.** **Mapper** maps
`draft.itr3_schedule_gst`. **Builder** emits `ScheduleGST` (conditional). **Validator**
checks GSTIN pattern `[a-zA-Z0-9]{15}` and non-negative amounts.

### Phase 55 — ESOP (employee stock-option tax deferral)

**PDF anchor:** PDF line 4314. ESOP deferred-compensation for eligible start-ups (S.80-IAC).
**Schema block:** `ScheduleESOP` (`PanofStartUp`/`DPIITRegNo`/`ScheduleESOP2122_Type`…
`ScheduleESOP2627_Type`/`TotalTaxAttributedAmt`).
**Gate 55A — `ITR3Input.schedule_esop: Optional[ITR3ESOPInput]`.** **Mapper** maps
`draft.itr3_schedule_esop` (reuse ITR-2's `_map_esop` pattern). **Builder** emits
`ScheduleESOP` (conditional). **Validator** checks ESOP year-wise fields.

### Phase 56 — Part B-TI (Computation of Total Income)

**PDF anchor:** PDF line 4394. Heads aggregation, Chapter VI-A, PGBP/CG/OS.
**Schema block:** `PartB-TI` (`Salaries`/`IncomeFromHP`/`ProfBusGain`/`CapGain`/`IncFromOS`/
`TotalTI`/`CurrentYearLoss`/`BalanceAfterSetoffLosses`).
**Gate 56A — Builder** emits `PartB-TI` from `ITR3Result` totals. **Validator** checks
Part B-TI reconciles to schedule sums (Salary + HP + BP + CG + OS − Chapter VI-A −
PGBP/CG/OS losses).

### Phase 57 — Part B-TTI (Computation of Tax Liability on Total Income)

**PDF anchor:** PDF line 4491. Tax at normal/special rates, rebate 87A, surcharge (with
marginal relief), cess, 234A/B/C/D/E/F/I, credits (TDS/TCS/advance/SAS), AMT, net tax,
refund/payable.
**Schema block:** `PartB_TTI` (`ComputationOfTaxLiability`/`TaxPaid`/`Refund`/`AssetOutIndiaFlag`).
**Gate 57A — Builder** emits `PartB_TTI` from `ITR3Result`. **Validator** checks Part B-TTI
reconciles to tax computation + 234-interest + credits. This is the reconciliation heart of
the return.

### Phase 58 — Tax Return Preparer (TRP) details

**PDF anchor:** PDF line 4617 (items 15–16 of Part B-TTI, printed **before** Section 17).
**Schema block:** `TaxReturnPreparer` (`IdentificationNoOfTRP`/`NameOfTRP`/`ReImbFrmGov`).
**Gate 58A — Mapper** reuses shared TRP handling (`personal_profile.py`). **Builder** emits
`TaxReturnPreparer` from `typed_input.filing_profile.trp` (conditional).

### Phase 59 — Section 17 Tax Payments (A: Advance/SAS, B: TDS-Salary, C: TDS-Other, D: TCS)

**PDF anchor:** PDF line 4622. Form-lettered subsections printed after TRP.
**Schema blocks:** `ScheduleIT` (A), `ScheduleTDS1` (B), `ScheduleTDS2` (C),
`ScheduleTDS3` (C non-salary), `ScheduleTCS` (D).
**Gate 59A — Mapper** reuses `_map_tds`/`_map_tds3`/`_map_tcs`/`_map_tax_payments`. **Builder**
emits `ScheduleTDS1`/`TDS2`/`TDS3`/`TCS`/`IT` from `typed_input` (not placeholders).
**Validator** checks TDS/TCS totals tie to Part B-TTI items 10b/10c/10d.

### Phase 60 — Verification  [cross-cutting: builder signature fix + schema validation]

**PDF anchor:** PDF line 4715. Place, date, capacity (individual/Karta/representative).

This is the final PDF section and the natural serialization gate, so the two remaining
cross-cutting fixes land here:

**Gate 60A — Rewrite `build_itr3_json(result, typed_input)` signature** to match
`build_itr2_json`'s contract — read identity/address/verification/TDS/bank from `typed_input`
(and its `filing_profile`), not from 15 loose string params. Remove the hardcoded
`"Verification"["Date"]="2026-07-31"` — read from `typed_input.filing_profile`. Stop
fabricating zero-block schedules — every schedule emitter built in Phases 3–56 now reads
real values. This is a **breaking signature change**; update the two callers
(`/itr3/compute-json` router — preferably deleted per Phase 61 — and `tests/validate_schemas.py::test_itr3`).

**Gate 60B — Create `app/engine/itd/itr3_schema.py`** [cross-cutting: schema validation].
`ITR3SchemaValidationError` + `get_itr3_schema_validator()` + `validate_itr3_json(document)`,
mirroring `itr2_schema.py`/`itr4_schema.py` (Draft-4 validator, `lru_cache`, schema path
`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-3_2026_Main_V1.1 (2).json`). Wire into
`_generate_cbdt_json_itr3` so every generated ITR-3 JSON is official-schema-validated before
return. Also emit the schema-envelope blocks here: `CreationInfo` and `Form_ITR3`
(`ScheduleGST` and `ScheduleESOP` are now emitted by their own Phases 51/52 — not here).

**Gate 60C — Builder** emits `Verification` from `typed_input.filing_profile` (capacity =
SELF/REPRESENTATIVE/KARTA/PARTNER).

**Exit criteria:** a known-good ITR-3 fixture produces CBDT JSON that passes
`validate_itr3_json`; ITR-1/2/4 regression green.

### Phase 61 — Legacy route cleanup + endpoint parity

**PDF anchor:** none (cleanup).

- `app/routers/itr.py`: delete `itr3_compute`/`itr3_compute_json` (the dead flat-payload
  routes); ITR-3 routes only through `/v2/clients/{id}/itr/{year}/generate-cbdt-json`.
- `app/routers/filing.py`: `_normalize_form()` accepts ITR-3; both Type-2 and Type-3 submission
  paths open for ITR-3 through the existing form-agnostic uploader.
- `client_itr_v2.py`: remove the HTTP 501 on ITR-3 PDF generation (or document as out-of-scope).
- `app/routers/tax_v2.py`: update docstring (ITR-3 no longer "not supported").
- `tests/test_filing_gateway_v2_itr3.py` (new): mirrors `test_filing_gateway_v2_itr2.py` —
  compute returns populated summary; pending reconciliation blocks; dispatch rejects non-ITR-3
  draft; `generate_cbdt_json` produces schema-valid JSON passing CBDT Category A validators;
  incomplete filing profile fails at compute time.
- `tests/test_itr3_itd_builder.py` (new): schema-valid document generation, conditional-schedule
  presence, real-data serialization (no fabricated zero blocks).
- `tests/test_itr3_input_validation.py` + `tests/test_itr3_calc_validation.py` (new): per-rule
  known-good + known-bad cases.
- Update `tests/test_filing_gateway_v2_itr4.py::test_compute_canonical_rejects_unsupported_form`
  and `tests/test_tax_v2_compute.py` — ITR-3 is no longer the "unsupported" assertion target.

**Exit criteria:** ITR-3 flows end-to-end through `/v2/*`; ITR-1/2/4 regression green; Direct
Submit works for ITR-3 through the existing form-agnostic `filingSubmitApi.submit`.

### Phase 62 — Frontend: wire ITR-3 compute/submit  [cross-cutting: frontend]

- `frontend/src/pages/ITRComputationPage.tsx`: remove the three ITR-3 gates
  (`handleGenerateCbdtJson`, `handleDirectSubmit`, PDF download); the ITR-2 schedules-tab
  pattern (`ITR2SchedulesWorkspace`) extends to ITR-3's auxiliary schedules via the same
  `ListSection<T>`/`NullableSection<T>` template.
- `frontend/src/domain/scheduleRegistry.ts`: flip all ITR-3 schedule statuses to `'available'`.
- `frontend/src/api/itrCompute.ts`: remove `computeItr3`/`computeItr3Json` if present; route
  through `itrV2.compute`/`generate` only.

**Exit criteria:** ITR-3 business data entered in the UI persists through
`PUT /v2/clients/{id}/itr/{year}`, reaches `compute_canonical_itr3`, and appears in the
generated CBDT JSON; `tsc -b` + `vitest` + `npm run build` green; ITR-1/2/4 regression green.

### Phase 63 — Final verification

- `pytest tests/ -q` — full backend suite green (modulo the known ~177 pre-existing baseline failures).
- `npx tsc -b` + `npx vitest run` + `npm run build` — clean.
- End-to-end: filing-ready ITR-3 draft → compute → CBDT JSON → `validate_itr3_json` → `can_upload=True`.
- Manual portal-upload control: generate a Type-3 UAT sample for ITR-3 via
  `scripts/eri_uat_sanity.py` and email to `erihelp@incometax.gov.in` for ITD's offline sanity check.

---

## 5. Validator disposition method (applies to Phases 12–59)

Classify every official ITR-3 validation rule (from
`Reference Docs by CBDT & ITD/Official Validations/` ITR-3 rules PDF) as exactly one of:

| Disposition | Meaning |
|---|---|
| `IMPLEMENTED` | Real validator code added in this phase. |
| `STRUCTURALLY_GUARANTEED` | The typed Pydantic schema already rejects the bad state (`@model_validator` / field constraints). No code added. |
| `CALCULATOR_ENFORCED` | The calculator already applies the cap/formula internally. No validator code. |
| `SCHEMA_ENFORCED` | The official JSON schema (`itr3_schema.py`) rejects the bad state. No validator code. |
| `BUILDER_GUARANTEED` | The builder emits the value correctly by construction (e.g. derived schedules). No validator code. |
| `NOT_REPRESENTABLE` | The rule checks a CBDT e-filing-UI sub-field consistency that this repo doesn't have (we build JSON programmatically, not from a raw editable UI). No code. |
| `EXTERNAL_CHECK` | The rule requires a live ITD portal call (e.g. PAN validation). Out of scope for pre-compute. |
| `PENDING` | Genuinely needs implementation but deferred with a documented reason (missing schema field, unresolved rate discrepancy). |

Record the disposition per rule in `app/engine/validators/itr3/official_rules_reference.py`
(a permanent file, per `CLAUDE.md` convention) so a future audit pass doesn't re-read the PDF.

---

## 6. Out of scope (explicitly)

- Rewriting `app/engine/calculators/itr3.py`'s core tax math (slab/rebate/surcharge/cess/
  interest) — already complete and shared via `app/engine/common/`. Phase 14 only fixes the
  PGBP-consumption, AMT-order, UD-setoff, and CFL-dead-branch defects.
- Touching the shared `personal_profile.py` normalizers (Phase 5F delivered these; ITR-3 reuses them).
- Deleting `app/engine/filing_gateway.py` (Phase 9 of the combined ITR-2/3 plan's job,
  post-ITR-3).
- PDF Statement-of-Income rendering for ITR-3 beyond removing the 501 gate (the report builder
  is a separate concern).

---

## 7. Verification (applies throughout)

- Every new `ITR3Input` construction round-trips through `compute_itr3` → `build_itr3_json` →
  `validate_itr3_json`.
- No commit lands that turns ITR-1, ITR-2, or ITR-4 regression suites red.
- The suite baseline is ~177 pre-existing failures predating this work — treat a red run as
  the known state, not something this change caused, but confirm the ITR-3 area isn't newly broken.

---

## 8. Update discipline

This doc's status line at the top flips to "✅ Delivered YYYY-MM-DD" per phase as each phase's
tests pass. The combined `ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s Phase-8 row remains the
umbrella tracker; this doc is the schedulewise detail.
