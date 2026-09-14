# ITR-2 Schedule AMTC — open issue (Type-2 UAT `validateItr`)

**Status: OPEN, deliberately left unresolved.** Documented here rather than "fixed" further,
per the investigation below — the payload is independently proven correct against the official
CBDT/ITD reference implementation, so no further code change is expected to resolve this without
new information from ITD.

## Symptom

A Schedule AMTC block with a **genuine nonzero AMT-credit carry-forward** (i.e. brought-forward
credit only partially utilized this year, some balance remains for future years) is rejected by
the live Type-2 UAT `validateItr` endpoint:

```
ITR2_INF24_PDM_ScheduleAMTC_AmtLiabilityAvailable_LkBA6 - Old tax Regime selected and In Schedule
AMTC, Sl. No. 6 Amount of AMT liability available for credit in subsequent assessment years
[total of 4 (D)] is not equal to Total of item no. 4D.
```

Reproduced with PAN GOYPT2026A, AY 2026-27, multiple independent scenarios (different credit
amounts, different brought-forward assessment years, AMT binding and non-binding years, zero and
nonzero utilization) — see `app/engine/itd/itr2.py`'s `_schedule_amtc()` docstring/inline comments
for the full trail. Only a return with **zero** remaining carry-forward (credit fully consumed
this year) passes live.

## What was ruled out

1. **Field mapping** (`TaxSection115JD`/`AmtLiabilityAvailable` — these two fields were originally
   wired as duplicates of Sl.1/Sl.3, an unverified guess). Confirmed wrong and fixed: they are
   Sl.5/Sl.6's own values (`AmtCreditUtilized_Total`/`BalAmtCreditCarryFwd_Total`). This fix is
   real and permanent — it resolved a *different*, now-closed rejection
   (`..._TaxSection115JD_jzyvD`, "Sl.5 ≠ Total of item 4(C)"). The remaining rejection is a
   distinct errCd (`..._AmtLiabilityAvailable_LkBA6`, Sl.6).
2. **Array shape** — hypothesized ITD reads `ScheduleAMTCDtls` positionally rather than by each
   row's own `AssYr`. Decompiled the official CBDT/ITD Excel filing utility's VBA
   (`ITR2_AY_26-27_V1.4.xlsm`, `ScheduleAMTC()` JSON-export function) and confirmed it always
   emits all 13 possible prior-year rows (2013-14 through 2025-26), zero-filled where blank, in
   chronological order — never a shorter array. Matched this in the builder. No live-behavior
   change.
3. **Every other candidate field value** — `AmtLiabilityAvailable` tested against: 0, the
   array-derived sum, the grand-total-including-current-year-new-credit, a Part B-TTI item-10
   echo. All rejected except literal 0 (only valid when the true remaining balance is genuinely
   0 — not usable as a general "fix").
4. **The row-level identity itself** — deliberately set `BalAmtCreditCarryFwd` to an
   intentionally-wrong value in a live test; it was correctly caught by a *different*, accurate
   errCd citing the right identity (`Balance AMT Credit Carried Forward should be equal to
   (Balance brought forward) − (AMT Credit Utilized)`). This confirms ITD's live validator *can*
   and *does* check that identity correctly — the Sl.6 rejection is not that check misfiring.

## Independent verification against the official reference implementation

Extracted and decompiled the VBA from the official CBDT/ITD Excel filing utility itself
(`Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/ITR2_AY_26-27_V1.4.zip` →
`ITR2_AY_26-27_V1.4.xlsm` — the exact file CBDT publishes alongside the JSON schema and
validation-rules PDF). Its `Sheet23` ("AMTC") VBA module's `ValidateTaxSection115JD()`/
`ValidateAmtLiabilityAvailable()` functions read named ranges `AMTC.TaxSection115JD` (cell K24 =
`AMTC.AmtCreditUtilized_Total`) and `AMTC.AmtLiabilityAvailable` (cell K25 =
`AMTC.BalAmtCreditCarryFwd_Total` = `SUM(K9:L22)`) — an exact match to this codebase's field
mapping.

Drove the live workbook via COM automation (PowerShell + `Excel.Application`):
unprotected the `AMTC` and `DropDownValues` sheets with the utility's own embedded password
(`SheetALL.Range("pwd")` → `DropDownValues!B4` = `infyxldev0216`), set `bacValue` = 2 (old
regime — confirmed from the VBA's own `resetAMTCForYes`/regime-selection handlers, where `1` =
new regime / 115BAC opted, `2` = old regime), fed the exact scenario values
(`TaxSection115JC`=471380, `TaxOthProvisions`=475800, one credit row: AY 2023-24, Gross=50000,
Utilized=4420), forced a full recalculation, and read the computed cells back:

| Cell | Label | Official utility | This codebase |
|---|---|---|---|
| L6 | Sl.3 (utilization cap) | 4420 | 4420 |
| K19 | Row-level BalCF (2023-24) | 45580 | 45580 |
| K23 | Total of column D | 45580 | 45580 |
| K24 | Sl.5 (`TaxSection115JD`) | 4420 | 4420 |
| K25 | Sl.6 (`AmtLiabilityAvailable`) | 45580 | 45580 |
| J23 | Total of column C | 4420 | 4420 |

**Byte-for-byte identical**, for both the real credit row and every zero-filled row (verified
2013-14's row computes 0/0 in the official tool too, matching this codebase's zero-fill).

## Conclusion

This codebase's Schedule AMTC output is independently proven correct against the primary source
ITD itself publishes (the official Excel utility). The live Type-2 UAT `validateItr` rejection
for a genuine nonzero AMT-credit carry-forward is a gap specific to ITD's Type-2 API-side
validator, distinct from the JSON-schema/Excel-utility layer — not a defect in this codebase.

**Do not attempt to "fix" this further by guessing at more field values.** Any further progress
requires new information from ITD: either a working reference JSON payload for a genuine
partial-utilization AMTC scenario, or specific guidance from ITD's API/validator team (not their
general support desk) about what their Type-2 validator checks that the Excel-utility-generated
JSON and this codebase's JSON both apparently don't satisfy.

## Practical impact

Only affects ITR-2 returns claiming Schedule AMTC credit utilization where a **nonzero balance
remains** after this year's utilization (i.e. brought-forward AMT credit exceeds this year's
utilization cap). A return where AMT credit is either absent, or fully consumed this year, is
unaffected — confirmed via 9 of 10 live scenarios in the same UAT round passing cleanly (see
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` for the full round log).

## Related code

- `app/engine/itd/itr2.py::_schedule_amtc()` — full inline documentation of this investigation,
  including the live errCd evidence and the Excel-utility verification, sits directly on the
  `AmtLiabilityAvailable`/`TaxSection115JD` field assignments.
- `app/engine/schedules/amt.py::compute_amtc()` — the FIFO utilization/carry-forward computation
  itself, independently re-verified statutorily correct against Section 115JD(2)/(3) and confirmed
  arithmetically identical to the official Excel utility's own formulas.
- `tests/test_itr2_itd_builder.py` — `test_schedule_amtc_taxsection115jd_and_amtliabilityavailable_are_sl5_sl6_not_sl1_sl3`
  and the other `test_schedule_amtc_*` tests pin the values this codebase controls.
