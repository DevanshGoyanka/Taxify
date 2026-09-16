# ITR-3 Field-by-Field Guide — Part 4: Schedule IF through Verification

Literal transcription reference, AY 2026-27, read directly from the rendered PDF pages
(not `pdftotext`). Source: `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf`,
Gazette pages 118–133 (PDF pages 44–59, the true end of the document — Verification is
confirmed to be the last thing printed; nothing follows it). No commentary, no
implementation notes — this is what the form prints, verbatim, field for field.

---

## 45. Schedule IF — Information regarding partnership firms in which you are partner

**Page:** 122.

Sub-heading: "Number of firms in which you are partner"

| Sl. No. | Name of the Firm | PAN of the firm | Whether the firm is liable for audit? (Yes/No) | Whether section 92E is applicable to firm? (Yes/No) | Percentage Share in the profit of the firm | Amount of interest due or received (i) | Amount of remuneration due or received (ii) | Capital balance on 31st March in the firm (iii) |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | **Total** | | | | | | | |

(Column numerals (i)/(ii)/(iii) print directly under the "interest"/"remuneration"/"capital
balance" headers as printed sub-labels.)

---

## 46. Schedule EI — Details of Exempt Income (Income not to be included in Total Income or not chargeable to tax)

**Page:** 122–124. Side-banner label printed vertically: "EXEMPT INCOME".

| # | Label as printed | Field ref |
|---|---|---|
| 1 | Interest income | `1` |
| 2(i) | Gross Agricultural receipts (other than income to be excluded under rule 7A, 7B or 8 of I.T. Rules) | `i` |
| 2(i-i) | Expenditure incurred on agriculture | `ii` |
| 2(iii) | Unabsorbed agricultural loss of previous eight assessment years | `iii` |
| 2(iv) | Agricultural income portion relating to Rule 7, 7A, 7B(1), 7B(1A) and 8 (from Sl. No. 38 of Sch. BP) | `iv` |
| 2(v) | Net Agricultural income for the year (i – ii – iii + iv) *(enter nil if loss)* | `2` |
| 2(vi) | "In case the net agricultural income for the year exceeds Rs.5 lakh, please furnish the following details *(Fill up details separately for each agricultural land)*" — header row, no numeric field itself | — |
| 2(vi)(a) | Name of district along with pin code in which agricultural land is located | — |
| 2(vi)(b) | Measurement of agricultural land in Acre | — |
| 2(vi)(c) | Whether the agricultural land is owned or held on lease *(drop down to be provided)* | — |
| 2(vi)(d) | Whether the agricultural land is irrigated or rain-fed *(drop down to be provided)* | — |
| 3 | Other exempt income (including exempt income of minor child) *(please specify)* | `3` |
| 4 | Income claimed as not chargeable to tax as per DTAA *(Applicable for non-residents only)* — table below | `4` |
| 5 | Pass through income claimed as not chargeable to tax *(Schedule PTI)* | `5` |
| 6 | Total (1+2+3+4+5) | `6` |

Item 4 DTAA table columns: **Sl. No. | Amount of income | Nature of income | Country name & Code | Article of DTAA | Head of Income | Whether TRC obtained (Y/N)**, rows `I`, `II`, then row `III` = "Total Income from DTAA claimed as not chargeable to tax" mapped to field `4`.

---

## 47. Schedule PTI — Pass Through Income details from business trust or investment fund as per section 115U, 115UA and 115UB

**Page:** 123–125. Side-banner: "PASS THROUGH INCOME".

Column headers (numbered (1)–(10) as printed): **Sl. (1) | Investment entity covered by section 115U/115UA/115UB (2) | Name of business trust/investment fund (3) | PAN of the business trust/investment fund (4) | Sl. (5) | Head of income (6) | Current Year income (7) | Share of current year loss distributed by Investment fund (8) | Net Income/Loss 9=7-8 (9) | TDS on such amount, if any (10)**

Repeating block per investment entity (rows 1, 2, … each with the identical internal head-of-income breakdown):

- Column (2) is a dropdown ("drop down to be provided").
- (5)/(6) internal rows:
  - `i` House property
  - `ii` Capital Gains
    - `a` Short term
      - `a1` Section 111A
    - `b` Long term
      - `b1` Section 112A
      - `B2` Sections other than 112A *(row 2's block prints this same sub-item as `b2` lower-case — printed inconsistently between row 1's "B2" and row 2's "b2")*
  - `iii` Other Sources
    - (row 1) `a` Dividend, `b` Others — (row 2) `1` Dividend, `2` Others *(numbering style differs between the two printed row blocks)*
  - `iv` Income claimed to be exempt
    - `A` u/s 10(23FBB)
    - `B` u/s ……………..
    - `C` u/s …………

Columns 8/9/10 are shaded (not applicable) for the `iv` "Income claimed to be exempt" rows in both blocks.

---

## 48. Schedule-TPSA — Details of Tax on secondary adjustments as per section 92CE(2A) as per the schedule provided in e-filing utility

**Page:** 125. Side-banner: "TAX ON SECONDARY ADJUSTMENTS AS PER SECTION 92CE(2A)".

| # | Label as printed | Field ref |
|---|---|---|
| 1 | Amount of primary adjustments on which option u/s 92CE(2A) is exercised & such excess money has not been repatriated within the prescribed time (please indicate the total of adjustments made in respect of all the AYs) | `1` |
| 2(a) | Additional Income tax payable @ 18% on above | `a` |
| 2(b) | Surcharge @ 12% on "a" | `b` |
| 2(c) | Health & Education cess on (a + b) | `c` |
| 2(d) | Total Additional tax payable (a + b + c) | `d` |
| 3 | Taxes paid | `3` |
| 4 | Net tax payable (2d-3) | `4` |
| 5 | Date(s) of deposit of tax on secondary adjustments as per section 92CE(2A) | table: Date 1 – Date 6, each `(DD/MM/YYYY)` |
| 6 | Name of Bank and Branch | `6` |
| 7 | BSR Code | `7` |
| 8 | Serial number of challan | `8` |
| 9 | Amount deposited | `9` |

---

## 49. Schedule FSI — Details of Income from outside India and tax relief (available only in case of resident)

**Page:** 125. Side-banner: "INCOME FROM OUTSIDE INDIA".

Column headers: **Sl. | Country Code *(dropdown to be provided in the e-filing utility)* | Taxpayer Identification Number | Sl. | Head of income | Income from outside India (included in PART B-TI) (a) | Tax paid outside India (b) | Tax payable on such income under normal provisions in India (c) | Tax relief available in India (e)=(c) or (d) whichever is lower | Relevant article of DTAA if relief claimed u/s 90 or 90A (f)**

*(Printed exactly as shown: the formula for column (e) references a "(d)" that has no separately labeled column header in this table — transcribed as printed, not corrected.)*

Repeating per-country block (rows 1, 2, …), each with internal sub-rows `i` Salary, `ii` House Property, `iii` Business or Profession, `iv` Capital Gains, `v` Other sources, then a `Total` row.

---

## 50. Schedule TR — Summary of tax relief claimed for taxes paid outside India (available only in case of resident)

**Page:** 125–126. Side-banner: "TAX RELIEF FOR TAX PAID OUTSIDE INDIA".

Item 1 "Details of Tax relief claimed" — columns: **Country Code (a) | Taxpayer Identification Number (b) | Total taxes paid outside India (total of (c) of Schedule FSI in respect of each country) (c) | Total tax relief available (total of (e) of Schedule FSI in respect of each country) (d) | Section under which relief claimed (specify 90, 90A or 91) (e)**, then a `Total` row.

| # | Label as printed | Field ref |
|---|---|---|
| 2 | Total Tax relief available in respect of country where DTAA is applicable (section 90/90A) *(Part of total of 1(d))* | `2` |
| 3 | Total Tax relief available in respect of country where DTAA is not applicable (section 91) *(Part of total of 1(d))* | `3` |
| 4 | Whether any tax paid outside India, on which tax relief was allowed in India, has been refunded/credited by the foreign tax authority during the year? If yes, provide the details below | `4`, Yes/No |
| 4(a) | Amount of tax refunded | — |
| 4(b) | Assessment year in which tax relief allowed in India | — |

---

## 51. Schedule FA — Details of Foreign Assets and Income from any source outside India

**Page:** 126–127. Side-banner: "DETAILS OF FOREIGN ASSETS". All sub-tables (A1–G) report
holdings "at any time during the calendar year ending as on 31st December 2025."

### A1 — Details of Foreign Depository Accounts held (including any beneficial interest)

Columns (numbered (1)–(12)): **Sl No (1) | Country name (2) | Country code (3) | Name of financial institution (4) | Address of financial institution (5) | ZIP code (6) | Account number (7) | Status (8) | Account opening date (9) | Peak balance during the period (10) | Closing balance (11) | Gross interest paid/credited to the account during the period (12)**

### A2 — Details of Foreign Custodial Accounts held (including any beneficial interest)

Same column structure as A1, with column (12) relabeled: **Gross amount paid/credited to the
account during the period (12)** *(drop down to be provided specifying nature of amount viz.
interest/dividend/proceeds from sale or redemption of financial assets/other income)*.

### A3 — Details of Foreign Equity and Debt Interest held (including any beneficial interest) in any entity

Columns (1)–(13): **Sl No (1) | Country name (2) | Country code (2) | Name of entity (3) |
Address of entity (4) | ZIP code (5) | Nature of entity (6) | Date of acquiring the interest (7)
| Initial value of the investment (8) | Peak value of investment during the period (9) |
Closing value (10) | Total gross amount paid/credited with respect to the holding during the
period (11) | Total gross proceeds from sale or redemption of investment during the period
(12)** *(column-number printing has "Country name"/"Country code" both anchored near (2) as a
merged two-part column, and the last two columns print as (12)/(13) in the header row though the
body only shows 13 distinct data columns total — transcribed as printed)*.

### A4 — Details of Foreign Cash Value Insurance Contract or Annuity Contract held (including any beneficial interest)

Columns (1)–(9): **Sl No | Country name | Country code | Name of financial institution in which
insurance contract held | Address of financial institution | ZIP code | Date of contract | The
cash value or surrender value of the contract | Total gross amount paid/credited with respect to
the contract during the period**

### B — Details of Financial Interest in any Entity held (including any beneficial interest)

Columns (1)–(12): **Sl No (1) | Country Name (2a) | Zip Code (2b) | Nature of entity (3) | Name
and Address (4) | Nature of Interest-Direct/Beneficial owner/Beneficiary (5) | Date since held
(6) | Total Investment (at cost) (in rupees) (7) | Income accrued from such Interest (8) | Nature
of Income (9) | Income taxable and offered in this return** split into **Amount (10) | Schedule
where offered (11) | Item number of schedule (12)**

### C — Details of Immovable Property held (including any beneficial interest)

Columns (1)–(11): **Sl No (1) | Country Name and code (2a/2b) | ZIP Code (3) | Address of the
Property (4) | Ownership-Direct/Beneficial owner/Beneficiary (5) | Date of acquisition (6) |
Total Investment (at cost) (in rupees) (7) | Income derived from the property (8) | Nature of
Income (9)** then **Income taxable and offered in this return**: **Amount (9) | Schedule where
offered (10) | Item number of schedule (11)** *(printed column-number sequence has (9) reused
across both the "Nature of Income" cell and the start of the taxable-income sub-block —
transcribed as printed)*.

### D — Details of any other Capital Asset held (including any beneficial interest)

Same column structure as C, with column 3 relabeled **Nature of Asset** in place of "Address of
the Property."

### E — Details of account(s) in which you have signing authority held (including any beneficial interest) ... and which has not been included in A to D above

Columns (1)–(11): **Sl No | Name of the Institution in which the account is held | Address of the
Institution | Country Name and Code | ZIP Code | Name of the account holder | Account Number |
Peak Balance/Investment during the year (in rupees) | Whether income accrued is taxable in your
hands | If (7) is yes, Income accrued in the account** then **If (7) is yes, Income offered in
this return**: Amount / Schedule where offered / Item number of schedule.

### F — Details of trusts, created under the laws of a country outside India, in which you are a trustee, beneficiary or settlor

Columns (1)–(12): **Sl No | Country Name and code | ZIP Code | Name and address of the trust |
Name and address of trustees | Name and address of Settlor | Name and address of Beneficiaries |
Date since position held | Whether income derived is taxable in your hands | If (8) is yes, Income
derived from the trust** then **If (8) is yes, Income offered in this return**: Amount / Schedule
where offered / Item number of schedule.

### G — Details of any other income derived from any source outside India (i) which is not included in items A to F above or, (ii) income under the head business or profession

Columns (1)–(9): **Sl No | Country Name and code | ZIP Code | Name and address of the person from
whom derived | Income derived | Nature of income | Whether taxable in your hands** then **If (6)
is yes, Income offered in this return**: Amount / Schedule where offered / Item number of schedule.

**Footer NOTE (printed verbatim at the bottom of Schedule FA):** "In case of an individual, not
being an Indian citizen, who is in India on a business, employment or student visa, an asset
acquired during any previous year in which he was non-resident is not mandatory to be reported in
this schedule if no income is derived from that asset during the current previous year."

---

## 52. Schedule 5A — Information regarding apportionment of income between spouses governed by Portuguese Civil Code

**Page:** 128.

- "Name of the spouse" — free field.
- "PAN/Aadhaar No. of the spouse" — free field.
- "Whether books of account of spouse is audited u/s 44AB or under any other provisions (other
  than u/s 92E) of this Act or under any other Acts? or Whether your spouse is a partner of a
  firm whose accounts are required to be audited u/s 44AB under this Act or under any other
  provisions (other than u/s 92E) of this Act or under any other Acts?" — Yes/No.
- "Whether books of account of spouse is audited u/s 92E? or Whether your spouse is a partner of
  a firm whose accounts are required to be audited u/s 92E under this Act?" — Yes/No.

Table — columns: **Heads of Income (i) | Receipts received under (ii) | Amount apportioned in the
hands of the spouse (iii) | Amount of TDS deducted on income at (iv) | TDS apportioned in the
hands of spouse (v)**, rows: `1` House Property, `2` Business or profession, `3` Capital gains,
`4` Other sources, `5` Total.

---

## 53. Schedule AL — Assets and Liabilities at the end of the year (other than those included in Part A-BS) (applicable in a case where total income exceeds Rs. 1 crore)

**Page:** 128. Side-banner: "DETAILS OF ASSETS AND LIABILITIES". **Confirms the ₹1 crore
threshold directly from the printed heading** — "applicable in a case where total income exceeds
Rs. 1 crore" — corroborating the fix already made to `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`.

**A — Details of immovable assets.** Columns: **Sl.No. (1) | Description (2) | Address (3) | Pin
code (4) | Amount (cost) in Rs. (5)**.

**B — Details of movable assets.** Columns: **Sl.No. (1) | Description (2) | Amount (cost) in
Rs. (3)**, rows:
- `(i)` Jewellery, bullion etc.
- `(ii)` Archaeological collections, drawings, painting, sculpture or any work of art
- `(iii)` Vehicles, yachts, boats and aircrafts
- `(iv)` Financial assets — with its own **Amount (cost) in Rs.** column and sub-rows:
  - `(a)` Bank (including all deposits)
  - `(b)` Shares and securities
  - `(c)` Insurance policies
  - `(d)` Loans and advances given
  - `(e)` Cash in hand

**C — Interest held in the assets of a firm or association of persons (AOP) as a partner or
member thereof.** Columns: **Sl.No. (1) | Name and address of the firm(s)/AOP(s) (2) | PAN of the
firm/AOP (3) | Assessee's investment in the firm/AOP on cost basis (4)**.

**D** — "Liabilities in relation to Assets at (A + B + C)" — single field, no sub-table.

---

## 54. Schedule GST — Information regarding turnover/gross receipt reported for GST

**Page:** 128. Side-banner: "DETAILS OF GST".

Columns: **Sl.No. (1) | GSTIN No(s). (2) | Annual value of outward supplies as per the GST
return(s) filed (3)**.

**Footer NOTE (printed verbatim):** "Please furnish the information above for each GSTIN No.
separately"

---

## 55. Schedule: Tax deferred on ESOP — Information related to Tax deferred - relatable to income on perquisites referred in section 17(2)(vi) received from employer, being an eligible start-up referred to in section 80-IAC

**Page:** 129. Side-banner: "DETAILS".

- "PAN of the employer being an eligible startup" — free field.
- "DPIIT registration number of the employer" — free field.

Table columns (numbered 1–8): **Sl. No. (1) | Assessment Year (2) | Amount of Tax deferred
brought forward (3)** then, under the shared header "Has any of the following events occurred
during the previous year relevant to current assessment year":
- **(4)** Such specified security or sweat equity shares were sold — `(i)` Fully / `(ii)` Partly /
  `(iii)` Not sold. Specify the date and amount of **tax attributed** to such sale out of Col 3
  *(Details to be provided as per utility)*.
- **(5)** Ceased to be the employee of the employer who allotted or transferred such specified
  security or sweat equity share? — Yes/No. If yes, specify date.
- **(6)** Forty-eight months have expired from the end of the relevant assessment year in which
  specified security or sweat equity shares referred to in the said *clause were allotted. If
  yes, specify date. — printed as *"(To be enabled from AY 2027-28) (Payment to be made in FY
  2026-27)"*.
