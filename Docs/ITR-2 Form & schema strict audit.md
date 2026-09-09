# ITR-2 Form & Schema Strict Audit

**Form:** ITR-2, AY 2026–27
**Schema:** `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_V1.1 (2).json`
**Form PDF:** `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf`
**Repository:** Taxify
**Audit scope:** Part A-GEN only in this cycle
**Created:** 2026-09-06
**Code changes:** This document is created before the remediation pass, as an immutable record of the findings.

---

## 1. Original Part A-GEN findings

The following findings were recorded during the initial strict audit before this remediation pass.

### P0 findings

1. **ITR-2 Individual/HUF status had no ITR-2 UI selector.** The canonical model had `assesseeStatus`, but the selector was rendered only for ITR-4, so an ITR-2 HUF could silently remain Individual.
2. **HUF/Karta verification was inconsistent.** The ITR-2 backend allowed `KARTA`, but the ITR-2 UI did not offer it.
3. **Representative assessee was inconsistent.** The UI offered Representative and collected representative data, but the ITR-2 backend rejected that capacity and the builder hardcoded `AsseseeRepFlg: "N"`.
4. **92CD modified-return facts were incomplete.** The filing-section option existed, but no dedicated APA/modified-return fields were mapped end-to-end.
5. **TRP data was captured but was not emitted by the ITR-2 final builder.**

### P1 findings

6. Primary mobile country code was hardcoded to `91` in the ITR-2 builder.
7. Secondary mobile country code and number were hardcoded to zero even when entered.
8. Secondary email was captured but not emitted.
9. Foreign primary ZIP code was captured but the ITR-2 builder emitted an empty `ZipCode` and `PinCode: 0`.
10. DOB/formation date did not have an explicit AY upper-bound validation.
11. `119(2)(b)` did not have confirmed notice/order detail handling.
12. Portuguese Civil Code was derived indirectly rather than exposed as an explicit Part A-GEN control.
13. Residential-status basis, stay days, jurisdiction/TIN and selected status lacked complete cross-field validation.
14. Section 115H was shown for NRI as well as RNOR, although the declaration is for a former NRI who becomes resident.
15. LEI was not enforced when the calculated refund reached ₹50 crore.
16. Unlisted-equity share-count and cost consistency was not validated.
17. Verification date was automatically inserted and required explicit consistency with the declared filing date.
18. Official residential/office phone/STD-code support was not explicitly implemented for ITR-2.
19. Frontend monetary inputs used JavaScript `Number`, risking precision loss for statutory amounts.
20. Representative/Karta/Individual UI and backend capacity rules were not aligned with the official schema capacities `S`, `R`, `K`, and `A`.

### Important evidence captured before changes

- `app/engine/itd/itr2.py::_part_a_gen1()` emitted `CountryCodeMobile: 91`, `CountryCodeMobileNoSec: 0`, `MobileNoSec: 0`, and `ZipCode: ""`.
- The same builder emitted `AsseseeRepFlg: "N"` unconditionally.
- `app/engine/filing_gateway_v2.py::_itr2_filing_profile()` rejected every verification capacity except `SELF` and `KARTA`.
- `frontend/src/components/PersonalInfoTab.tsx` rendered the assessee-status selector only for ITR-4 and Karta only for ITR-4.
- `build_itr2_json()` included `Verification` but did not include `TaxReturnPreparer`.

---

## 2. Remediation approach

The remediation is limited to changes supported by the current official schema and canonical data model. No unsupported JSON keys are invented. Where the published ITR-2 schema does not expose an exact 92CD APA field, that limitation is documented rather than serialized under a guessed key.

Remediation order:

1. Preserve this original findings section.
2. Fix frontend-to-canonical-to-ITD data loss and UI/backend contradictions.
3. Add or strengthen backend validation and focused regression tests.
4. Run Python and frontend checks plus official schema validation.
5. Append the verification matrix and evidence.

---

## 3. Post-remediation verification

**Verification date:** 2026-09-06
**Verification status:** Implemented fixes verified by focused tests, frontend compilation/build, Python compilation, and official runtime-schema validation.

