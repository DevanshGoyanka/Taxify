# Taxify Frontend UI/UX Audit &amp; CA-Perspective Redesign Blueprint

**Prepared:** 2026-09-16
**Scope:** Every file in `frontend/src/` read in full (151 source files), split across five parallel audit passes so nothing was sampled — plus a broad survey of the Indian ITR-filing and CA-practice-software market.
**Trigger:** The product owner (a practising CA) flagged the current UI as "a complete mess — no clarity in anything... no consistency across pages," specifically naming the Capital Gains and Business/Profession tabs as the worst offenders, and asked for a full-file audit (no spot-checking) plus a detailed redesign plan for all five income heads, informed by how existing market players handle the same problems.

---

## 1. Executive summary

Capital Gains and Business/Profession look worse than the rest of the app because they carry the most CBDT complexity with the least design attention — but they are not an isolated problem. They are the sharpest expression of a pattern that runs through all 151 files.

Taxify was not styled inconsistently by accident. It was built the way most tax software gets built under deadline pressure: one schedule at a time, one developer at a time, each one solving "how do I get this CBDT field onto a screen" fresh, with no shared vocabulary to reach for. A real design-token system exists — a navy-and-gold palette, four typefaces, a full CSS variable set in `index.css` — but it governs the shell (the sidebar, the dashboard, the login chrome) and almost nothing else. The moment a CA opens an actual income-head tab, that system disappears and each form reaches for its own inline styles, its own colors, its own idea of what a "computed field" or an "add row" button should look like.

The result is not one bug. It's roughly a dozen small, structural decisions repeated inconsistently across 150 files — no shared component library, raw CBDT field codes surfacing as labels, five different greens for the same button, no progressive disclosure on the longest forms, generic "Entry #1" row labels, and (this is the one that should worry engineering most) a confirmed money-safety bug where a Decimal value arriving as a JSON string silently inflated a real client's turnover tenfold before someone patched it in one file and not its twin.

The blueprint in this document is not a coat of paint. It proposes a real component library, a real label glossary for the ~370 CBDT fields that currently have none, a wizard structure for the two schedules that most need one, and a phased path to get there without freezing the product mid-filing-season.

---

## 2. Methodology

No spot-checking. Every file in `frontend/src/` was read in full — pages, components, the domain/logic layer that drives what labels and tabs actually render, utilities, and the shared type system — split across five parallel passes:

| Pass | Scope | Files |
|---|---|---|
| 1 | Capital Gains & Business/Profession — the two flagged areas, in full depth | 12 |
| 2 | The ITR-3 schedule-editor family (AMT, AL/FA/ESOP, CYLA/BFLA, Foreign Schedules, PTI, Part A P&L/BS, Part A-OI, Part A-QD, Special Schedules, TPSA, Tax Payment, Personal Info) | 21 |
| 3 | Every other income-head manager — Salary, House Property, Other Sources, Deductions, the shared modals, the five UI primitives, the layout shell | 31 |
| 4 | Every page and the navigation shell, including a full off-token colour census | 20 |
| 5 | The domain/logic layer — the schedule registry, formatters, type definitions, import mappers | 53 |

Alongside the code, the Indian ITR-filing and CA-practice-software market was surveyed broadly — both the modern cloud platforms individual taxpayers use and the legacy desktop suites CAs have relied on for a decade — plus two international products for wizard-design reference. Section 4 covers what's worth borrowing from each.

---

## 3. Fourteen root causes

Every finding across all five passes reduces to one of these fourteen. Fix these and the hundred-odd small inconsistencies underneath them mostly resolve on their own.

### 1. There is no shared component library, so every screen reinvents one
The `components/ui/` folder holds five files and 114 lines total — `Badge`, `CollapsibleWarning`, `EmptyState`, `SkeletonRow`, `Spinner`. Nothing else: no `Button`, `Input`, `Select`, `Card`, `Modal`, or `FormField`. Across the 64 form-bearing components read, we counted at least eight independent re-implementations of "label + input", six of "collapsible entry card", and five of "empty state message" — and confirmed `EmptyState`, `SkeletonRow`, and `Spinner` are used by **zero** of the 23 income-head manager files that would benefit from them.

