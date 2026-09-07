# Statement of Income PDF Report (ITR-1 / ITR-2 / ITR-4)

Status: **Delivered for ITR-1, ITR-2, ITR-4. ITR-3 explicitly deferred (501).**
Endpoint: `GET /v2/clients/{client_id}/itr/{year}/download-pdf`
Frontend trigger: the **PDF** button on `ITRComputationPage.tsx`'s toolbar.

## 1. What this replaces

Before this change, `download_client_itr_pdf_v2()` (`app/routers/client_itr_v2.py`) rendered a
placeholder: a raw `reportlab.pdfgen.canvas` page listing draft-level *counts*
(`Employers: 1`, `House properties: 0`, ...) with no computed tax figures at all — its own
docstring said so explicitly ("It does not fabricate tax figures").

The reference format this feature targets is the Winman-style **"Statement of Income"** CA
computation sheet: a header identity block, a one-page income/tax summary with schedule
cross-references, and numbered supporting schedules (employer detail, interest/dividend
breakup, capital gains, TDS/TCS, bank accounts, a signature block). Five real reference PDFs in
that format were used to derive the layout (`C:\Users\Devansh\Desktop\COmputation reference\`
and `C:\Users\Devansh\Desktop\reference computation.pdf`, both outside the repo — CA-software
output, not committed here).

## 2. Architecture

New package: `app/engine/reports/` (4 files, ~1,150 lines total).

```
ReturnDraft + client               compute_canonical(draft)              build_statement_of_income_context()         render_statement_of_income()
(saved v2 draft)          ─────►   ITR1PipelineResult /          ─────►  StatementOfIncomeContext            ─────►   PDF bytes
                                    ITR2PipelineResult /                 (form-agnostic: SummaryRow[] +                (reportlab Platypus)
                                    ITR4PipelineResult                    ScheduleTable[])
```

| File | Role |
|---|---|
| `app/engine/reports/models.py` | Generic, form-agnostic data shapes: `SummaryRow`, `ScheduleTable`, `StatementOfIncomeContext`. The renderer only ever sees these — it has no idea "ITR-1" or "ITR-4" exist. |
| `app/engine/reports/formatting.py` | Pure presentation helpers: Indian digit grouping (`format_inr`), `DD-Mon-YYYY` dates (`format_date`, locale-independent — no `strftime("%b")`), assessment-year/previous-year string conversion. No tax logic. |
| `app/engine/reports/builders.py` (729 lines) | The bulk of the work: three functions, `build_itr1_context()`, `build_itr2_context()`, `build_itr4_context()`, each turning a `ReturnDraft` + its pipeline result into a `StatementOfIncomeContext`. Dispatched by `build_statement_of_income_context(draft, client, pipeline_result)`. |
| `app/engine/reports/renderer.py` (257 lines) | `render_statement_of_income(ctx) -> bytes` — lays the generic context out with reportlab Platypus (`SimpleDocTemplate`, `Table`, `Paragraph`). Raises `ImportError` if reportlab is missing, matching the endpoint's existing degrade-gracefully convention. |

Wired in `app/routers/client_itr_v2.py::download_client_itr_pdf_v2()`.

## 3. The one design rule everything else follows

> Every amount that lands in the income/tax summary or in a schedule's **total** row is read
> directly off the calculator's own result dataclass (`ITR1Result` / `ITR2Result` / `ITR4Result`)
> or off a raw, non-computed input fact (an employer's name, a bank account number, a TDS
> certificate's deductor). Nothing is re-derived in the report layer.

This was a deliberate response to a real risk surfaced during design: several schedules
(Section 112A capital-gains scrips, Schedule CG land/building rows) have per-transaction detail
in the raw draft but the *aggregate* exemption/classification math (e.g. the ₹1.25L Section 112A
exemption, which applies once across all scrips, not per scrip) lives only in the calculator.
Recomputing it per row in the report would have produced numbers that don't match the real
computation and could silently drift from it over time. Instead:

- **Summary lines and schedule totals** always come from `ITRNResult` fields (`salary_income`,
  `capital_gains_112a`, `tax_before_rebate`, `refund_due`, etc.) or from a nested
  `result.schedules[...]` dataclass (`OSResult`, `CGResult`, `SpecialRatesResult`, `HPResult`).
- **Per-row disclosure tables** (one row per employer, per TDS certificate, per capital-gains
  transaction) use **raw draft facts** (dates, names, sale consideration, cost of acquisition)
  purely for descriptive detail — never a locally-computed gain/tax figure. Where the real
  per-row math isn't preserved by the calculator (Section 112A/115AD per-scrip classification),
  the schedule shows the input facts and a note pointing at the aggregate Tax-on-Total-Income
  schedule for the authoritative taxable figure, rather than guessing.
- A small exception, called out explicitly in code (`builders.py::_employer_gross()`): the
  per-employer "gross salary received" figure is a straight sum of `Employer` row fields
  (`basic + da + bonus + ... + retrenchmentCompensation`), **copied verbatim from the exact
  formula** `app/engine/draft_to_itr1_input.py::_map_salary()` uses to build the aggregate
  `salary_gross` the calculator returns. It's arithmetic, not tax law, so reproducing it in the
  report is safe — and it's why the per-employer lines foot to the calculator's own total.

## 4. Per-form coverage

| Form | Compute path used | Notes |
|---|---|---|
| ITR-1 | `compute_canonical_itr1()` → `ITR1Result` | No `SpecialRatesResult`; only `capital_gains_112a` as a scalar. `ITR1Result.normal_rate_income` is used directly for the slab breakdown (authoritative, not re-derived). |
| ITR-2 | `compute_canonical_itr2()` → `ITR2Result` | Full `schedules["si"]` (`SpecialRatesResult.entries`) drives the Tax-on-Total-Income schedule's per-rate-bucket rows (111A/112A/112/VDA/DTAA/...). `schedules["hp"]`/`schedules["cg"]`/`schedules["os"]` supply house-property/capital-gains/other-sources detail. `typed_input.cg_transactions` (the exact list the calculator itself classified) drives the capital-gains transaction-detail schedule. |
| ITR-4 | `compute_canonical_itr4()` → `ITR4Result` | Adds the Presumptive Business schedule (44AD/44ADA/44AE), sourced from `draft.businesses` (per-business identity/turnover — the calculator only returns one aggregate `presumptive_income` scalar, never a per-business breakdown, so per-business rows are descriptive facts, and the schedule's **total** row still uses the calculator's `presumptive_income`). |
| ITR-3 | **None** | `compute_canonical()` in `app/engine/filing_gateway_v2.py` explicitly does not dispatch ITR-3 — it only exists via a separate, non-persisted legacy endpoint (`POST /itr3/compute`) that takes a raw `ITR3Input` body, not a saved `ReturnDraft`. Building a `draft_to_itr3_input.py` mapper is comparable in size to the ITR-2 v2-pipeline effort and is out of scope here — the endpoint returns `501` with a clear message instead of a best-effort/unreliable report. |

## 5. What each schedule is built from

| Schedule | Source | Why |
|---|---|---|
| Employer Details (one per employer) | `draft.employers[i]` (name, TAN, address, nature of employment) | Identity facts, not computed. |
| Salary computation | `ITRNResult.salary_gross` / `.salary_deduction_us16` / `.salary_income` | **Bug found & fixed**: `salary_deduction_us16` already *includes* `salary_deduction_us16ia` (see `app/engine/schedules/salary.py:340`, `deductions_u16 = std_ded + ent_allowance + prof_tax`) — the first version of this report summed both fields, double-counting the standard deduction (showed ₹1,50,000 instead of ₹75,000 for a single ₹3,25,000-salary employer). Fixed to use `salary_deduction_us16` alone. |
| House Property (one per property) | `result.hp_results` (ITR-1/4, top-level field) or `result.schedules["hp"]` (ITR-2, no top-level field) | `HPResult` (`app/engine/schedules/house_property.py`) already carries GAV/NAV/standard-deduction/interest/income-chargeable per property; zipped by index against `draft.houseProperties` for the address. |
| Capital Gains — simplified (ITR-1/4) | `draft.capitalGainsSchedule.simplified112A` (aggregate sale consideration/cost) + `result.capital_gains_112a` | No real per-scrip data exists for these forms — only one aggregate block — so the schedule shows one aggregate row, not a synthesized fake transaction list (a real, previously-flagged risk: `filing_gateway_v2.py::_capital_gains_summary()` manufactures a *single fake row* purely for frontend display reconciliation; this report deliberately does not reuse that synthesized data). |
| Capital Gains — transaction detail (ITR-2) | `typed_input.cg_transactions` (`ITR2Input`, the exact list `_classify_cg_transactions()` iterates) | Real per-transaction facts (description, asset type, dates, consideration, cost, expenses) with an explicit note that the STCG/LTCG split and Section 112A/54-series exemptions are applied in aggregate — pointing at the Tax-on-Total-Income schedule for the real taxable numbers. |
| Interest / Other Income | `result.schedules["os"]` (`OSResult`) | Already itemized at the right granularity (FD interest, savings interest, IT-refund interest, family pension, other) — no need to dig into raw per-bank-account draft data, which doesn't exist below this granularity anyway. |
| Dividends | `OSResult.dividend_income` | Single aggregate line (no per-declaration breakdown exists at the calculator-result level for a generic report). |
| Presumptive Business (ITR-4) | `draft.businesses` (per-business name/scheme/turnover/declared income) + `result.presumptive_income` (schedule total) | Per-business rows are descriptive; the schedule's own total row uses the calculator's aggregate, not a re-sum of the descriptive rows. |
| Agricultural Income | `draft.exemptIncome.grossAgriculturalReceipts` / `.agriculturalExpenses` (raw) + `result.net_agricultural_income` (calculator) | Shown as an informational line below Total Income (rate-purposes only, not added to the total), matching the reference format. |
| Tax on Total Income | ITR-1/4: `result.slab_tax` + `result.capital_gains_112a`/`result.special_rate_tax`. ITR-2: `result.schedules["si"].entries` (`SpecialRateEntry` list) | For ITR-2 this schedule is the real Schedule-SI equivalent — one row per special-rate basket (111A/112A/112/VDA/DTAA/...), each already carrying `taxable_income`/`tax_amount` from the calculator. |
| Slab-Rate Tax Computation | `app/engine/common/slab_tax.py::slab_breakdown()` (new function, see §6) | Purely descriptive bracket-by-bracket display; the schedule's own **Total** row always prints the calculator's real `slab_tax`, never a re-sum of the breakdown rows, so a display-only rounding edge case in the breakdown can never silently diverge from the real figure. |
| TDS from Salaries | `draft.employers[i].tdsDeducted` | **Not** `draft.taxes.tds` — that list's `headOfIncome` enum (`HP/CG/OS/BP/EI/NA`) has no salary value; salary TDS is tracked separately per employer. |
| TDS as per Form 16A | `draft.taxes.tds` | Non-salary TDS certificates only (by construction of the schema). |
| TCS | `draft.taxes.tcs` | Shown only when non-empty. |
| Advance Tax / Self-Assessment Tax | `draft.taxes.challans`, split by `.kind` | Feeds two summary lines (Advance Tax Paid / Self-Assessment Tax Paid) above the final Refund/Payable line. |
| Bank Accounts | `draft.bankAccounts` | Identity/reference facts. |

## 6. Supporting change: `slab_breakdown()`

`app/engine/common/slab_tax.py` gained one new public function, `slab_breakdown(taxable_income,
age_bracket, regime)`, returning the per-bracket `(lower, upper, rate, income_in_bracket,
tax_in_bracket)` tuples for whatever slab table `compute()` would have used. It's a pure display
helper — it reuses the exact same `_slabs_for()` table and `round_to_nearest_rupee()` rounding
`compute()` already uses, so it can never disagree with the real slab tax on the underlying
table, only (in principle) on bracket-rounding presentation, which is why the schedule's **Total**
row still prints the calculator's authoritative `slab_tax`, not a sum of this function's output.

## 7. Layout bugs found and fixed during implementation

Two real reportlab layout bugs were caught by rendering real drafts (not caught by unit tests,
since they're purely visual):

1. **Table headers overlapping instead of wrapping.** `_build_schedule_table()` originally passed
   plain Python strings into `Table` cells. reportlab does not wrap plain strings to the column
   width — a 6-column schedule (e.g. ITR-2's capital-gains transaction table: Description / Date
   of Acquisition / Date of Transfer / Sale Consideration / Cost of Acquisition / Transfer
   Expenses) rendered with adjacent header text running together
   (`"Date of TransfeSale ConsideratioCost of AcquisitioTransfer Expenses"`). Fixed by wrapping
   every cell (header and body) in a `reportlab.platypus.Paragraph` with an explicit style, which
   wraps correctly to the column width. Also added a text-vs-money alignment heuristic: a 2-column
   schedule (Field/Value pairs, e.g. Employer Details) left-aligns both columns since its second
   column is often narrative text (an address); a 3+ column schedule right-aligns everything past
   the first column, since those are almost always money tables.
2. **Header "Address" label vertically misaligned against a multi-line address.** The header's
   `left_table`/`right_table` (`_build_header_table()`) had no explicit `VALIGN`, so reportlab
   defaulted to `MIDDLE`. A 3-row label/value table where one row (Address) spans 4 lines made
   that row tall; with `VALIGN: MIDDLE`, the "Address" *label* cell centered against the tall row,
   visually appearing next to the 2nd/3rd line of the address instead of the 1st. Fixed by adding
   an explicit `VALIGN: TOP` table style to both inner tables (the outer 2-column table already
   had `VALIGN: TOP`, which is why Name/PAN/etc. were unaffected — only a row containing a
   *multi-line* cell exposed the bug).

## 8. Frontend changes

`frontend/src/pages/ITRComputationPage.tsx`:
- Added a `pdfDownloading` loading state; the **PDF** button now shows a spinner and disables
  itself while the request is in flight (a real compute + PDF render round-trip, not the old
  instant stub).
- Added a `title` tooltip describing what the button does and that ITR-3 isn't supported yet.
- Success toast reworded to "Statement of Income PDF downloaded successfully".

**No changes were needed** to `frontend/src/api/itrV2.ts`'s error handling — its existing
`parseBlobError()` already recursively unwraps a JSON error body's `message`/`errors` fields
(built for the CBDT-JSON-generation error path), and it handles this endpoint's `HTTPException(
detail={"message": ..., "errors": [...]})` shape correctly out of the box, including the extra
layer of wrapping `app/main.py`'s global exception handler adds
(`{"error": true, "message": {...}, "status_code": 422}` — confirmed live, see §9).

## 9. Verification performed

**Unit-level (ad hoc script, not committed — `scratchpad/smoke_pdf.py` during development):**
built representative `ReturnDraft`s for ITR-1/2/4 covering: a normal single-employer salary
return; a presumptive-business ITR-4; a multi-schedule ITR-1 (house-property loss under the new
regime, Section 112A capital gains, TCS, self-assessment tax); a multi-schedule ITR-2 (house
property, real `cg_transactions` land/building entry, VDA, surcharge); and empty/near-empty
drafts for all three forms (including the ITR-4/ITR-2 eligibility-rejection paths, which
correctly raise `FilingGatewayV2Error` rather than crash). All 8 scenarios rendered valid,
correctly-computed PDFs.

**Regression suite:** `pytest` run across every test file touching `slab_tax`, the ITR-1/2/4
calculators, and the filing gateway (`test_filing_gateway_v2*.py`, `test_itr1_calculator.py`,
`test_itr1_e2e.py`, `test_itr2_integration.py`, `test_itr2_itd_builder.py`,
`test_itr4_calculator.py`, `test_itr4_e2e.py`, `test_itr4_calc_validation.py`,
`test_itr4_statutory_formula_known_answers.py`, `test_boundary_regression.py`,
`test_filing_gateway_v2_itr2.py`) — **255 passed, 1 pre-existing failure** confirmed via
`git stash` to be unrelated (a representative-verification-capacity error-message wording
mismatch in `test_filing_gateway_v2_itr2.py`, present on `HEAD` before this feature).

**Live browser test** (both dev servers running, real login session, real client): clicked PDF on
client **Sunit Ramashankar Goyanka** (PAN `ACUPG3482G`, ITR-2) —
- First click: compute-blocking issue (`verification.declarationAccepted` false) → correct `422`,
  surfaced via the existing error-toast plumbing.
- Fixed the client's data (accepted the verification declaration; changed the filing section from
  an expired `139(1)` to `139(4)` belated, since AY 2026-27's ITR-2 due date had passed).
- Second click: real `200 OK`, `Content-Disposition: attachment; filename=
  ITR_ITR2_ACUPG3482G_2026-27_StatementOfIncome.pdf`, `content-length: 5408` — downloaded and
  inspected; correctly reflects that client's actual saved Other-Sources income, TDS credits
  (State Bank of India, Anand Purushottam Agrawal), and bank account.
- No new browser console errors after the fix.

`npm run build` (`tsc -b && vite build`) passes clean after the frontend edits.

## 10. Known limitations (by design, not oversights)

- **ITR-3**: no report at all yet (§4) — needs its own `ReturnDraft` compute pipeline first.
- **No per-employer salary economics from the calculator**: `ITRNResult` only ever returns one
  aggregate `SalaryResult`; per-employer figures in the report are a verbatim reproduction of the
  mapper's own summation formula (§3), not something the calculator itself exposes per row.
- **No per-bank-account interest itemization**: `OSResult` is itemized by *nature* (FD/savings/
  refund/other), not by bank account — that granularity isn't captured anywhere upstream today.
- **ITR-2 capital-gains transaction table has no gain/tax column**: deliberately, to avoid
  re-deriving the Section 112A aggregate-exemption math per row (§3) — see the schedule's own
  note pointing at the Tax-on-Total-Income schedule.
- **44AE presumptive vehicles**: shown as sub-rows under their business in the same schedule
  table, not a separate schedule.

## 11. Where to extend this

- **ITR-3**: once `app/engine/draft_to_itr3_input.py` + `compute_canonical_itr3()` exist (tracked
  separately, see `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`'s own Phase 8 note), add
  `build_itr3_context()` to `builders.py` and register it in `_BUILDERS`, then drop the `501` gate
  in `client_itr_v2.py`. The renderer needs no changes — it's already form-agnostic.
- **Richer capital-gains disclosure**: if a future calculator change starts preserving per-scrip
  Section 112A classification post-exemption-allocation (not just the 3 aggregate scalars
  `compute_112a()` currently returns), `build_itr2_context()`'s transaction-detail schedule could
  add a real gain/tax column without violating the "never re-derive" rule.