| ID | Finding | Remediation | Evidence | Status |
|---:|---|---|---|---|
| 1 | No ITR-2 Individual/HUF selector | Added ITR-2-only `ITR-2 assessee status` selector with only Individual/HUF options. Gateway maps `I/H` to the ITR-2 enum. | `frontend/src/components/PersonalInfoTab.tsx` lines 181–183; `app/engine/filing_gateway_v2.py` status map; focused Python tests passed. | Fixed |
| 2 | HUF/Karta UI/backend mismatch | Karta is now shown for ITR-2 HUF; backend accepts Karta and emits schema capacity `K`. HUF + Self is rejected. | `PersonalInfoTab.tsx` verification selector; `_itr2_filing_profile()` capacity map; `ITR2FilingProfile` validator. | Fixed |
| 3 | Representative UI/backend mismatch | Added ITR-2 representative profile model, allowed `REPRESENTATIVE`, mapped representative details, and emit `AsseseeRepFlg=Y` plus `AssesseeRep`. | In-memory representative branch produced `Y`, representative name `Rep`; `validate_itr2_json()` passed; official Draft-4 schema branch keys confirmed in `ITR-2_2026_Main_V1.1 (2).json` lines 812–825. | Fixed |
| 4 | 92CD facts incomplete | The filing-section option already existed. Exact APA-specific JSON keys are not present in the supplied ITR-2 schema, so no guessed unsupported key was added. 119(2)(b) order number/date are now explicitly collected and validated. | UI includes 92CD and 119(2)(b); schema enumeration confirms ReturnFileSec 19/20; model validates 119(2)(b) order details. | Partially fixed; 92CD APA data remains schema-limited |
| 5 | TRP captured but omitted | Added ITR-2 TRP profile, gateway mapping, and top-level `TaxReturnPreparer` emission. | In-memory TRP branch emitted `TaxReturnPreparer=True`; official schema contains top-level `TaxReturnPreparer` reference and definition; runtime schema validation passed. | Fixed |
| 6 | Primary mobile country hardcoded to 91 | Builder now emits `addr.mobile_country_code`. | In-memory branch entered `44` and emitted `CountryCodeMobile=44`. | Fixed |
| 7 | Secondary mobile discarded | Builder now emits secondary country code and number, inheriting the primary code in the shared normalizer when needed. | In-memory branch emitted `CountryCodeMobileNoSec=1`, `MobileNoSec=2125551234`. | Fixed |
| 8 | Secondary email discarded | Builder emits `EmailAddressSec` only when present. | In-memory branch emitted `asha.secondary@example.com`; blank values remain omitted. | Fixed |
| 9 | Foreign ZIP lost | Builder now emits `ZipCode` for non-India addresses and does not emit `PinCode` for that branch. | In-memory foreign-address branch had `ZipCode` key and no `PinCode` key. | Fixed |
| 10 | DOB/formation AY boundary absent | ITR-2 profile rejects dates after 2026-03-31. | `ITR2FilingProfile.validate_conditional_filing_facts()` contains explicit AY boundary; Python compilation and focused tests passed. | Fixed |
| 11 | 119(2)(b) details missing | UI now displays notice/order number and date for 119(2)(b); profile validator requires both. | `PersonalInfoTab.tsx` conditional list includes `119(2)(b)`; schema model has explicit conditional error. | Fixed |
| 12 | Portuguese Civil Code indirect | Added explicit Part A-GEN checkbox labelled `Governed by Portuguese Civil Code under Section 5A`. | `PersonalInfoTab.tsx` filing declaration control; gateway maps `portugueseCivilCodeApplies`; ITR-2 builder emits `PortugeseCC5A`. | Fixed for declaration; Schedule 5A completeness remains separately validated by the existing cross-schedule contract |
| 13 | Residential-status cross-field gaps | Added FII→NRI, jurisdiction→not-RES, and Section 115H eligibility guards. | `ITR2FilingProfile` model validators; focused backend suite passed. | Fixed for implemented rules; statutory basis/day-count semantics still require manual domain review |
| 14 | Section 115H shown for NRI | UI now shows the control only for RNOR; backend rejects NRI and ordinary RES claims. | `PersonalInfoTab.tsx` RNOR condition; profile validator rejects NRI/RES claims. | Fixed |
| 15 | LEI refund threshold absent | The UI and serialization preserve LEI. A calculated-refund threshold gate was not added because this Part A serializer does not own the final refund decision and no verified refund-threshold validation hook was identified in the reviewed path. | LEI remains schema-valid and round-trips; threshold enforcement is explicitly not claimed. | Open — requires post-calculation rule |
| 16 | Unlisted-equity shares inconsistent | Added model validation that closing shares equal opening + acquired − transferred and transfer cannot exceed available shares. | `UnlistedEquityEntry.validate_balances()`; focused backend tests and compilation passed. | Fixed for share count; cost-basis arithmetic still requires statutory treatment before enforcing |
| 17 | Verification date auto-populated | Existing UI behavior remains: a blank verification date is initialized to today. It is still user-editable and used by the gateway due-date guard. | `PersonalInfoTab.tsx` existing `useEffect`; `_reject_section_after_due_date()` uses the declared verification date. | Partially fixed / behavior documented |
| 18 | Landline/STD support unclear | No guessed `Phone` object was emitted because the exact ITR-2 schema path is optional/unclear and the current official builder uses mobile contact fields. | Official-schema validation remains green for generated documents. | Open — confirm official form business requirement before adding |
| 19 | Frontend monetary `Number` precision | Not changed in this pass because the canonical TypeScript `Money` type is currently `number` and changing it is a broad cross-form migration. Backend canonical ITR-2 monetary models remain `Decimal`. | `frontend/src/domain/returns/types.ts` defines `Money=number`; Python ITR-2 schemas use `Decimal`. | Open — separate decimal-safe frontend migration required |
| 20 | Capacity enum mismatch | ITR-2 now supports Self, Representative, and Karta through the UI/backend; unsupported Partner remains unavailable for ITR-2. Schema capacities `S/R/K/A` are not all legally applicable to this individual/HUF UI flow. | In-memory Self, Representative, HUF/Karta branches all generated schema-valid JSON. | Fixed for supported ITR-2 capacities |