### 2. A real design-token system exists — and is bypassed constantly
`index.css` defines a genuine palette (`--navy`, `--gold`, `--bg`, `--text-primary`, `--border`, etc.) used correctly by the app shell. But `BankAccountManager.tsx`, `Section80CManager.tsx`, `Section80DManager.tsx`, `DonationEntryManager.tsx`, `DeductionLoanManager.tsx`, all four standalone Other-Sources managers, and `EmployerReconciliationModal.tsx` use **zero** token references — every colour is a raw hex literal. The main computation shell alone (`ITRComputationPage.tsx`) contributes roughly 25 distinct off-token values on its own, including a pure-black `#000000` border and a mismatched light-blue `#cfe2f3` tab wrapper unrelated to the brand palette.

### 3. The app wears three unrelated visual identities
The documented navy/gold/DM Sans system governs the dashboard and sidebar. `LoginPage.css` defines its own, entirely separate lavender/violet palette with its own `--loom-ink`/`--loom-muted` CSS variables and a sixth undocumented font (Raleway) — strong evidence it was copied from an unrelated template and never re-skinned. `LandingPage.css` defines a third, generic-gray palette, also in Raleway. A user's first two screens — Landing, then Login — look like two different products, neither of which resembles the Dashboard they land on next.

### 4. Raw CBDT field codes are shown directly to the CA as labels
At least four independent, hand-written "turn a CBDT field name into English" functions exist in the codebase — in `ITR3BusinessCoreManager.tsx`, `ITR3BusinessAuxiliaryManager.tsx`, `itr3ScheduleBP.ts`, and `ITR2SchedulesWorkspace.tsx` — each with a different, independently-typed abbreviation dictionary that will keep drifting apart. Five more files pass the raw field name straight through with no transformation at all. Confirmed directly in the code: a CA filling Part A-OI sees literal labels like `StkInsurPrem` and `RolyatyOrServiceFee` (a typo baked into the CBDT source and never caught); Schedule TPSA shows `AmtPrimaryAdjUs92CE_2A` as a field label; three files permanently print the raw JSON schema path underneath every field (e.g. `ScheduleCYLA.HP.IncCYLA.IncOfCurYrUnderThatHead`) as if it were help text.

### 5. No progressive disclosure where it matters most
Capital Gains (~20 CBDT sections), Personal Info (9+ sections, no collapse), Salary (8–11 sections per employer), Part A P&L + Balance Sheet (246 fields in one continuous grid) all render as one uninterrupted scroll. This isn't a capability gap: `ITR3BusinessWorkspace.tsx` already implements a clean five-step wizard, and `DeductionsWorkspace.tsx`/`ScheduleOSWorkspace.tsx` both implement a working accordion with running per-section totals. The pattern exists. It was simply never applied to the screens that need it most.

### 6. Two competing implementations of the same official schedule can silently diverge
Schedule BP has two independent renderers — a generic JSON-schema walker inside `ITR3BusinessCoreManager.tsx` and a hand-built editor, `ITR3ScheduleBPEditor.tsx`, that's the one actually wired into filing. The 44AD/44ADA/44AE presumptive-income editor exists twice, once per form (`ITR3PresumptiveManager.tsx`, `ITR4ScheduleBPManager.tsx`), built by copying one into the other. A real, documented production bug — string-concatenation silently inflating a declared turnover tenfold — was fixed with defensive coercion in the ITR-4 copy. The ITR-3 copy was never patched. Five standalone Other-Sources managers (dividend, interest, gifts, winnings, family pension) duplicate — less completely, and with at least two outright wrong section-code labels — what the consolidated `ScheduleOSWorkspace.tsx` already does properly.

### 7. The money type isn't safe, and the UI is quietly compensating for it, file by file
Backend Decimal fields sometimes arrive over the wire as JSON strings while their TypeScript type claims `number`. Three separate files (`ITR4ScheduleBPManager.tsx`, `scheduleBpAdapter.ts`, and defensive comments in `editorModelV2.ts`/`filingPreflight.ts`) each independently rediscovered and patched around this — and its near-twin, `ITR3PresumptiveManager.tsx`, never got the fix. No redesign of colour or layout fixes a return that silently files the wrong number.

### 8. Repeatable rows default to "Entry #1", not the transaction's own name
Capital gains transactions, exempt-income entries, donation and 80GGA/80GGC rows, house-property parcels, and every ITR-2-only schedule label their rows only by index. A CA reviewing 15 property sales or 20 scrip transactions cannot tell rows apart without opening each one. Exactly one file — `EmployerEntryManager.tsx`, which titles each card with the employer's own name once typed — already does this correctly. That should become the house rule, not the exception.