- **(7)** Amount of tax payable in the current Assessment Year *(to be populated from col. 3 or 4
  as the case maybe)*.
- **(8)** Balance amount of tax deferred to be carried forward to next Assessment years — printed
  as "Col (3-7)".

Rows: Sl. 1–5 for AYs 2021-22 through 2025-26 (each printing "Sl. No. 8 of Schedule ESOP for last
year" under column 2/3's carried-forward reference), and Sl. 6 for the current AY 2026-27 (columns
2 and 4 onward shaded, i.e. not applicable for the current year's own opening row).

---

## 56. Part B – TI — Computation of total income

**Page:** 130–131. Side-banner: "TOTAL INCOME".

| # | Label as printed (with cross-reference) | Field ref |
|---|---|---|
| 1 | Salaries *(6 of Schedule S)* | `1` |
| 2 | Income from house property *(3 of Schedule-HP)* (enter nil if loss) | `2` |
| 3 | Profits and gains from business or profession — header (no value cell) | — |
| 3(i) | Profit and gains from business other than speculative business and specified business *(A37 of Schedule BP)* (enter nil if loss) | `3i` |
| 3(ii) | Profit and gains from speculative business *(3(ii) of Table E of Schedule BP)* (enter nil if loss and take the figure to schedule CFL) | `3ii` |
| 3(iii) | Profit and gains from specified business *(3(iii) of Table E of Schedule BP)* (enter nil if loss and take the figure to schedule CFL) | `3iii` |
| 3(iv) | Income chargeable to tax at special rates *(3e, 3f & 3g of Schedule BP)* | `3iv` |
| 3(v) | Total (3i + 3ii + 3iii + 3iv) (enter nil if 3v is a loss) | `3v` |
| 4 | Capital gains — header | — |
| 4(a) Short term — header | — | |
| 4(a)(i) | Short-term chargeable @ 20% *(8ii of item E of schedule CG)* | `ai` |
| 4(a)(ii) | Short-term chargeable @ 30% *(8iii of item E of schedule CG)* | `aii` |
| 4(a)(iii) | Short-term chargeable at applicable rate *(8iv of item E of schedule CG)* | `aiii` |
| 4(a)(iv) | Short-term chargeable at special rates in India as per DTAA *(8v of item E of schedule CG)* | `aiv` |
| 4(a)(v) | Total Short-term (ai + aii + aiii + aiv) (enter nil if loss) | `4av` |
| 4(b) Long-term — header | — | |
| 4(b)(i) | Long-term chargeable @ 12.5% *(8vi of item E of schedule CG)* | `bi` |
| 4(b)(ii) | Long-term chargeable at special rates in India as per DTAA *(8vii of item E of schedule CG)* | `bii` |
| 4(b)(iii) | Total Long-term (bi + bii) (enter nil if loss) | `4biii` |
| 4(c) | Sum of Short-term/Long-term capital gains (4av+4biii) (enter nil if loss) | `4c` |
| 4(d) | Capital gain chargeable @ 30% u/s 115BBH *(C2 of schedule CG)* | `4d` |
| 4(e) | Total capital gains (4c + 4d) | `4e` |
| 5 | Income from other sources — header | — |
| 5(a) | Net income from other sources chargeable to tax at normal applicable rates *(6 of Schedule OS)* (enter nil if loss) | `5a` |
| 5(b) | Income chargeable to tax at special rates *(2 of Schedule OS)* | `5b` |
| 5(c) | Income from the activity of owning and maintaining race horses *(8e of Schedule OS)* (enter nil if loss) | `5c` |
| 5(d) | Total (5a + 5b + 5c) (enter nil if loss) | `5d` |
| 6 | Total of head wise income (1 + 2 + 3v + 4e + 5d) | `6` |
| 7 | Losses of current year to be set off against 6 *(total of 2xvi, 3xvi and 4xvi of Schedule CYLA)* | `7` |
| 8 | Balance after set off current year losses (6 – 7) *(total of serial number (ii) to (xv) column 5 of Schedule CYLA + 5b + 3iv)* | `8` |
| 9 | Brought forward losses to be set off against 8 *(total of 2xv, 3xv and 4xv of Schedule BFLA)* | `9` |
| 10 | Gross Total income (8-9) *(also total of serial no (i) to (xiii) of column 5 of Schedule BFLA + 5b + 3iv)* | `10` |
| 11 | Income chargeable to tax at special rate under section 111A, 112, 112A etc. included in 10 | `11` |
| 12 | Deductions under Chapter VI-A — header | — |
| 12(a) | Part-B, CA and D of Chapter VI-A *[(1 + 3) of Schedule VI-A and limited upto (total of i,ii,iii,iv,v,viii,xii,xiii) of column 5 of BFLA]* | `12a` |
| 12(b) | Part-C of Chapter VI-A *[2 of Schedule VI-A]* | `12b` |
| 12(c) | Total (12a + 12b) *[limited upto (10-11)]* | `12c` |
| 13 | Deduction u/s 10AA *(c of Sch. 10AA)* | `13` |
| 14 | Total income (10 -12c-13) | `14` |
| 15 | Income which is included in 14 and chargeable to tax at special rates *(total of (i) of schedule SI)* | `15` |
| 16 | Net agricultural income/ any other income for rate purpose *(2v of Schedule EI)* | `16` |
| 17 | Aggregate income (14-15+16) *[applicable if (14-15) exceeds maximum amount not chargeable to tax]* | `17` |
| 18 | Losses of current year to be carried forward *(total of row xix of Schedule CFL)* | `18` |
| 19 | Deemed income under section 115JC *(3 of Schedule AMT)* | `19` |

---

## 57. Part B – TTI — Computation of tax liability on total income

**Page:** 131–133. Side-banner (spanning items 1–9): "COMPUTATION OF TAX LIABILITY". Side-banner
(item 10): "TAXES PAID". Side-banner (items 13–14): "BANK ACCOUNT".

| # | Label as printed | Field ref |
|---|---|---|
| 1(a) | Tax payable on deemed total income under section 115JC *(4 of Schedule AMT)* | `1a` |
| 1(b) | Surcharge on (a) *(if applicable)* | `1b` |
| 1(c) | Health and Education Cess @ 4% on (1a+1b) above | `1c` |
| 1(d) | Total Tax Payable on deemed total income (1a+1b+1c) | `1d` |
| 2 | Tax payable on total income — header | — |
| 2(a) | Tax at normal rates on 17 of Part B-TI | `2a` |
| 2(b) | Tax at special rates *(total of col. (ii) of Schedule-SI)* | `2b` |
| 2(c) | Rebate on agricultural income *[applicable if (14-15) of Part B-TI exceeds maximum amount not chargeable to tax]* | `2c` |
| 2(d) | Tax Payable on Total Income (2a + 2b – 2c) | `2d` |
| 2(e) | Rebate under section 87A | `2e` |
| 2(f) | Tax payable after rebate (2d – 2e) | `2f` |
| 2(g) | Surcharge — header, three-column sub-table: **Surcharge computed before marginal relief / (blank) / Surcharge after marginal relief** | — |
| 2(g)(i) | @ 25% of *16(ii) of Schedule SI* | `2gi` → `ia` |
| 2(g)(ii) | @10% or 15%, as applicable | `2gii` → `iia` |
| 2(g)(iii) | On [(2f) – *16(ii) of Schedule SI*- tax on income referred in 2g(ii) above)] | `2giii` |
| 2(g)(iv) | Total (ia + iia) | `2giv` |
| 2(h) | Health and Education Cess @ 4% on (2f + 2giii) | `2h` |
| 2(i) | Gross tax liability (2f+ 2giv + 2h) | `2i` |
| 3 | Gross tax payable (higher of 1d and 2i) | `3` |
| 3(a) | Tax on income without including income on perquisites referred in section 17(2)(vi) received from employer, being an eligible start-up referred to in section 80-IAC(3-3b) | `3a` |
| 3(b) | Tax deferred - relatable to income on perquisites referred in section 17(2)(vi) received from employer, being an eligible start-up referred to in section 80-IAC | `3b` |
| 3(c) | Tax deferred from earlier years but payable during current AY *(total of col 7 of schedule Tax deferred on ESOP)* | `3c` |
| 4 | Credit under section 115JD of tax paid in earlier years *(applicable if 2i is more than 1d)* *(5 of Schedule AMTC)* | `4` |
| 5 | Tax payable after credit under section 115JD (3a+3c – 4) | `5` |
| 6 | Tax relief — header | — |
| 6(a) | Section 89 *(Please ensure to submit Form 10E to claim this relief)* | `6a` |
| 6(b) | Section 90/ 90A *(2 of Schedule TR)* | `6b` |
| 6(c) | Section 91 *(3 of Schedule TR)* | `6c` |
| 6(d) | Total (6a + 6b+ 6c) | `6d` |
| 7 | Net tax liability (5 – 6d) *(enter zero if negative)* | `7` |
| 8 | Interest and fee payable — header | — |
| 8(a) | Interest for default in furnishing the return (section 234A) | `8a` |
| 8(b) | Interest for default in payment of advance tax (section 234B) | `8b` |
| 8(c) | Interest for deferment of advance tax (section 234C) | `8c` |
| 8(d) | Fee for default in furnishing return of income (section 234F) | `8d` |
| 8(da) | Fee for furnishing revised return of income (section 234-I) | `8da` |
| 8(e) | Total Interest and Fee Payable (8a+8b+8c+8d+8da) | `8e` |
| 9 | Aggregate liability (7 + 8e) | `9` |
| 10 | Taxes Paid — header | — |
| 10(a) | Advance Tax *(from column 5 of 17A)* | `10a` |
| 10(b) | TDS *(total of column 5 of 17B and column 9 of 17C)* | `10b` |
| 10(c) | TCS *(column 7(i) of 17D)* | `10c` |
| 10(d) | Self-Assessment Tax *(from column 5 of 17A)* | `10d` |
| 10(e) | Total Taxes Paid (10a+10b+10c+10d) | `10e` |
| 11 | Amount payable *(Enter if 9 is greater than 10e, else enter 0)* | `11` |
| 12 | Refund *(If 10e is greater than 9)* *(Refund, if any, will be directly credited into the bank account)* | `12` |
| 13 | "Do you have a bank account in India (Non-Residents claiming refund with no bank account in India may select No)" — Select Yes or No | `13` |
| 13(i) | a) Details of all Bank Accounts held in India at any time during the previous year (excluding dormant accounts) — table: **Sl. | IFS Code of the Bank in case of Bank Accounts held in India | Name of the Bank | Account Number | Type of account (Dropdown to be provided by e-filing utility) | Select Account for refund credit (tick at least one account √)**, rows I, II | — |
| — | Note under 13(i) (printed verbatim): "1. All bank accounts held at any time are to be reported, except dormant A/c. 2. In case multiple accounts are selected, the refund will be credited to one of the validated accounts after processing the return." "Rows can be added as required" | — |
| 13(ii) | b) Non-residents, not having bank account in India may, at their option, furnish the details of one foreign bank account — table: **Sl. No. | SWIFT Code | Name of the Bank | Country of Location | IBAN** | — |
| 14 | "Do you at any time during the previous year,- (i) hold, as beneficial owner, beneficiary or otherwise, any asset (including financial interest in any entity) located outside India; or (ii) have signing authority in any account located outside India; or (iii) have income from any source outside India? *[applicable only in case of a resident] [Ensure Schedule FA is filled up if the answer is Yes]*" — ○Yes ○No | `14` |