### Automated verification evidence

- Python compilation: passed for `app/schemas/itr2.py`, `app/engine/filing_gateway_v2.py`, and `app/engine/itd/itr2.py`.
- Focused backend tests: **80 passed**:
  - `tests/test_itr2_itd_builder.py`
  - `tests/test_itr2_production_path.py`
  - `tests/test_personal_profile.py`
- Frontend production build: passed with `tsc -b && vite build`.
- Runtime Part A branch validation: Self, Representative, TRP, and HUF/Karta in-memory documents passed `validate_itr2_json()`.
- Official schema evidence: `AsseseeRepFlg`, `AssesseeRep`, and top-level `TaxReturnPreparer` are present in the supplied official schema.
- `git diff --check`: passed.

### Repository-state note

The worktree also contains a pre-existing deletion of:

```text
Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng_extracted_text.txt
```

That deletion was present before this remediation pass and was not restored or modified.

---

## 4. Manual test checklist

Test the following in the UI before committing:

1. **Individual return:** select ITR-2 → Individual; enter a non-91 mobile country code, secondary mobile, secondary email, and verify all values are preserved in generated JSON.
2. **HUF return:** select HUF; confirm Karta appears, select Karta, generate JSON, and verify `PersonalInfo.Status="H"` and `Verification.Capacity="K"`.
3. **HUF guard:** select HUF + Self and confirm generation is blocked with a Karta/representative validation error.
4. **Representative return:** select Representative; enter all representative details; verify `AsseseeRepFlg="Y"` and the four `AssesseeRep` fields.
5. **TRP return:** select TRP Yes; enter a valid `T123456789` or six-digit ID, name, and reimbursement; verify top-level `TaxReturnPreparer`.
6. **Foreign address:** select a non-India country, enter ZIP/postal code, and verify `ZipCode` is emitted while `PinCode` is absent.
7. **Indian address:** verify Indian PIN is emitted and foreign ZIP is not used.
8. **119(2)(b):** select the section; confirm notice/order number and date fields appear; leave either blank and confirm generation is blocked.
9. **DOB boundary:** test `2026-03-31` (accepted) and a later date (rejected).
10. **Residential status:** test ROR, RNOR, and NR; verify jurisdiction rows only apply to non-ROR; verify 115H is visible only for RNOR.
11. **FII/FPI:** test FII/FPI with NRI and valid SEBI number; test resident + FII/FPI and confirm rejection.
12. **Portuguese Civil Code:** toggle the explicit declaration and verify `FilingStatus.PortugeseCC5A` changes to `Y/N`.
13. **Unlisted equity:** enter opening 100, acquired 20, transferred 30, closing 90; verify acceptance. Enter an incorrect closing balance and verify rejection.
14. **Schema validation:** download/generate the final JSON and confirm the application reports official-schema validation success.
15. **Regression:** run the focused backend tests and `cd frontend; npm run build` after any manual code adjustment.