### 9. There is no single visual language for "primary action" or "this field is locked"
Save/Add/primary-action buttons appear in at least five unrelated greens across the app (`#5BB981`, `#16a34a`, `#15803D`, `#22a06b`, `#4CAF50`) — sometimes two different greens in the same file. "This field is computed, don't edit it" renders five different ways: plain grey, the gold-pale token (used correctly in Business/Profession but nowhere else), a literal placeholder string reading "Backend computed" typed inside the input, or no visual distinction from an editable field at all.

### 10. The app's own navigation registry documents its ITR-3 gaps — and may be stale about them
`scheduleRegistry.ts` is genuinely well engineered — a clean six-state status model and predicate-driven "is this required" logic. But eight schedules (AMT, Foreign Source Income, Foreign Tax Relief, Pass-Through Income, Assets & Liabilities, Schedule 5A, ESOP deferral, SI/SPI) are marked `missing` for ITR-3 while fully `available` for ITR-2. A CA moving between an ITR-2 and an ITR-3 client for conceptually identical situations gets two different levels of completeness — and several of the domain modules those schedules would need (`itr3ForeignSchedules.ts`, `itr3TPSA.ts`, `itr3Schedule80Coverage.ts`) already exist, suggesting the registry may simply be out of date rather than describing a real gap.

### 11. Two factual/legal-reference errors are baked directly into visible copy
The standalone `DividendEntryManager.tsx` stores a dividend under internal code `10(22e)` but displays it to the CA as `2(22)(e)` — a different Income-tax Act section entirely, and one any working CA would recognise as wrong. `WinningsManager.tsx` labels card-game winnings with TDS section 194B, which is actually the lottery section. These are the kind of errors that cost a product a CA's trust the first time they're spotted.

### 12. Ten fully-built pages sit completely unreachable from routing
Accounting, Billing, Calendar, Communication, Jobs, Notices, Reconciliation, Reports, Sync, and Tasks are each a complete, token-consistent page with no live data behind them and no route pointing to them. They're evidence of a broader firm-practice-management ambition — client billing, a compliance calendar, a notice tracker — that was started, built cleanly, and then shelved. Worth a product decision (revive or remove) before the redesign, rather than leaving them as silent dead weight.

### 13. Zero contextual help for the genuinely hard concepts
AMT, DTAA/foreign-tax relief, pass-through income, transfer-pricing secondary adjustment, and the gift-exemption rules (relative vs. non-relative, marriage exemption) get one line of description each, at most, and no per-field guidance. The technical means already exists — `PersonalInfoTab.tsx`'s `Field` component supports a `help` string and uses it for things like PAN format — it was simply never extended to the schedules that need it most.

### 14. No loading feedback, anywhere
`Spinner.tsx` and `SkeletonRow.tsx` exist, are correctly token-styled, and are used by zero of the 23 income-head files audited. Every "waiting on the backend to compute your eligible deduction" moment is static text — "Awaiting backend calculation" — not a loading state.

---

## 4. Who else a CA already uses

India's ITR-software market splits cleanly into two generations, plus the portal every return eventually has to clear. Each generation solves a different half of the problem Taxify has — and neither solves both.

### Tier one — the cloud generation
Built for volume and speed, often DIY-first with CA-assisted tiers layered on. Strongest at making an import feel trustworthy and a first-time filing feel guided.

| Player | What they do well |
|---|---|
| **ClearTax** | Broadest feature set of the DIY tier — 300+ income types, 80+ broker integrations for capital gains, AI-assisted chat filing, sub-8-minute claimed filing time for simple returns. |
| **Quicko** | Auto-imports capital-gains transactions directly from Zerodha/Upstox and formats them into schedule-ready detail — the closest thing this market has to "we already reconciled this for you." |
| **myITreturn** | A genuinely linear, step-by-step guided flow with direct Income Tax Department data import — low cognitive load for a straightforward salaried return. |
| **EZTax** | "EZ-Help" — field-by-field contextual assistance built into the form itself, so a taxpayer never has to leave the page to understand what a field means. |
| **TaxBuddy, Tax2Win, TaxSpanner, TaxRaahi** | Mobile-first or hybrid DIY/expert models; Tax2Win pairs an AI-DIY flow with a full regime-comparison tool up front. |
| **IndiaFilings, Vakilsearch, LegalRaasta** | Broader compliance platforms (company registration, GST, trademarks) with ITR as one service among many — less specialised tax UX, but instructive for bundling adjacent compliance work into one dashboard. |
| **Groww / Fisdom, 1Finance** | Brokerage-adjacent entrants filing ITR as an extension of an existing investment relationship — P&L statements flow straight from the brokerage account with no separate import step. |