---

## 58. Tax Return Preparer (TRP) details

**Page:** 133. Printed as item 15/16, before Section 17.

| # | Label as printed |
|---|---|
| 15 | "If the return has been prepared by a Tax Return Preparer (TRP) give further details below:" — fields: **Identification No. of TRP | Name of TRP | Counter Signature of TRP** |
| 16 | If TRP is entitled for any reimbursement from the Government, amount thereof |

---

## 59. Section 17 — TAX PAYMENTS

**Page:** 133. Printed as item 17, with lettered sub-sections A–D. Side-banner labels printed
vertically per sub-table: "ADVANCE/SELF ASSESSMENT TAX" (A), "TDS ON SALARY" (B).

### 17-A — Details of payments of Advance Tax and Self-Assessment Tax

Columns: **Sl No (1) | BSR Code (2) | Date of Deposit (DD/MM/YYYY) (3) | Serial Number of Challan
(4) | Amount (Rs.) (5)**, rows i–iv.

**Footer NOTE (printed verbatim):** "Enter the totals of Advance tax and Self-Assessment tax in
Sl. No. 10a & 10d of Part B-TTI"

### 17-B — Details of Tax Deducted at Source from Salary [As per Form 16 issued by Employer(s)]

Columns: **Sl No (1) | Tax Deduction Account Number (TAN) of the Employer (2) | Name of the
Employer (3) | Income chargeable under Salaries (4) | Total tax deducted (5)**, rows I, II.

