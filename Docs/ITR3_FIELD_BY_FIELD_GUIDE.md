# ITR-3 Field-by-Field Guide (AY 2026-27) — Index

**Source:** `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf` (59 pages,
printed Gazette pages 75-133). Every field below was transcribed by directly reading the
rendered PDF pages (not `pdftotext` or any other text-extraction shortcut) — verbatim line-item
labels, column headers, units, formulas, and dropdown/checkbox options as actually printed, not
paraphrased.

**Coverage confirmed:** all 60 Parts/Schedules from `Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`
§0A's verified ordering appear here exactly once, in order, with no gaps and no duplication at
the file boundaries (checked by grepping the `##` headings across all four files after they were
written).

## The four files

| File | Sections | PDF pages |
|---|---|---|
| [`ITR3_FIELD_BY_FIELD_GUIDE_1_PERSONAL_INFO_TO_HP.md`](ITR3_FIELD_BY_FIELD_GUIDE_1_PERSONAL_INFO_TO_HP.md) | 1-13: Personal Information → Schedule HP | 1-19 (Gazette 75-93) |
| [`ITR3_FIELD_BY_FIELD_GUIDE_2_BP_TO_OS.md`](ITR3_FIELD_BY_FIELD_GUIDE_2_BP_TO_OS.md) | 14-24: Schedule BP → Schedule OS | 19-39 (Gazette 93-113) |
| [`ITR3_FIELD_BY_FIELD_GUIDE_3_CYLA_TO_SI.md`](ITR3_FIELD_BY_FIELD_GUIDE_3_CYLA_TO_SI.md) | 25-44: Schedule CYLA → Schedule SI | Gazette 114-123 |
| [`ITR3_FIELD_BY_FIELD_GUIDE_4_IF_TO_VERIFICATION.md`](ITR3_FIELD_BY_FIELD_GUIDE_4_IF_TO_VERIFICATION.md) | 45-60: Schedule IF → Verification | 44-59 (Gazette 118-133), confirmed page 59 is the true end of the form |

Each file's section numbering matches `ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` §0A's `#` column
exactly, so a given phase's PDF fields can be looked up by its phase number directly.

## Items needing a human visual spot-check

These are not transcription failures — each was read directly from the PDF and transcribed
exactly as it renders — but the printed layout itself is ambiguous, dense, or internally
inconsistent enough that a second pair of eyes on the actual page image is worth it before
coding against them blindly. None of these affect the Part/Schedule ordering or the field
*names* already verified in the implementation plan; they're column/row-level layout ambiguities.

1. **Schedule 80G, section D, row "iii Total"** (guide 3) — fell on a page break during
   transcription; inferred to exist by symmetry with sections A-C (which each print an explicit
   "iii Total" row) but not independently visually confirmed.
2. **Section A19(b)(I)(A)** (guide 1) — the source PDF's own indentation makes it ambiguous
   whether sub-items `(a)`/`(b)` answer `(I)(A)(ii)` specifically or `(I)(A)` as a whole;
   transcribed exactly as indented, not resolved.
3. **Table 63, 44AE goods-carriage rows** (guide 1) — the form doesn't print a fixed row count,
   only sample rows `(i)(a)`/`(i)(b)` before an "Add row" affordance; noted as-is, not invented.
4. **Part A-OI items 4a/4b and Schedule S's employer-nature dropdown** (guide 1) — no option list
   is printed on the page itself ("drop down to be provided"); transcribed as such rather than
   guessing options.
5. **Schedule 112A / 115AD's rightmost columns** (guide 2) — cost-basis/FMV/deduction/balance
   column headers and formula references (e.g. "(4*10)", "(7+12)") render visually compressed and
   close together; transcribed as printed, but worth a direct visual check if exact column
   assignment matters for the builder.
6. **Schedule CG Part D's eight 54-series deduction sub-tables** (54/54B/54D/54EC/54F/54G/54GA/
   115F) (guide 2) — near-identical `i`-`v` row structure repeated eight times with only minor
   per-section variation (e.g. 54EC has no Capital Gains Accounts Scheme sub-block); each was
   transcribed independently rather than assumed uniform, but the repetition makes this section
   easy to mis-transcribe by pattern-matching — worth a second look.
7. **Schedule FSI's column (e) formula** references a column "(d)" that isn't separately labeled
   in the printed table (guide 4).
8. **Schedule FA §A3 and §C** (guide 4) — column-number labels are reused/inconsistent in the
   PDF's own header row (e.g. "(2)" appears twice; "(9)" labels both a parent cell and its
   sub-column) — printed that way, not a transcription artifact.
9. **Schedule PTI's internal lettering** (guide 4) — inconsistent between its two printed row
   blocks (`B2`/`a`/`b` vs. `b2`/`1`/`2`); both transcribed exactly as printed, not normalized.
10. **Section 17-C's column numbering** repeats "13" across two adjacent header cells (guide 4).
11. **Section 17 has no standalone "TDS3" sub-table** — only lettered sub-sections A/B/C/D are
    printed on the page; sub-table C itself covers Form 16A/16B/16C/16D/16E (spanning both
    salary-adjacent and non-salary-property TDS in one table). **This matters for the
    implementation plan**: wherever `ScheduleTDS3` is mapped as if it were a separately printed
    subsection, it must instead be derived from sub-table C's own columns — there is no fifth
    lettered subsection on the actual page.

## How this relates to the implementation plan

`Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` already correctly notes `ScheduleTDS3` as "(C,
non-salary)" in its §0A table (row 59), which is consistent with finding #11 above — the plan
was already right on this point; this guide gives the literal field-level backing for why. The
Schedule AL threshold fix from the previous audit (₹1 crore, not ₹50L) is independently
re-confirmed here: guide 4's own transcription of section 53's heading already prints "(applicable
in a case where total income exceeds Rs. 1 crore)" verbatim.