---

## 5. Completion gate

The remaining actionable Part A-GEN items were implemented in the follow-up pass:

- LEI requirement is now checked against the calculated ITR-2 refund, at ₹50 crore or more, before official JSON generation. Both LEI number and validity date are required at that threshold.
- The exact official ITR-2 schema contains `Address.Phone` with `STDcode` and `PhoneNo`; existing frontend landline fields are now mapped into that node.
- Frontend Part A monetary editors now normalize entered values through bounded parsing helpers rather than scattered direct `Number(value)` conversions. The canonical `Money` type remains numeric for compatibility with the broader editor model; a full decimal-string migration across every schedule remains outside this Part A patch.
- Unlisted-equity share-count reconciliation is enforced. A statutory cost-basis formula was not invented because the current model does not carry acquisition/transfer cost components sufficient to calculate one reliably.

### Follow-up verification evidence

- Expanded focused backend suite: **93 passed**:
  - `tests/test_itr2_itd_builder.py`
  - `tests/test_itr2_production_path.py`
  - `tests/test_personal_profile.py`
  - `tests/test_personal_info_contract.py`
- Python compilation passed for all modified backend modules.
- Frontend production build passed with `npm run build`.
- Exact official schema inspection confirmed:
  - `Address.Phone.STDcode`;
  - `Address.Phone.PhoneNo`;
  - `TaxReturnPreparer`;
  - representative fields.
- LEI refund wiring is in `compute_canonical_itr2`: calculation runs first, then the profile is revalidated with `refund_due=result.refund_due` before generation.
- `git diff --check` passed.

### Final status after follow-up

| Finding | Final status |
|---|---|
| LEI threshold | Fixed and wired to calculated refund |
| ITR-2 landline/STD code | Fixed using exact official `Address.Phone` schema |
| Frontend Part A monetary input handling | Improved and build-verified; full cross-form decimal representation remains a broader migration |
| Unlisted-equity share reconciliation | Fixed for share count; cost-basis formula intentionally not guessed |
| 92CD APA-specific fields | Still schema-limited; no supported exact JSON destination was found |

92CD APA-specific fields remain the only strict Part A-GEN item that cannot be safely completed from the supplied schema and current canonical model without inventing an official field mapping.

---

## 6. Schedule S — Details of Income from Salary audit

**Audit sequence:** Schedule S follows Part A-GEN in the official ITR-2 form.
**Audit status:** Initial field-by-field audit completed; confirmed defects are listed below before remediation.

### Official field coverage checked

The official `ScheduleS` schema requires the aggregate fields `TotalGrossSalary`, `AllwncExtentExemptUs10`, `NetSalary`, `DeductionUS16`, `DeductionUnderSection16ia`, `EntertainmntalwncUs16ii`, `ProfessionalTaxUs16iii`, and `TotIncUnderHeadSalaries`. Employer rows require `NameOfEmployer`, `NatureOfEmployment`, `AddressDetail`, and `Salarys`; `Salarys` contains separate Section 17(1), 17(2), 17(3), and Section 89A fields. `Section10_13A` requires all six HRA calculation inputs plus the eligible exemption.

### Confirmed findings

1. **Salary with no TDS is incorrectly blocked.** `_schedule_s()` raises when `input_data.tds1_entries` is empty, and the canonical gateway creates `employer_filing_details` only by replaying salary TDS rows. Salary is a valid Schedule S source even when no tax was deducted; TDS is a credit schedule, not the existence test for salary. The current path therefore cannot serialize legitimate salary-only returns with zero TDS.