**Footer NOTE (printed verbatim):** "Please enter total of column 5 in 10b of Part B-TTI"

### 17-C — Details of Tax Deducted at Source (TDS) on Income [As per Form 16A issued or Form 16B/16C/16D/16E furnished by Deductor(s)]

Columns (numbered (1)–(13)): **Sl No (1) | TDS credit relating to self/other person [spouse as
per section 5A/other person as per rule 37BA(2)] (2) | PAN/Aadhaar No. of Other Person (if TDS
credit related to other person) (3) | TAN of the Deductor/PAN/Aadhaar No. of Tenant/Buyer (4) |
Section under which TDS is deducted (4a) | Unclaimed TDS brought forward (b/f) (5)** — split into
**Fin. Year in which deducted / Amount b/f** — **TDS of the current Financial Year (TDS Deducted
during the FY 2025-26) (6)** split into **Deducted in own hands / Deducted in the hands of spouse
as per section 5A or any other person as per rule 37BA(2) (if applicable)** — **(7) TDS credit
being claimed this Year (Only if corresponding income is being offered for tax this year, not
applicable u/s 194N)** split into **Claimed in own hands (8) / Claimed in the hands of spouse as
per section 5A or any other person as per rule 37-I(1) (if applicable) (9)**, each of which
further splits into **Income | TDS | PAN/Aadhaar No.** — **Gross Amount (11) | Head of Income (12)
| Corresponding Receipt/withdrawals offered (13)** — **TDS credit being carried forward (13)**
*(the printed column-number sequence repeats "13" for both the last two headers — transcribed as
printed)*. Row: `i`.