### Tier two — the CA desktop suites
Built for professionals doing volume, multi-client work — not a single taxpayer's single return. This is Taxify's actual competitive set, and the tier most worth studying closely, because it already understands the CA's real workflow.

| Player | What they do well — and what to watch for |
|---|---|
| **Winman CA-ERP** | The pattern most worth stealing: *single-window computation* — data entry and the resulting computed tax sit in the same table, with no navigating between screens to see the effect of a change. Praised specifically for minimal key operations. |
| **Genius (SAG Infotech)** | Positions as a full compliance suite rather than a standalone filer — strong office automation; useful reference for eventually connecting Taxify's own shelved Billing/Calendar/Tasks pages to the filing workflow. |
| **Sinewave TaxSuite** | The one legacy player reviewers describe as having modernised its interface — proof a dense, CA-grade tool doesn't have to look or feel dated to stay dense and fast. |
| **Saral IncomeTax, EasyOFFICE, Webtel, Spectrum (KDK)** | Established, price-competitive, broadly similar single-window desktop paradigms. |
| **CompuTax** | The cautionary tale: reviewers explicitly describe it as "a legacy desktop interface that feels slow and cluttered compared to modern cloud tools" — exactly the reputation risk Taxify's current Capital Gains/Business tabs are courting. |

### The one everyone eventually has to clear
The government's own **e-Filing 2.0** portal (incometax.gov.in) auto-populates PAN, salary, capital gains, TDS and interest from its own prefill data, and is the final destination for every return regardless of which tool prepared it. It is the ground truth a CA reconciles against, not a design model to imitate — but its prefill transparency (exactly what was pulled in, from where) is worth matching.

### Two international reference points
Neither files an Indian return, but both set the bar for what "guided" actually looks like at scale. **TurboTax**'s specific advantage isn't friendliness — it's *traceability*: screens that show exactly what was imported, flag which transactions need attention, and state plainly where each number lands on the official form. **H&R Block** is the counter-example: solid for ordinary cases, but its guidance thins out fast the moment a return has anything unusual — the same failure mode Taxify's schedule editors have for AMT, DTAA relief, or transfer pricing.

> The lesson isn't "copy ClearTax" or "copy Winman." It's that the cloud tier solved import-trust and first-time guidance, the desktop tier solved professional-volume density, and no single player in this market has both. That gap is exactly where Taxify should sit.

---

## 5. A design system worth keeping

Before any income-head gets redesigned, it needs somewhere real to stand.

### Colour
Keep the existing navy/gold identity — it's genuinely well chosen, it's just underused. Extend it with the semantic tokens the audit found missing: a dedicated "computed field" surface, and a real three-tier severity system, so the app stops inventing a new red or green every time a file needs one.

| Token | Value | Role |
|---|---|---|
| `--navy` | `#0B1929` | Primary brand / headings |
| `--gold` | `#C9943A` | Accent / primary CTA |
| `--bg` | `#F7F7F5` | Page ground |
| `--text-primary` | `#0F1E2D` | Body text |
| `--surface-computed` *(new)* | `#FDF3E0` | The one and only "field is locked/computed" treatment |
| `--success` *(the only green)* | `#15803D` | |
| `--danger` *(the only red)* | `#B91C1C` | |
| `--warning` *(the only amber)* | `#eb6767` | |

**Rule of application:** every colour a form component uses comes from this token list. No component file defines its own hex value for anything a token already covers — that single rule, enforced in code review, would have prevented roughly forty of the findings in Section 3.

### Type
Keep DM Sans for interface text and Playfair Display for the occasional editorial moment (the dashboard greeting is a good use of it). Add one deliberate role the current system lacks: a monospace treatment specifically for CBDT codes, ISINs, TAN/PAN/GSTIN values and section numbers, so a CA's eye learns to distinguish "a value you type verbatim" from "a label you read."

### The component inventory
Nine primitives cover essentially every pattern the audit found reinvented:

| Component | Replaces |
|---|---|
| `<FormField>` | The 8+ hand-rolled "label + input + help + error" implementations across Employer, HouseProperty, PersonalInfo, Deductions, ExemptIncome, ScheduleOS, ITR2Schedules. |
| `<MoneyInput>` | Every raw `<input type="number">` handling rupees by hand; centralises Indian digit grouping, the string-vs-number coercion that caused the 10× bug, and one visual state for "locked/computed." |
| `<ComboSelect>` | Plain `<select>` for anything over ~15 options — the 280-option 44AD nature-of-business list, the 70-option exempt-income subcategory list, the 60-option TDS section dropdown. |
| `<EntryCard>` | The six independent "collapsible repeatable row" implementations; derives its own title from the row's own data instead of defaulting to "Entry #N." |
| `<Section>` (accordion) | The ad hoc section-heading patterns in Capital Gains, Personal Info, and Salary; ships with a collapsed-state running total. |
| `<Stepper>` | Generalises `ITR3BusinessWorkspace`'s five-step wizard into a reusable pattern for any schedule complex enough to need one. |
| `<StatusTag>` | The five unrelated "field is locked" treatments and the parallel schedule-status colour system invented inside `ITRComputationPage.tsx`. |
| `<EmptyState>` / `<LoadingRow>` | Already exist, unused. Wire them in everywhere a list can be empty or a computation can be pending. |
| `<HelpNote>` | A standard inline-help affordance for AMT, DTAA relief, pass-through income, gift exemptions, transfer pricing. |

---

## 6. The blueprint: five income heads, rebuilt

Every proposal below assumes the design system in Section 5 already exists. Capital Gains and Business/Profession get the deepest treatment, both because the product owner asked for it and because the audit found the most to fix there — but none of the five heads escape the same fourteen root causes, so each gets a real plan.

### 6.1 — Salary income (`Schedule S`)

*Currently: `EmployerEntryManager.tsx` — 839 lines, 8–11 flat sections per employer.*

This is, by the audit's own account, the best-token-adhering income-head file in the app — it mostly does the right thing already. The fix here isn't rescue, it's discipline: collapse it, name its rows properly, and delete the stray hardcoded colours (a pure-black card border, a rogue `#16a34a` add-button that should be the one shared green) that snuck past an otherwise careful implementation.

**Proposed structure per employer, as a 4-step accordion:**
1. **Employer** — Name, TAN, category; the card title updates live as soon as a name is typed.
2. **Pay components** — Basic/DA/allowances, collapsed by default once totalled.
3. **Exemptions** — HRA, LTA, retirement benefits, each its own collapsed sub-section, expanded only if claimed.
4. **TDS & reconciliation** — Against Form 16/26AS, surfaced with a live match indicator.