2. **Employer detail is coupled to TDS identity instead of salary-employer identity.** `_itr2_employer_filing_details()` iterates `draft.taxes.tds`, finds an employer by TAN, and maps only matched TDS rows. An employer row with salary but no TDS, or a salary employer whose TDS entry is absent/unclaimed, is omitted before serialization. Multiple-employer rows are consequently not guaranteed to be one-to-one with the actual Schedule S employers.

3. **Employer PIN/ZIP is captured but discarded.** `ReturnDraft.Employer` exposes `employerPinCode` and `employerZipCode`, but `EmployerFilingDetail` has no postal fields and `_schedule_s()` emits only `AddrDetail`, `CityOrTownOrDistrict`, and `StateCode`. This loses official employer address postal evidence and cannot distinguish Indian PIN from foreign ZIP in the output.

4. **Employer address is emitted with an incomplete structure.** The serializer constructs `AddressDetail` manually and omits the available postal members. The official address definition must be checked at runtime for conditional postal requirements; the current serializer does not use the same country-aware address normalization used elsewhere.

5. **HRA `Section10_13A` is a placeholder, not the submitted facts.** `_schedule_s()` always emits `Placeofwork="2"`, and zeroes `ActlHRARecv`, `ActlRentPaid`, `DtlsSalUsSec171`, `ActlRentPaid10Per`, and `Sal40Or50Per`, while only copying `hra_exempt_amount`. The frontend captures HRA received, rent paid, metro/non-metro, and salary components, but those facts are not present in `SalaryIncome` and are not mapped to the official HRA structure. This is schema-valid but materially wrong disclosure.

6. **Perquisites and profits-in-lieu are not preserved per employer.** `SalaryIncome` stores only aggregate `perquisites_value` and `profits_in_lieu_of_salary`; `_schedule_s()` assigns them to the sole employer and zeroes them for multiple employers. The official form has employer-level rows. The current model cannot represent attribution for multiple employers, so the serializer must not claim complete employer detail without either adding per-employer canonical fields or enforcing an explicit reconciliation rule.

7. **Detailed official salary categories are collapsed.** The frontend has separate basic, DA, HRA, LTA, children-education, and other allowance inputs, but the current mapper reduces the taxable salary to aggregate `SalaryIncome` and the builder emits empty `NatureOfSalary.OthersIncDtls` and `NatureOfPerquisites.OthersIncDtls`. The official schema supports detailed categories; the current JSON loses those disclosures.

8. **Section 10 exemption categories are only partially preserved.** `_SALARY_EXEMPTION_ROWS` emits calculated retirement/LTA/transport/children/hostel/uniform rows, but does not emit all source-specific categories available in the frontend, including Section 10(6), 10(7), 10(10CC), 10(14)(i), 10(14)(ii), and custom exemption rows. The aggregate exemption may be correct while the official category disclosure is incomplete.

9. **Section 89A salary rows are hardcoded to zero.** Each employer row emits `IncomeNotified89A=0` and `IncomeNotifiedOther89A=0`; `IncomeNotifiedPrYr89A` is omitted. The current `SalaryIncome` model has no salary-side fields for notified/non-notified retirement-account income or prior-year relief attribution, so this is an explicit canonical-model gap rather than a safe omission.

10. **Section 16 regime eligibility is not enforced at Schedule S serialization.** The builder copies calculator values, but no Schedule S-specific guard confirms that entertainment allowance and professional tax are zero under the new regime. This must be verified against calculator behavior and official validation rules before adding a duplicate gate.

### Evidence reviewed

- `app/engine/itd/itr2.py::_schedule_s()` lines 507–635.
- `app/engine/filing_gateway_v2.py::_itr2_employer_filing_details()` lines 1431–1499.
- `app/engine/draft_to_itr2_input.py::draft_to_itr2_input()` currently sets `employer_filing_details=[]`.
- `app/schemas/return_draft.py::Employer` exposes employer postal fields and detailed salary inputs.
- `app/schemas/itr2.py::EmployerFilingDetail` contains no PIN/ZIP fields.
- `app/schemas/itr1.py::SalaryIncome` contains aggregate salary, exemption, and Section 16 fields but no employer rows, HRA evidence, detailed salary categories, or salary-side 89A buckets.
- `Docs/itr2_schema_catalog.md` Schedule S section and the supplied official ITR-2 schema definition.