### 17-D — Details of Tax Collected at Source (TCS) [As per Form 27D issued by the Collector(s)]

Columns: **Sl.No. (1) | TCS relating to self/other person [spouse as per section 5A/ other person
as per rule 37-I(1)] (2)(i) | Tax Deduction and Tax Collection Account Number of the Collector
(2)(ii) | PAN of other Person (if TCS credit related to other person) (3) | Unclaimed TCS brought
forward (b/f)** split into **Fin. Year in which collected (4) / Amount b/f (5)** — **TCS of the
current fin. year** split into **Collected in own hands (6)(i) / Collected in the hands of spouse
as per section 5A or any other person as per rule 37-I(1) (if applicable) (6)(ii)** — **TCS credit
being claimed this Year** split into **Claimed in own hands (7)(i) / Claimed in the hands of
spouse as per section 5A or any other person as per rule 37-I(1) (if applicable) (7)(ii)**, itself
split into **TCS | PAN** — **TCS credit being carried forward (8)**. Row: `i`.

**Footer NOTE (printed verbatim):** "Please enter total of column (7)(i) in 10c of Part B-TTI"

---

## 60. VERIFICATION

**Page:** 133. Final section of the form — confirmed nothing else is printed after this; page 133
is the literal end of the 59-page PDF.