Concretely: replace the eight-section flat scroll with four `<Section>` accordions per employer, each showing its own running subtotal collapsed. Fix the render-time `seq` counter (currently mutated during render, flagged by React's own linter) by deriving section numbers from a stable list instead of a closure. Delete the unused `taxRegime` prop and `totalSalaryTDS` calculation, or restore whatever summary card they were meant to feed.

### 6.2 — House property (`Schedule HP`)

*Currently: `HousePropertyEntryManager.tsx` — densely minified, near-zero help text.*

The smallest fix in scope, and the most damaging in tone: the one visible field label in the current implementation reads **"House Property Serial Number (HPSNo) \*"** — a raw CBDT abbreviation left inside a user-facing label with the parenthetical practically apologising for it.

| Before | After |
|---|---|
| `House Property — HPSNo 2` | `12, Lake View Apartments — Let out` |

Restructure into one `<EntryCard>` per property, titled by address (or "Self-occupied" / "Let out" when no address exists yet) rather than a serial number. Give the computed-income block its own `--surface-computed` treatment instead of a near-invisible tint that currently looks almost identical to an editable field. Add one line of inline help on the 30%-standard-deduction and co-ownership-share rules — both genuinely non-obvious and currently unexplained anywhere in the form.

### 6.3 — Capital gains (`Schedule CG`)

*Currently: `CapitalGainsEntryManager.tsx` — ~20 CBDT sections, one continuous scroll, shared across four ITR forms.*

This is the schedule the product owner named first, and the audit confirms why: it's a single 438-line file rendering every one of Schedule CG's roughly twenty official sub-schedules — A1 through A6, B1 through B9, Schedule 112A, Schedule 115AD, VDA, deduction claims, quarterly accrual, the loss set-off matrix — in one uninterrupted vertical scroll, for every ITR form, merely dimming (not hiding) whichever sections don't apply. A CA filing a simple listed-equity return still scrolls past all twenty sections to get anywhere.

The fix isn't more sections. It's asking the one question that actually organises how a CA thinks about capital gains — *what kind of asset was this* — before showing any CBDT machinery at all.

```
What did you sell?
├── Listed shares / equity funds   → 111A / 112A auto-classified by holding period
├── Land or building               → Cost, improvement, section 50C, transferee detail
├── Unlisted shares / NRI securities → Section code picked from your answer, not a dropdown
├── Virtual digital assets         → Business or capital, asked once
└── Slump sale / other assets
        ↓
   Review & deductions → Schedule CG, assembled
```

**Five concrete changes:**

1. **An asset-type question first.** "What did you sell?" with five plain-language options (listed shares/funds, land or building, unlisted shares, virtual digital assets, other) replaces showing all twenty CBDT buckets up front. The holding-period/section classification (111A vs. 112A, short-term vs. long-term) is derived from the dates the CA enters, not chosen from a jargon dropdown like *"115AD(1)(b)(ii) proviso."*
2. **Rows named by the asset, not the index.** A scrip transaction titles itself by company name and ISIN once entered; a property sale titles itself by address. "Entry #3" never appears.
3. **A live overview that updates as you go**, not a static summary table shown once at the top — the existing "Gains overview" table is a good instinct, badly placed; move it to a persistent sidebar or sticky footer that updates per entry.
4. **One field-list source of truth.** Today, the exemption-section dropdown (54/54B/54F/54EC) is hand-duplicated in three separate places in the file with no shared list — a correctness risk as much as a consistency one. Collapse to one canonical list, filtered by form/asset-type where genuinely needed.
5. **DTAA, buy-back losses, and unutilised-deposit sections become their own collapsed steps**, shown only once the CA indicates they apply — not permanently visible, dimmed, disabled rows every filer scrolls past.

| Before — dropdown value | After — derived, not chosen |
|---|---|
| `A3. Equity shares / equity-oriented funds with STT (111A / 115AD(1)(ii) proviso)` | Listed shares, sold within 12 months, STT paid → taxed under section 111A *(auto-detected from your dates)* |

### 6.4 — Business & profession (`Schedule BP` / `Part A-P&L` / `Part A-BS`)

*Currently: 8 interlocking components, 830–393 lines each, two competing renderers for the same schedule.*

This is the largest and most structurally broken area in the app, and the fix has to happen in a specific order, because right now the problem isn't primarily visual — it's architectural. Two independent systems can produce Schedule BP: a generic JSON-schema walker (`ITR3BusinessCoreManager.tsx`) that mechanically renders whatever the CBDT schema happens to contain, and a hand-built editor (`ITR3ScheduleBPEditor.tsx`) that's the one actually wired into filing today. They can drift apart silently. **Before any redesign work starts here, that duplication needs a decision**: retire the schema-walker's Schedule BP path entirely, keep only the hand-built one, and do the same audit for the near-identical ITR-3/ITR-4 presumptive-income editors (one has a real money-safety fix the other lacks).

Once there's one editor per schedule instead of two, the redesign follows the same shape that already works elsewhere in this exact codebase — `ITR3BusinessWorkspace.tsx`'s five-step flow is genuinely good and should become the template, extended one level deeper:

```
1. Profile          → Audit status, nature of business, 44AD/ADA/AE eligibility
2. Books & accounts  → Trading + Manufacturing accounts, if maintained
3. Profit & loss     → Grouped by real accounting sections, not schema order
4. Adjustments       → Disallowances, addbacks — only the ones that apply
5. Supporting        → Depreciation, 80-IA family, GST, transfer pricing — checklist-gated
6. Review            → Schedule BP, assembled
```

**Three changes carry almost all the weight:**

1. **A real label glossary for the 377 fields across Part A-P&L, Part A-BS, and Schedule BP.** This is the single highest-leverage fix in the entire audit. Today these labels are produced by mechanically splitting camelCase CBDT field names — `AmtDebPLDisallowUs36` becomes "Amt Deb P L Disallow Us36." Writing the ~370 real English labels this data already has official descriptions for (most are standard accounting line items: "Provision for bad and doubtful debts," "Interest paid to a related party disallowed under section 40A(2)(b)") transforms this section without touching a single pixel of layout.
2. **Group by accounting concept, not schema nesting.** Today's grouping in `ITR3ScheduleBPEditor.tsx` is a substring-match heuristic on the field's own path name — a field only lands in "final business totals" if its name happens to contain "Tot," "Balance," or "IncomeOf." A CA thinks in terms of "depreciation add-backs," "disallowed personal expenses," "presumptive vs. regular computation" — group the 131 Schedule BP fields that way instead, with each group collapsed by default and showing its own subtotal.
3. **Consolidate the four independent "nature of business" colour palettes and the 280-option flat dropdown** into one searchable `<ComboSelect>` — nobody should scroll a 280-item alphabetically-inconsistent list to find "Social Media Influencer."

| Before | After |
|---|---|
| `AmtDebPLDisallowUs36 — ₹0`<br>`ScheduleBP.PARTA_OI.AmtDisallUs36.StkInsurPrem` | Insurance premium on stock, disallowed<br>*Section 36 — auto-carries from Part A-P&L* |

### 6.5 — Other sources (`Schedule OS`)

*Currently: one good consolidated workspace, five smaller duplicate managers competing with it.*

The unusual thing about this income head is that the audit's best file and worst files both live here. `ScheduleOSWorkspace.tsx` is the second-best-organised file in the entire app — consistent accordions, a genuinely good progressive-disclosure pattern for five-period interest breakdowns, and a race-horse-activity section that correctly shows the real section 58/59 computation chain instead of a generic field grid. Sitting alongside it are five standalone managers — `DividendEntryManager`, `InterestEntryManager`, `GiftPropertyManager`, `WinningsManager`, `FamilyPensionManager` — that duplicate subsets of the same functionality less completely, with independently-invented colours, and in two confirmed cases, wrong section-code labels.

The fix here is almost entirely subtractive. Confirm with engineering whether the five standalone managers are still reachable from any live route; if they're legacy (the evidence strongly suggests they are — `ScheduleOSWorkspace` is newer and more complete), delete them rather than redesign them. What remains is mostly a polish pass on an already-good file:

- Stop concatenating raw CBDT codes into dropdown labels — *"DividendOthThan22e — Dividend other than deemed dividend u/s 2(22)(e)"* should read as the plain-language half only, with the code available on hover or in a details view.
- Extend the file's own good "five-period breakup" collapse pattern to the DTAA and unexplained-income sections, which currently don't get it.
- Replace the generic "Section / nature \*" label — reused for five structurally different pickers across the file — with a label specific to what's actually being picked each time.

---

## 7. Delivery roadmap

Four phases, ordered by leverage-to-risk ratio — the cheapest, safest wins first, the architectural decisions before the visual ones, and Capital Gains/Business/Profession last precisely because they're where the wrong order would hurt most.

### Phase 0 — Foundations
Build the nine-component library and the extended token set from Section 5 in isolation, against the existing screens, changing no visible behaviour yet. Fix the money-type-safety gap (root cause 7) here — before any relabeling work, since a mislabeled-but-correct field is a UX bug and a correctly-labeled-but-wrong field is a liability.

### Phase 1 — Decide the duplicates
Resolve every confirmed duplicate-implementation finding (root cause 6) with a product decision, not a redesign: one Schedule BP renderer, one presumptive-income editor shared between ITR-3/ITR-4, one Other-Sources implementation, one modal pattern. Retire the ten orphaned pages or wire them in — either way, stop carrying dead code into the new design. Resync `scheduleRegistry.ts` against what actually exists.

### Phase 2 — Salary, House Property, Other Sources
Migrate onto the new component library in ascending order of current quality — Other Sources' consolidation first, then Salary's accordion pass, then House Property's rename-and-restyle. These are lower-risk proving grounds for the new system before it meets Capital Gains and Business/Profession.

### Phase 3 — Capital Gains & Business/Profession
The two flagged areas, last and most carefully. Capital Gains gets the asset-type-first restructure; Business/Profession gets the extended wizard plus the 377-field label glossary, which can be authored in parallel with the component work since it's pure content, not code.

---

## Appendix — Evidence index

The full file list behind every finding above, for whoever picks this up next.

**Capital Gains & Business/Profession (12 files):**
`CapitalGainsEntryManager.tsx`, `BusinessProfessionEntryManager.tsx`, `business/ITR3BusinessCoreManager.tsx`, `business/ITR3BusinessAuxiliaryManager.tsx`, `business/ITR3BusinessWorkspace.tsx`, `business/ITR3PresumptiveManager.tsx`, `business/ITR3ScheduleBPEditor.tsx`, `business/ITR4ScheduleBPManager.tsx`, `business/ITR4ScheduleBPData.ts`, `domain/itr3ScheduleBP.ts`, `domain/returns/scheduleBpAdapter.ts`, `domain/itr3Depreciation.ts`

**The ITR-3 schedule-editor family (21 files):**
`ITR3AMTEditor.tsx`, `ITR3AlFaEsopEditor.tsx`, `ITR3CYLABFLAEditor.tsx`, `ITR3ForeignSchedulesEditor.tsx`, `ITR3PTIEditor.tsx`, `ITR3PartAFinancialEditor.tsx`, `ITR3PartAOIEditor.tsx`, `ITR3PartAQDEditor.tsx`, `ITR3SpecialSchedulesEditor.tsx`, `ITR3TPSAEditor.tsx`, `ITR3TaxPaymentEditor.tsx`, `ITR3PersonalInfoPage.tsx`, `domain/itr3AlFaEsop.ts`, `domain/itr3ForeignSchedules.ts`, `domain/itr3PartAFinancials.ts`, `domain/itr3PartAOI.ts`, `domain/itr3PartAQD.ts`, `domain/itr3Pti.ts`, `domain/itr3SpecialSchedules.ts`, `domain/itr3TPSA.ts`, `domain/returns/itr3LossSetoff.ts`

**Other income-head managers & shared components (31 files):**
`EmployerEntryManager.tsx`, `HousePropertyEntryManager.tsx`, `PersonalInfoTab.tsx`, `BankAccountManager.tsx`, `DeductionLoanManager.tsx`, `DonationEntryManager.tsx`, `Section80CManager.tsx`, `Section80DManager.tsx`, `EmployerReconciliationModal.tsx`, `ImportConfirmationModal.tsx`, `IndianNumberInput.tsx`, `PortalProgressCircle.tsx`, `ProtectedRoute.tsx`, `StatusPill.tsx`, `deductions/DeductionsWorkspace.tsx`, `dividend/DividendEntryManager.tsx`, `exemptincome/ExemptIncomeWorkspace.tsx`, `familyPension/FamilyPensionManager.tsx`, `gifts/GiftPropertyManager.tsx`, `interest/InterestEntryManager.tsx`, `itr2/ITR2SchedulesWorkspace.tsx`, `othersources/ScheduleOSWorkspace.tsx`, `winnings/WinningsManager.tsx`, `ui/Badge.tsx`, `ui/CollapsibleWarning.tsx`, `ui/EmptyState.tsx`, `ui/SkeletonRow.tsx`, `ui/Spinner.tsx`, `layout/AppLayout.tsx`, `layout/Sidebar.tsx`, `layout/Topbar.tsx`

**Pages & navigation shell (20 files):**
`ITRComputationPage.tsx`, `ITRComputationTabs.tsx`, `AdvancedTaxPage.tsx`, `ClientsPage.tsx`/`.css`, `DashboardPage.tsx`, `RegisterPage.tsx`, `LoginPage.tsx`/`.css`, `LandingPage.tsx`/`.css`, `AccountingPage.tsx`, `BillingPage.tsx`, `CalendarPage.tsx`, `CommunicationPage.tsx`, `JobsPage.tsx`, `NoticesPage.tsx`, `ReconciliationPage.tsx`, `ReportsPage.tsx`, `SyncPage.tsx`, `TasksPage.tsx`, `App.css`

**The domain/logic layer (53 files):**
`domain/scheduleRegistry.ts`, `domain/amt.ts`, `domain/eligibility.ts`, `domain/itr3AlFaEsop.ts`, `domain/itr3CapitalGainsAccrual.ts`, `domain/itr3CoverageManifest.ts`, `domain/itr3Depreciation.ts`, `domain/itr3ForeignSchedules.ts`, `domain/itr3PartABS.ts`, `domain/itr3PartAFinancials.ts`, `domain/itr3PartAOI.ts`, `domain/itr3PartAQD.ts`, `domain/itr3Pti.ts`, `domain/itr3Schedule80Coverage.ts`, `domain/itr3ScheduleBP.ts`, `domain/itr3ScheduleUD.ts`, `domain/itr3SpecialSchedules.ts`, `domain/itr3TPSA.ts`, `domain/scheduleOSCoverage.ts`, `domain/returns/*.ts` (16 files), `utils/*.ts` (11 files), `types/*.ts` (4 files), `hooks/useSeo.ts`, `contexts/AYContext.tsx`, `constants/itdCountryCodes.ts`