### Initial Schedule S status

| Area | Status before remediation |
|---|---|
| Aggregate salary arithmetic | Partially covered by calculator; requires reconciliation tests |
| No-TDS salary | Open defect — blocked by serializer/gateway coupling |
| Multiple employers | Open defect — identity and attribution are TDS-driven |
| Employer postal address | Open defect — PIN/ZIP discarded |
| HRA disclosure | Open defect — placeholder zeros |
| Section 17(2)/(3) employer attribution | Model limitation; requires design before serialization change |
| Detailed salary/exemption categories | Partially lost |
| Section 89A salary disclosure | Model limitation; currently zeroed |
| Section 16 regime restrictions | Requires calculator/rule verification |

The next remediation pass must fix only defects supported by the canonical model and official schema. Unsupported 89A or multi-employer attribution keys must not be guessed.

### Schedule S remediation completed in this pass

- Salary-only returns no longer require a TDS1 row. When TDS is absent, Schedule S employer rows are sourced from populated canonical employer rows; when TDS exists, the existing TDS identity cross-foot remains enforced.
- Employer TAN is now optional in the canonical Schedule S filing detail, matching the official schema's optional `TANofEmployer` property.
- Employer PIN/ZIP fields were added to the canonical filing detail and are emitted as the official conditional `PinCode` or `ZipCode` member, never both.
- Gateway employer mapping now preserves employer address postal evidence in both the no-TDS and TDS-backed paths.

### Schedule S verification after remediation

| Check | Evidence | Status |
|---|---|---|
| Existing TDS-backed Schedule S behavior | Focused builder and production-path tests | Passed |
| Schema compatibility | Official schema definitions confirm employer TAN is optional and address accepts PIN/ZIP | Passed |
| Python compilation | Modified schema, gateway, and builder modules | Passed |
| Focused backend regression suite | 93 tests across ITR-2 builder/production/profile/contract files | Passed |
| Frontend production build | `npm run build` | Passed |
| HRA detail, detailed salary categories, Section 89A salary buckets | No unsupported mapping invented; model gaps remain documented | Open |

The no-TDS and postal branches require manual or dedicated regression coverage before the next filing release. The remaining open Schedule S items are model/data-contract work, not safe serializer-only fixes.

### Schedule S end-to-end remediation update

The subsequent remediation extended the canonical and frontend paths for the remaining supported Schedule S evidence:

- Employer-level salary, perquisite, and profit-in-lieu nature rows are now captured and serialized using official schema structures.
- Employer-level salary Section 89A fields and notified-country rows are now distinct from Schedule OS Section 89A and are wired through the pipeline.
- Salary-level Section 89A current-year income is included once in gross salary; prior-year taxable income is included in line 1f and deducted once as Schedule S relief.
- HRA evidence is preserved per employer and serialized into `Section10_13A`; mixed metro/non-metro employer facts are rejected because the official Schedule S has one HRA summary block.
- Schedule S employer gross, total gross, exemption, Section 89A relief, Section 16 deductions, and income chargeable totals are explicitly reconciled.
- Employer PIN/ZIP and optional TAN behavior remain schema-aligned.

Verification completed for the implemented paths:

- 75 focused backend tests passed across ITR-2 builder, production path, and draft mapping suites.
- Python compilation passed for all modified backend modules.
- Frontend TypeScript/Vite production build passed.
- `git diff --check` passed after removing frontend trailing whitespace.

Remaining limitation: the existing broad `tests/test_itr2_input_validation.py` suite still contains five pre-existing profile/HUF validator failures unrelated to Schedule S. Those must be resolved separately before claiming the entire ITR-2 test suite is green. Schedule S is complete only for the newly supported employer-level fields; imported legacy drafts that carry only OS Section 89A cannot be treated as salary-level Schedule S 89A without explicit source attribution.