Printed declaration text (verbatim, with blanks shown as `___`):

> "I, `___` son/ daughter of `___` solemnly declare that to the best of my knowledge and belief,
> the information given in the return and schedules thereto is correct and complete and is in
> accordance with the provisions of the Income-tax Act, 1961. I further declare that I am making
> returns in my capacity as `___` *(drop down to be provided)* and I am also competent to make
> this return and verify it. I am holding permanent account number `___` *(if allotted)*. I
> further declare that the critical assumptions specified in the agreement have been satisfied
> and all the terms and conditions of the agreement have been complied with. (Applicable in a
> case where return is furnished under section 92CD)"

Fields: **Date | Place | Sign here ➔**.

*(A digital-signature stamp block appears in the bottom-right corner of the printed Gazette page
— "SARVESH KUMAR SRIVASTAVA / Digitally signed by SARVESH KUMAR SRIVASTAVA / Date: ... / ..." —
this is the Gazette publication's own signing block, not a form field, and is not part of the
ITR-3 schema.)*

---

## Uncertain / flagged during transcription

1. **Schedule FSI's column (e)'s formula** references "(d)" but no column is separately labeled
   (d) in the printed table — transcribed exactly as printed, not corrected or inferred.
2. **Schedule FA §A3**'s column-number labels print "(2)" twice (once under "Country name," once
   under "Country code") and the tail end of the header row shows (12)/(13) while the visible data
   columns total 13 — transcribed as printed; the merged/reused numbering is the form's own layout
   artifact, not a transcription error on this pass.
3. **Schedule FA §C**'s "Income taxable and offered in this return" sub-block reuses column number
   (9) for both the parent "Nature of Income" cell and the first sub-column — printed that way,
   not adjusted.
4. **Schedule PTI**'s internal lettering for "Long term"/"Other Sources" sub-items is inconsistent
   between the row-1 block (`B2`, `a`/`b`) and the row-2 block (`b2`, `1`/`2`) — both transcribed
   exactly as printed rather than normalized to one style.
5. **Section 17-C**'s column-number sequence repeats "13" across two adjacent header cells (Gross
   Amount/Head of Income block vs. TDS-carried-forward) — printed that way in the source table,
   transcribed as-is.
6. No standalone "TDS3" sub-table is printed anywhere in Section 17 as its own lettered
   subsection — only A/B/C/D appear on the page. Whatever schema block(s) the implementation plan
   maps to a "TDS3" concept must derive from sub-table C's own columns (which cover Form
   16A/16B/16C/16D/16E, i.e. both salary-adjacent and non-salary-property TDS in one printed
   table) — this transcription does not invent a fifth lettered sub-section that isn't on the page.
