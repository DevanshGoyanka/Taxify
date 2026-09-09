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
>
> **Update (2026-09-08): a full form-order re-audit — reading the actual ITR-2 form PDF part by
> part and cross-referencing every field against the official schema, independent of this
> document's own prior findings list — found ten new CRITICAL findings the "all P0 closed" claims
> above did not anticipate**, several in schedules the prior cycle marked fully fixed (Schedule CG/
> 115AD, Schedule OS) or never independently re-examined at all (Schedule VIA and its six detail
> schedules, Schedule AMTC, Part B-TTI, Verification). See the "Update (2026-09-08)" blockquote
> under §21 Final assessment for the full itemized list — the short version: Chapter VI-A
> deductions (§8.0/§8.0a, claimed by most real taxpayers) and Schedule VIA are effectively
> non-functional at the schema level, and this is a bigger production blocker than anything the
> prior "all P0 closed" framing identified. Every new finding is a fresh subsection dated
> "2026-09-08" within its schedule's own existing section, cross-referencing rather than
> restating prior findings.
>
> **Update (2026-09-09): two of the ten new CRITICAL findings are now fixed and verified — Schedule
> VIA (§8.0) and Schedule 115AD (§3.10), the two explicitly requested for this pass.** Schedule VIA
> now populates every named per-section field (previously only a `TotalChapVIADeductions` scalar
> plus a non-existent extra key), closing what was likely the highest-reach single finding in this
> document given how close to universal Chapter VI-A claims are. Schedule 115AD is now built and
> registered as its own top-level schedule, correctly separated from Schedule112A by the assessee's
> FII/FPI status. Both fixes are regression-tested and `git stash`-verified against pre-fix code;
> see each section's own "Fix status (2026-09-09)" blockquote for full evidence. **Still open, not
> attempted in this pass**: §8.0a (the six dedicated Chapter VI-A detail schedules — 80D/80G/80GGA/
> 80GGC/80DD/80U — explicitly scoped out, a materially larger body of work than the single-function
> Schedule VIA fix) and the eight remaining new CRITICAL findings from the 2026-09-08 pass
> (`GrossIncChrgblTaxAtAppRate`, `ScheduleAMTCDtls` field names, `PropertyOwnerOther`,
> `AssetOutIndiaFlag`, `"GrossTaxPayable"`, `AssesseeVerPAN`'s HUF-incompatible pattern, Schedule
> CG's Table E/F, Part B-TI's STCG bucket swap). The overall classification from the 2026-09-08
> update stands: not yet production-ready.
>
> **Update (2026-09-09, same day, second pass): `AssetOutIndiaFlag` and `GrossTaxPayable` are also
> now fixed and verified — both in Part B-TTI.** `AssetOutIndiaFlag` now tracks real Schedule FA
> presence instead of a hardcoded `"NO"`. **The `GrossTaxPayable` finding itself was wrong and is
> retracted** — the field is real and schema-required (not a nonexistent key as originally
> claimed); the actual bug was that it was hardcoded to `0` rather than `max(item 1d,
> GrossTaxLiability)`, now fixed, scoped to stay correct without also solving the separate
> `TaxPayDeemedTotIncUs115JC`/AMT-linkage gap. See both sections' "Fix status (2026-09-09)"
> blockquotes (the `GrossTaxPayable` one includes the retraction in full) for complete evidence.
> Four of the ten new CRITICAL findings are now closed; six remain, plus §8.0a.
>
> **Update (2026-09-09, third pass): `GrossIncChrgblTaxAtAppRate` (§3.4a, Schedule OS's own
> headline total) is also fixed and verified.** Five of the ten new CRITICAL findings are now
> closed. Found (documented, not fixed — out of scope for this pass) a new CRITICAL-candidate bug
> while writing the regression test: `os_other_income_entries` ("any other income") is disclosed in
> Schedule OS but never actually taxed — the calculator never sums it into
> `other_sources_income`. See §3.4a's fix note for evidence.
>
> **Update (2026-09-09, fourth pass): `ScheduleAMTCDtls` (§9.3a) is also fixed and verified — six
> of the ten new CRITICAL findings now closed.** Beyond the field-naming/`TotSetOffEys` fix, found
> and fixed a second, more severe, previously-undocumented bug in the same function: multi-year AMT
> credit utilization applied the full current-year offset capacity independently to every row
> instead of tracking consumption across rows (FIFO), over-crediting utilization whenever more than
> one year of brought-forward credit existed. See §9.3a's fix note for full evidence. Four new
> CRITICAL findings remain open, plus §8.0a and the `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, fifth pass): `PropertyOwnerOther` (§6.4) is also fixed and verified — seven
> of the ten new CRITICAL findings now closed.** Fixed exactly as remediated (new field + a
> `validate_property_owner_other` model validator mirroring the existing `co_owned`/
> `co_owner_details` precedent). Three new CRITICAL findings remain open, plus §8.0a and the
> `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, sixth pass): `AssesseeVerPAN` (§18b.1) is also fixed and verified — eight
> of the ten new CRITICAL findings now closed.** Fixed exactly as remediated: a new `karta_pan`
> field on `ITR2FilingProfile`, required by a model validator whenever `assessee_status == HUF`,
> selected in `_verification_block()` in place of the HUF's own (schema-incompatible) `pan`. Wired
> end-to-end including a new conditional "Karta's PAN" frontend field. Two new CRITICAL findings
> remain open — Schedule CG's Table E/F hardcoded zero, and Part B-TI's STCG bucket swap — plus
> §8.0a and the `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, seventh pass): Part B-TI's STCG bucket swap (§18a.1) is also fixed and
> verified — nine of the ten new CRITICAL findings now closed.** Fixed exactly as remediated:
> `_partb_ti()` now branches on `is_fii_fpi` the same way `_schedule_cg()`/`_schedule_115ad()`
> already do, so `ShortTerm20Per` always holds the true 111A bucket, `ShortTermAppRate` holds the
> ordinary slab-rate bucket (zero for FII/FPI), and `ShortTerm30Per` holds the FII-only flat-30%
> bucket (zero otherwise). One new CRITICAL finding remains open — Schedule CG's Table E/F
> hardcoded zero (§3.9) — plus §8.0a and the `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, eighth pass): Schedule CG's Table E and Table F (§3.9) are also fixed and
> verified — all ten of the ten new CRITICAL findings from the 2026-09-08 form-order re-audit are
> now closed.** Table E (`CurrYrLosses`) required exposing the within-Schedule-CG (section 70)
> intra-head loss set-off matrix `cyla.py` was already computing internally but discarding down to
> aggregate totals — refactored to track and return the full per-source→per-target breakdown
> without changing any existing value (proven order-independent for aggregates; see §3.9's own fix
> note). Table F (`AccruOrRecOfCG`) now buckets real per-transaction gains by transfer-date quarter,
> with a documented, bounded simplification for two aggregate-level refinements (section 50CA
> deeming, section 112A grandfathering) that don't apply per-transaction. **Only §8.0a (six Chapter
> VI-A detail schedules) and the `os_other_income_entries` undertaxation gap remain open** from
> everything tracked in this document's current findings list.
>
> **Update (2026-09-09, ninth pass): §8.0a (the six Chapter VI-A detail schedules — 80D, 80G,
> 80GGA, 80GGC, 80DD, 80U) is also fixed and verified.** All six were built end-to-end by wiring
> `ITR2Input` and `app/engine/calculators/itr2.py` into the SAME shared per-section eligibility
> engine (`app/engine/schedules/deductions/`) ITR-1 already uses in production for these exact
> schedules, then adding six `_schedule_80*()` builder functions to `app/engine/itd/itr2.py`
> adapted from ITR-1's own proven implementation (confirmed field-for-field identical against
> ITR-2's official schema, with two deliberate ITR-2-specific additions: `Form10IAFilingDate`/
> `FormAckNum11A` on Schedule80DD/80U, and HUF-member-dependent support on Schedule80DD). Found
> and fixed a real incidental bug along the way: `is_80dd_severe`/`is_80u_severe` were reading a
> `Chapter6ADeductions` field `_map_deductions()` never populates, silently defaulting every
> taxpayer to non-severe regardless of their real selection. See §8.0a's own fix note for full
> evidence. **The only item remaining open in this entire document is now the
> `os_other_income_entries` undertaxation gap** (§3.4a) — every CRITICAL finding from both the
> original audit and the 2026-09-08 form-order re-audit is closed.
>
> **Update (2026-09-09, tenth pass): the `os_other_income_entries` undertaxation gap (§3.4a) is
> also fixed and verified — every finding tracked anywhere in this document is now closed.**
> `os_other_income_entries` now reaches taxable income via `app/engine/calculators/itr2.py`.
> Investigating the real v2 draft pipeline before shipping that alone surfaced a genuine
> double-taxation risk: the same underlying "any other income" rows were already being summed into
> a separate generic aggregate (`OtherSourcesIncome.other_income`, via the mapper shared with
> ITR-1) that also reaches GTI — fixed by widening the existing MACHINERY_RENT/PASS_THROUGH
> back-out in `app/engine/draft_to_itr2_input.py` to also exclude `os_other_income_entries`'s own
> total, so the two fields partition rather than overlap the same rows. See §3.4a's own fix note
> for full evidence, including why the straightforward one-line fix would have been wrong for real
> taxpayers despite passing a test written the same way the original finding was.
>
> **Update (2026-09-09, Phase 8 re-audit): with every finding this document tracked closed, a full
> independent schema-first re-audit — the standing plan's own local-correctness exit gate — was run
> across the entire pipeline, mirroring the 2026-09-08 pass's proven methodology exactly (split by
> form area, read the official schema/form/CBDT Validation Rules independently, don't trust any
> prior "fixed" claim without re-checking it). It found 26 new findings, roughly half CRITICAL —
> see the new §20 for the complete write-up. The single highest-reach defect found: Schedule
> CYLA's own six capital-gains sub-baskets are unconditionally zero (a `getattr` silently falling
> back on a nonexistent attribute), directly contradicting Schedule BFLA in the very same JSON for
> every ITR-2 return with any STCG/LTCG income — this form's primary use case. Also found: Section
> 112A gain corrupted by double-counted deductions on the *primary* scrip-entry UI (turns real
> gains into fabricated losses); a sibling of the just-fixed `os_other_income_entries` bug
> (`os_pass_through_income`, disclosed but never taxed); `PartB_TTI.NetTaxLiability` holding the
> wrong post-interest quantity (the exact bug class CLAUDE.md documents as already fixed for ITR-1,
> never ported to ITR-2); `ScheduleAMT.DeductionClaimUndrAnySec` wrong on 100% of AMT-applicable
> returns; and five more Chapter VI-A detail schedules (80C/80E/80EE/80EEA/80EEB) with zero
> implementation, in the exact same family §8.0a fixed six of, missed by that finding's own scope.
> **ITR-2 is not production-ready — the classification below is revised accordingly.**
>
> **Update (2026-09-09, Phase 8 fix cycle, first fix): the Schedule CYLA capital-gains-bucket bug
> (§20.3) is fixed and verified — 1 of Phase 8's 26 findings closed.** `_schedule_cyla()` now reads
> the correct per-bucket gross-income figures from `cyla.cg_gross_income` instead of nonexistent
> attributes that silently defaulted to zero. See §20.3's own fix note for full evidence, including
> a new regression test proving Schedule CYLA and Schedule BFLA now agree with each other for the
> same basket (the exact cross-schedule contradiction this finding described). 25 Phase 8 findings
> remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, second fix): the Section 112A double-counted-deduction
> bug (§20.4) is also fixed and verified — 2 of Phase 8's 26 findings closed.** `compute_112a()`
> (`app/engine/schedules/capital_gains.py`, shared with ITR-3) no longer subtracts
> `asset.total_deductions` on top of the cost/expenditure it already subtracts separately — a
> redundant field confirmed (via an existing validator and the schedule builder's own independent
> `TotalDeductions` computation) to have no legitimate role as a compute input at all. A sibling
> instance of the same bug in Table F's own scrip-gain approximation was found and fixed in the
> same pass. See §20.4's own fix note for full evidence, including why the pre-fix behavior was
> "a real gain pays zero tax" rather than the negative figure the finding's own numeric example
> suggested. 24 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, third fix): `os_pass_through_income` (§20.5) is also
> fixed and verified — 3 of Phase 8's 26 findings closed.** The mirror-image half of the earlier
> `os_other_income_entries` fix: `input_data.os_pass_through_income` is now added into
> `r.other_sources_income` in `app/engine/calculators/itr2.py`. No double-counting risk existed here
> (unlike `os_other_income_entries`) since `draft_to_itr2_input.py` already correctly backed this
> field out of the generic aggregate — the calculator simply never read it at all. See §20.5's own
> fix note for full evidence. 23 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, fourth fix): the `InterestGross` self-contradiction
> (§20.5) is also fixed and verified — 4 of Phase 8's 26 findings closed.** `InterestGross`
> (`app/engine/itd/itr2.py`) now sums all nine of its own declared sub-items (savings/FD/refund
> interest, pass-through interest, the four PF-proviso buckets, and "interest from others"), not
> just the first three — and since item 1 (`GrossIncChrgblTaxAtAppRate`) reads `InterestGross`
> directly, it picks up the fix automatically. This closes only the disclosure-formula half of the
> finding; the PF-proviso/NSC/bonds categories' underlying tax still reaches GTI via an untraceable
> generic aggregate rather than a dedicated path — deliberately left open as a distinct follow-up.
> See §20.5's own fix note for full evidence. 22 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, fifth fix): the `ScheduleAMT.DeductionClaimUndrAnySec`
> bug (§20.6) is also fixed and verified — 5 of Phase 8's 26 findings closed.** `_schedule_amt()`
> (`app/engine/itd/itr2.py`) previously read a `total_deductions` attribute that doesn't exist on
> `AMTResult` at all, silently defaulting to 0 on 100% of AMT-applicable returns. Now computed as
> `adjusted_total_income - result.taxable_income`, confirmed exact by tracing `amt.py`'s own
> arithmetic — no change to `amt.py` itself needed. See §20.6's own fix note for full evidence.
> 21 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, sixth fix): the `ScheduleTR1` DTAA/non-DTAA
> double-counting bug (§20.6) is also fixed and verified — 6 of Phase 8's 26 findings closed.**
> `_schedule_tr1()` (`app/engine/itd/itr2.py`) now reads each row's own `relief_section` directly
> instead of re-searching every entry sharing that row's country code — a per-row test instead of a
> per-country one. Caught and fixed an incidental type bug while writing the regression test
> (initializing the running totals from `Decimal` rather than `int` silently produced
> schema-invalid output despite being numerically correct — caught by an existing test failing on
> re-run). See §20.6's own fix note for full evidence. 20 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, seventh fix): the Schedule TDS3 `AadhaarOfBuyerTenant`
> gap (§20.6) is also fixed and verified — 7 of Phase 8's 26 findings closed.** `_schedule_tds3()`
> (`app/engine/itd/itr2.py`) now conditionally includes `AadhaarOfBuyerTenant` from the paired
> `TDS3Entry.tenant_aadhaar` whenever supplied — previously built only from `TDS3FilingDetail`,
> which has no Aadhaar field at all, so the captured value was a dead end regardless of what the
> taxpayer entered. See §20.6's own fix note for full evidence. 19 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, eighth fix): the five missing Chapter VI-A schedules
> (§20.1 — `Schedule80C`/`Schedule80E`/`Schedule80EE`/`Schedule80EEA`/`Schedule80EEB`) are also
> fixed and verified — 8 of Phase 8's 26 findings closed.** The exact same "computed but discarded"
> pattern as §8.0a's own six schedules, missed by that finding's own scope: `ITR2Input` gained the
> five fields, `draft_to_itr2_input.py`/`calculators/itr2.py` now wire them through the same shared
> eligibility engine, and `itd/itr2.py` gained `_schedule_80c()`/`_schedule_deduction_loan()`
> (adapted from ITR-1's own proven, already-generic implementations). Found and fixed an incidental
> gap in `_chapter6a_detail_schedules()`'s own `claimed()` helper along the way: it needed the same
> "80C" combined-key decomposition `_schedule_via()` already applies, or a real 80C claim under the
> common (non-GTI-capped) case would have read as zero. One existing test needed updating to add a
> now-required 80C detail row, matching real CBDT validator behavior. See §20.1's own fix note for
> full evidence. 18 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, ninth fix): all four §20.2 Part B-TI/Part B-TTI CRITICAL
> findings are also fixed and verified — 12 of Phase 8's 26 findings closed.** `PartB_TTI.
> NetTaxLiability` now holds item 12 ("Balance Tax After Relief" = `gross_tax_liability - relief_89
> - relief_90_91`, floored at 0), the exact ITR-1 fix (`itd/itr1.py:628-639`) ported to ITR-2 with
> its extra `relief_90_91` term — distinct from `AggregateTaxInterestLiability` (item 14), which
> correctly keeps reading the calculator's fully-aggregated `net_tax_liability` and needed no
> change. `IntrstPay.TotalIntrstPay` now sums in the 234F late fee and the 234-I fee
> (`FeeFurnish234I`, itself found hardcoded 0 in the same dict despite the calculator already
> computing `result.fees_234i` — fixed alongside so its own sibling total wouldn't silently stop
> cross-footing). `PartB-TI.IncFromOS`'s `IncChargblSplRate`/`FromOwnRaceHorse` are now sourced
> from `_schedule_os()`'s own already-computed `IncChargeableSpecialRates`/`BalanceOwnRaceHorse`
> totals (called a second time from `_partb_ti()`), guaranteeing the CBDT-rule-500-502-mandated
> consistency with Schedule OS by construction rather than by independent re-derivation.
> `IncChargeTaxSplRate111A112`/`IncChargeableTaxSplRates` now both read `si.total_special_rate_income`
> (Schedule SI's own full column-(i) total) instead of a CG-only `post_loss_cg` subset — per the
> form's own caption ("total of column (i) of schedule SI") and CBDT rule 374's explicit text
> ("consistent with **all** the special incomes of Schedule SI"), confirming both fields are meant
> to hold the identical full-SI-total quantity, not just 111A/112/112A(+VDA). Four new regression
> tests in `tests/test_itr2_itd_builder.py`, each confirmed via `git stash` to fail against pre-fix
> code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 684 passed, only
> the same 5 pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated to
> this fix, confirmed still failing identically on pre-fix code too). 14 Phase 8 findings remain
> open.
>
> **Update (2026-09-09, Phase 8 fix cycle, tenth fix): the Schedule CFL current-year-loss
> mislabeling bug (§20.2/§20.3) is also fixed and verified — 13 of Phase 8's 26 findings closed.**
> `_schedule_cfl()` now partitions its flattened carry-forward entries by
> `assessment_year_of_loss == "2026-27"` before summarizing, so `TotalOfBFLossesEarlierYrs` (form
> row ix) covers only genuine brought-forward losses, `CurrentAYloss` (row xi, previously never
> emitted at all) now discloses this year's own fresh unabsorbed loss separately, and
> `TotalLossCFSummary` (row xii) — already correct — is unchanged. See §20.3's own fix note for full
> evidence, including the deliberately-deferred `AdjTotBFLossInBFLA` (row x) gap noted as a forward
> pointer, not fixed. 13 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, eleventh fix): the Schedule HP `ifLetOut` "D"-code bug
> (§20.3) is also fixed and verified — 14 of Phase 8's 26 findings closed.** `_schedule_hp()` now
> emits `ptype` (`property_type.value`) directly instead of collapsing "D" (deemed let out) into
> "L" (let out), matching ITR-1's own builder. No calculator change needed — deemed-let-out already
> gets correct (uncapped) interest treatment via the same code path ordinary let-out uses. See
> §20.3's own fix note for full evidence. 12 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, twelfth fix): the discarded per-employer Section 10
> exemption rows bug is also fixed and verified — 15 of Phase 8's 26 findings closed.**
> `_schedule_s()` now collects `detail.section10_exemption_rows` from every employer and merges it
> into `AllwncExemptUs10Dtls`, instead of computing it into a loop-local variable that was then
> shadowed and discarded. Found and fixed one incidental integrity gap in the same rewrite: the
> frontend's "OTH" catch-all option has no matching official schema code, so it now raises a clear
> error instead of risking schema-invalid JSON. Found, but deliberately left unfixed and newly
> documented as its own finding: six of the nine codes this editor offers (EIC/10(17)/10(14)(i)-or-
> (ii)-"not otherwise entered"/their 115BAC variants) never reduce taxable salary income at all, for
> ITR-1 AND ITR-2 alike (shared `_map_salary()`) — a real over-taxation defect, materially larger in
> scope than this JSON-disclosure fix. See §20.3's own fix note and the new forward-pointer finding
> immediately after it for full evidence. 11 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, thirteenth fix): the EIC/10(17)/10(14)(i)-or-(ii)/
> 115BAC-variant undertaxation gap (§20.3, discovered mid-cycle during the twelfth fix above, not
> part of the original 26-finding tally) is also fixed and verified — the tally stays 15/26 closed,
> 11 remaining, since this finding was never counted in either total.** A new
> `SalaryIncome.other_section10_exempt` field now carries the direct pass-through sum of all six
> previously-dropped codes into `exempt_allowances` (`schedules/salary.py`), fed by
> `_map_salary()` (`draft_to_itr1_input.py`, shared verbatim by ITR-2). Real over-taxation on a
> narrow taxpayer population (judges, MPs/MLAs/MLCs, embassy/foreign-service employees) is now
> corrected for both forms through the one shared code path. See §20.3's own fix note for full
> evidence.
>
> **Update (2026-09-09, Phase 8 fix cycle, fourteenth fix): the `uniform_allowance_exempt` wrong
> Section 10(14) sub-clause bug (§20.3) is also fixed and verified — 16 of Phase 8's 26 findings
> closed.** `_SALARY_EXEMPTION_ROWS` now tags it `"10(14)(i)"` (actual-expenditure-based, matching
> both the official schema's own description and the calculator's own docstring) instead of
> `"10(14)(ii)"` (the fixed-statutory-rate bucket transport/CEA/hostel correctly use). No tax
> effect — disclosure-only. Found, but left unfixed as a forward pointer: ITR-1's own builder takes
> a different, likely also-wrong approach for the same allowance (folds it into CEA's row on an
> incorrect "no separate schema code" premise) — a genuine, separate, ITR-1-only defect, out of
> scope here. See §20.3's own fix note for full evidence. 10 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, fifteenth fix): the `IncomeNotified89AType` wrong
> field-names bug (§20.3, dormant/latent) is also fixed and verified — 17 of Phase 8's 26 findings
> closed.** `EmployerFilingDetail.income_notified_89a_country_rows` is now typed
> `List[OS89ACountryEntry]` (reusing Schedule OS's own identical `NOT89AType` model) instead of a
> raw dict list, `filing_gateway_v2.py` now builds proper entries from the frontend's raw shape, and
> `_schedule_s()` now emits the official `NOT89ACountrycode`/`NOT89AAmount` keys instead of passing
> the frontend's own field names through unchanged. Fixed proactively despite zero current impact
> (no frontend UI exists yet) — per this document's own stated rationale for latent findings, fixing
> now is cheaper than re-discovering it later. See §20.3's own fix note for full evidence. 9 Phase 8
> findings remain open.
>
> **Update (2026-09-09): the remaining "untraceable channel" half of the `InterestGross` finding
> (§20.5, fourth fix above) is also fixed and verified — tally unchanged at 17/26 closed, 9
> remaining, since this was the deliberately-deferred second half of a finding already counted
> closed, not a new one.** The four PF-proviso interest fields and `os_interest_from_others` are now
> explicitly added to `r.other_sources_income` in `calculators/itr2.py`, with a matching back-out
> added to `draft_to_itr2_input.py`'s existing generic-aggregate handling — the same
> back-out-and-add-back pattern already used for `os_pass_through_income`/`os_machinery_plant_rent`/
> `os_other_income_entries`. GTI inclusion for this income is now traceable and independently
> verifiable, not riding along invisibly inside a generic residual. See §20.5's own fix note for
> full evidence.
>
> **Update (2026-09-09, Phase 8 fix cycle, sixteenth fix): the `IncChargeableSpecialRates` 2c/2e
> incompleteness gap (§20.5) is partially fixed and verified — 18 of Phase 8's 26 findings closed.**
> 2c (accumulated-PF income, `TaxAccumulatedBalRecPF.TotalIncomeBenefit`) now folds into the item-2
> sum — a pure disclosure-arithmetic fix, no tax-computation change, since this income already
> reached GTI correctly. 2e (`PassThrIncOSChrgblSplRate`) is now included in the formula (as `+ 0`)
> but its own value stays hardcoded `0` — deliberately deferred, matching the severity note's own
> "lower-priority structural limitation" framing: no dispatch path for OS-head special-rate PTI
> exists anywhere in this engine, and building one is a genuine new-feature design (section
> 115UA(2)/115UB(1) proviso rate-inheritance, no existing `section`-code convention to key off), not
> a bug fix. See §20.5's own fix note for full evidence. 8 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, seventeenth fix): the SchedulePTI 111A/112A
> misclassification bug (§20.5) is also fixed and verified — 19 of Phase 8's 26 findings closed.**
> `_schedule_pti()` now routes each entry's amount to `STCG_Sec111A`/`LTCG_Sec112A` or
> `STCG_Others`/`LTCG_Others` using the identical classification the calculator's own PTI dispatch
> loop already taxes it under — Schedule PTI and Schedule SI can no longer disagree about which
> bucket the same income belongs in. Disclosure-only; no tax effect. See §20.5's own fix note for
> full evidence. 7 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, eighteenth fix): the ScheduleEI `IncNotChrgblToTax`/
> `TotalExemptInc` arithmetic bug (§20.5) is also fixed and verified — 20 of Phase 8's 26 findings
> closed.** Item 4 (`IncNotChrgblToTax`) now correctly sums the (currently always-empty)
> `IncNotChrgblAsPerDTAADtls` detail array instead of duplicating item 1; item 6 (`TotalExemptInc`)
> now sums all five declared items (1+2+3+4+5) per the form's own formula. Caught and fixed a
> genuine `sum(..., 0)`-returns-`int`-not-`Decimal` bug in the same rewrite, which would have
> crashed `_to_rupees()`. Disclosure-only; no tax effect. See §20.5's own fix note for full
> evidence. 6 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, nineteenth fix): the two remaining silently-dropped
> Schedule EI/OS data points (§20.5) are also fixed and verified — 21 of Phase 8's 26 findings
> closed.** `ExemptIncome.other_description` now reaches `ScheduleEI.OthersInc.OthersIncDtls`
> (previously hardcoded `[]`); the per-assessment-year accumulated-PF breakdown now reaches
> `ScheduleOS.TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls` via a new `OSAccumulatedPFEntry`
> field/model, instead of being collapsed to aggregate totals before ever reaching `ITR2Input`.
> Completeness gaps only — aggregate totals/tax were already correct in both cases. See §20.5's own
> fix note for full evidence. 5 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, twentieth fix): the `EquityMFonSTT` one-row-per-
> transaction bug (§20.4, CRITICAL, filing-blocking) is also fixed and verified — 22 of Phase 8's
> 26 findings closed.** `_schedule_cg()` now aggregates every matching 111A transaction into a
> single row instead of one row each — the schema's `EquityOrUnitSec94TypeMFonSTT` sub-type has no
> scrip identifier and is aggregate-only, capped at `maxItems: 2`, so any taxpayer with 3+ STT-paid
> equity/MF STCG transactions (a routine case for retail equity investors) previously produced
> outright schema-invalid, `validateItr`-rejected JSON. Found and fixed an incidental bug in the
> same rewrite: `BalanceCG`/`CapgainonAssets` previously omitted `improvement_cost` from the
> subtraction despite the sibling `DeductSec48.TotalDedn` already including it. See §20.4's own fix
> note for full evidence. 4 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, twenty-first fix): the Schedule 112A/115AD
> `LTCGBeforelowerB1B2{suffix}` aggregate-vs-rows mismatch (§20.4) is also fixed and verified — 23 of
> Phase 8's 26 findings closed.** `_112a_style_schedule()` now sums the rows' own already-clamped
> `LTCGBeforelowerB1B2` values for the aggregate, instead of independently recomputing
> `max(0, total_sale - total_cost)` from bucket totals — the same "sum the rows, not the bucket"
> pattern `Balance{suffix}` already used correctly nearby. Disclosure-only; the tax-relevant
> `Balance{suffix}`/`TotalBalance{suffix}` fields were already correct. See §20.4's own fix note for
> full evidence. 3 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, twenty-second fix): Table F's missing VDA accrual
> timing (§20.4) is also fixed and verified — 24 of Phase 8's 26 findings closed.** `_accrued_cg()`
> now buckets each VDA transaction's income into `VDATrnsfGainsUnder30Per` by transfer-date quarter,
> reusing `_schedule_vda()`'s own income-derivation formula and the same quarter-bucketing machinery
> every other real category in this table already uses. See §20.4's own fix note for full evidence.
> 2 Phase 8 findings remain open.
>
> **Update (2026-09-09, Phase 8 fix cycle, twenty-third fix): both remaining §20.6 input-validation
> gaps are also fixed and verified — 25 of Phase 8's 26 findings closed.**
> `ESOPDeferralInput.dpiit_registration_number` now enforces the official `DIPP[0-9]{3,5}` pattern.
> `TDS2Entry.head_of_income` is now a proper `Literal["HP", "CG", "OS", "EI", "NA"]` — re-verified
> against the schema first: the finding's cited "correctly Literal-typed sibling on `TDS3Entry`" is
> actually dead code for this purpose (`_schedule_tds3()` sources `HeadOfIncome` from
> `TDS3FilingDetail` instead), and TDS2's own real enum includes a fifth value (`NA`) TDS3's
> doesn't. See §20.6's own fix note for full evidence. Only one Phase 8 finding remains open: the
> deliberately-deferred `PassThrIncOSChrgblSplRate` (2e) structural gap from §20.5 (no PTI-
> special-rate-OS mapper exists anywhere in this engine — a genuine new-feature design, not a bug
> fix, per that finding's own fix note).
>
> **Update (2026-09-09, Phase 8 fix cycle, twenty-fourth and final fix): `PassThrIncOSChrgblSplRate`
> (2e, §20.5) is also fixed and verified — 26 of Phase 8's 26 findings closed. The Phase 8 re-audit
> cycle is complete.** A new `PTI_OS_SPECIAL_RATE_SECTIONS` constant and a matching dispatch branch
> in the calculator's own PTI loop (which already had three ghost-imported, never-used rate
> functions hinting this was originally planned and left unfinished) now routes an OS-head Schedule
> PTI entry to Schedule SI when its `section` retains a special-rate character
> (115BB/115BBE/115BBF/115BBG/115BBJ/115BBA/111) — deliberately narrower than the full
> `_OS_HEAD_SI_SECTIONS` set, excluding the NRI 115A-family/115E codes that don't plausibly describe
> a pass-through fund's own underlying income. `_schedule_os()` now computes the matching disclosure
> total from the identical constant, single source of truth. See §20.5's own fix note for full
> evidence.

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

## 3.9 Full form-order re-audit (2026-09-08) — Schedule CG's Tables E and F are entirely stubbed

Cross-referenced Schedule CG (form pp. 42-51) against schema `ScheduleCGFor23` and its
`CurrYrLosses`/`AccruOrRecOfCG` sub-blocks, then the current `app/engine/itd/itr2.py::_schedule_cg()`
(lines 1266-1444) in full. §3.1-§3.3's fixes (Schedule 112A as a real schedule, full category
mapping, VDA head-classification) are all confirmed still present and correct in the current code
— no regression. This pass found two structural gaps neither §3.1-§3.3 nor any other section of
this document currently covers: the schedule's own **Table E** (loss set-off) and **Table F**
(quarterly accrual) are both unconditionally stubbed to zero, regardless of real underlying data.

### New finding — Table E ("item E — Set-off of current year capital losses with current year capital gains", `CurrYrLosses` in JSON) is hardcoded to all-zero

**Evidence:** `_schedule_cg()`'s return value (`itd/itr2.py:1429-1439`) hardcodes every field of
`InLossSetOff`/`InStcg20Per`/`InStcg30Per`/`InStcgAppRate`/`InStcgDTAARate`/`InLtcg12_5Per`/
`InLtcgDTAARate`/`TotLossSetOff`/`LossRemainSetOff` to `0`, unconditionally — none of these keys
read from `result.schedules["cg"]` or any other computed value. This is the official form's Table
E (form p. 49) — the within-Schedule-CG loss-set-off matrix (e.g. a current-year short-term
capital loss on one asset netted against a current-year long-term gain on another, entirely
distinct from Schedule CYLA's cross-*head* set-off). The official form's own Part B-TI explicitly
names Table E's own output column as the *source* for each capital-gains rate bucket — "Short-term
chargeable @ 20% **(8ii of item E of schedule CG)**", "...@ 30% (8iii of item E...)", etc. (form
p. 67-68) — so a fully-zeroed Table E is a visible, checkable inconsistency against the same
schedule's own non-zero `TotalSTCG`/`TotalLTCG` whenever a taxpayer actually had a within-CG-head
loss to set off.

**Correctness note (not a computation bug):** traced where Part B-TI's own capital-gains figures
actually come from — `_partb_ti()` (`itd/itr2.py:2580`) reads `result.schedules["post_loss_cg"]`,
the calculator's own independently-computed post-loss figures, **not** anything from Schedule CG's
own JSON. So the *actual filed tax liability figures are unaffected* by Table E being zeroed —
this is a pure disclosure-completeness gap in Schedule CG's own presentation, not a wrong-tax risk,
consistent with this document's established practice of distinguishing "wrong number" bugs from
"missing disclosure" bugs.

**Impact:** every ITR-2 return with any current-year capital loss offsetting a current-year
capital gain files a Schedule CG whose own internal set-off table shows nothing happened, while
the schedule's bucket totals (and Part B-TI, sourced independently) correctly reflect that it did
— a real, visible internal inconsistency in the filed document.

**Severity:** High (disclosure completeness + internal consistency, not a tax-correctness defect).

**Remediation:** populate `CurrYrLosses` from the calculator's own within-CG loss-set-off working
(the same computation `post_loss_cg` is presumably derived from, or the classifier's per-bucket
gain/loss breakdown before netting) rather than leaving it zeroed; the schema's own field names
(`StclSetoff30Per`, `LtclSetOff12_5Per`, etc.) closely mirror the form's own column headers,
suggesting a fairly direct mapping is available once the calculator's intermediate netting values
are exposed to the builder.

> **Fix status (2026-09-09): fixed and verified.** The within-CG (section 70) intra-head loss
> set-off was already being computed as the first step of `cyla.py`'s own `compute()` (STCL
> against any CG bucket, then LTCG; LTCL against LTCG only), but only its AGGREGATE totals were
> exposed — the CYLA engine immediately continued into its own separate, later section-71
> cross-head absorption (business/HP losses against the same CG pools) without ever surfacing the
> per-source→per-target breakdown Table E needs. Refactored `cyla.py`'s `compute()` to track a
> full source-bucket × target-bucket set-off matrix (`CYLAResult.cg_setoff_matrix` and five sibling
> fields: `cg_gross_income`, `cg_gross_loss`, `cg_intra_head_remaining`, `cg_source_setoff_total`,
> `cg_source_loss_remaining`) as a snapshot taken before the later cross-head step runs — proven
> mathematically to preserve every existing aggregate/remaining value byte-for-byte regardless of
> the source-processing order chosen (only the new per-source attribution is order-sensitive, so a
> documented canonical bucket order was picked, mirroring the AMTC fix's own FIFO convention). A
> new `_cg_loss_setoff_table()` (`app/engine/itd/itr2.py`) maps this matrix directly onto the nine
> `CurrYrLosses` schema fields, replacing the hardcoded-zero stub; the now-dead `_z6()` helper was
> removed. `cyla.py` is shared with ITR-3's calculator — confirmed via `tests/test_cyla.py` (17
> tests, all still green) and a clean `import app.engine.calculators.itr3` that this is a strictly
> additive, non-breaking refactor. One new regression test in `tests/test_itr2_itd_builder.py`
> (`test_schedule_cg_table_e_reflects_real_intra_head_loss_setoff`), confirmed via `git stash` to
> fail against pre-fix code.

### New finding — Table F ("Information about accrual/receipt of capital gain", `AccruOrRecOfCG`) never uses real transaction dates

**Evidence:** `_accrued_cg()` (`itd/itr2.py:1648-1657`) takes no arguments and returns the same
all-zero `_date_range()` default for all six required quarterly buckets
(`ShortTermUnder20Per`/`30Per`/`AppRate`/`DTAARate`, `LongTermUnder12_5Per`/`DTAARate`) — called
unconditionally with zero arguments at `_schedule_cg()`'s single call site (line 1441). This is
the official form's Table F (form p. 50), which asks which quarter (Upto 15/6, 16/6-15/9,
16/9-15/12, 16/12-15/3, 16/3-31/3) each rate-bucket's gain actually accrued in — information that
is directly derivable from each `CGTransaction`'s own `date_of_sale`/`date_of_transfer` field
(already captured and used elsewhere in the same schedule for the STCG/LTCG classification split
itself), but never bucketed by quarter for this specific table.

**Impact:** same class as the Table E finding — a real, checkable form field silently left at its
"no data" default despite the underlying per-transaction dates existing in the input. Unlike Table
E, this table has no direct successor reference from Part B-TI, so its role is closer to
Schedule OS's own quarterly dividend/lottery breakdown (`_date_range()`'s own docstring already
documents that precedent) — informational disclosure supporting the taxpayer's own Section 234C
interest position, not a figure any downstream JSON block re-reads.

**Severity:** Medium (disclosure completeness only — matches this document's established rating
for the analogous Schedule OS quarterly-breakdown gaps elsewhere).

**Remediation:** bucket each `CGTransaction`'s (and land/building/112A row's) gain by transfer-date
quarter into the appropriate rate bucket, mirroring the quarterly-breakdown pattern already
implemented for Schedule OS's dividend disclosure (`itd/itr1.py`'s
`dividend_quarterly_breakdown`, per `_date_range()`'s own docstring).

> **Fix status (2026-09-09): fixed and verified.** `_accrued_cg()` (`app/engine/itd/itr2.py`) now
> takes `input_data`/`result` and buckets real gains by transfer-date quarter (a new
> `_cg_quarter_index()` helper implementing the form's own 5-period boundaries) into the 3 buckets
> this pipeline has real data for (111A → 20%, generic-other/land-building → 30%-or-12.5% by
> holding period, 112A/115AD scrips → 12.5%); the always-empty applicable-rate/DTAA buckets stay
> honestly zero, matching every other disclosure in this builder with no data source for them.
> Land/building reuses the calculator's own already-computed per-asset signed gain
> (`asset.balance`, which already reflects section 50C deeming and indexation) rather than
> re-deriving it; generic-other and 112A/115AD scrip gains use a simplified per-transaction formula
> that deliberately does not replicate section 50CA deeming or section 112A grandfathering exactly
> (both are aggregate-level refinements elsewhere in this schedule that are not distributive over a
> per-transaction sum, so an exact per-transaction replication would not even reconcile back to
> those aggregate figures) — documented in the function's own docstring as an honest, bounded
> approximation, consistent with this table having no downstream consumer. A loss-making
> transaction contributes zero to its quarter rather than a negative figure, since the schema's own
> `DateRangeType` fields reject negative values and the table discloses accrual of *gain*
> specifically. One new regression test in `tests/test_itr2_itd_builder.py`
> (`test_schedule_cg_table_f_buckets_gains_by_real_transfer_date_quarter`), confirmed via
> `git stash` to fail against pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/
> `test_cyla`/`test_capital_gains_loss_foundation` regression suite: 823 passed, only the same 6
> pre-existing failures (unrelated to this fix, not newly introduced).

### Forward-pointer — Part B-TI's `CapGain` block may drop non-zero STCG-30%/DTAA-rate buckets

While tracing Table E's correctness, `_partb_ti()`'s `CapGain` block (`itd/itr2.py:2593-2609`) was
observed to hardcode `ShortTerm30Per`/`ShortTermSplRateDTAA`/`LongTermSplRateDTAA` to `0`
unconditionally, reading only `post_loss_cg`'s `normal_stcg`/`111a`/`112`/`112a_gross` keys — not
verified further here (Part B-TI/B-TTI is its own dedicated pass later in this re-audit); flagged
so it isn't lost, and to be confirmed or ruled out when that section is audited rather than
duplicating the investigation now.

## 3.10 The top-level Schedule 115AD scrip-detail table (mirroring Schedule 112A) is never emitted — a real gap §3.1's fix did not cover

**Important distinction from §3.1**, confirmed by re-reading that finding's fix write-up in full:
§3.1's fix correctly routes an FII/FPI assessee's data to the *Schedule-CG-internal* aggregate
fields (`NRISecur115AD`, `NRISaleOfEquityShareUs112A`, Schedule-SI SecCodes `5AD1biip`/`5ADiii`
etc.) — that work is real and confirmed still correct in the current code. But the official
schema separately defines a **top-level, scrip-by-scrip detail schedule** named `Schedule115AD`
(`Schedule115ADDtls[]`, each row using the identical `Schedule112A115ADType` shape as
`Schedule112A`'s own rows) — this is the form's page-51 "115AD(1)(b)(iii) proviso" table, the
FII/FPI-specific structural twin of the resident-taxpayer `Schedule112A` scrip table, not the
Schedule-CG-internal aggregate fields §3.1 already fixed.

**Evidence:** grepped `app/engine/itd/itr2.py` for `Schedule115AD`/`_schedule_115ad` — the only hit
is the schema-referenced type name inside comments; there is no `_schedule_115ad()` function, and
the top-level JSON never carries a `"Schedule115AD"` key at all (the sole schedule-registration
site, line 2773, only sets `"Schedule112A": _schedule_112a(input_data)`). `_schedule_112a()`
itself (`itd/itr2.py:1664-1744`) has no FII/FPI branching whatsoever — it draws from the identical
`eligible_types = {"listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"}`
regardless of `input_data.filing_profile.is_fii_fpi`, and always emits its rows under
`"Schedule112A"`. This means an FII/FPI taxpayer's 112A-eligible scrip-level transactions are
currently placed in the **resident** taxpayer's scrip table, not the FII-specific one the official
form provides for exactly this case.

**The frontend already fully anticipated this distinction — the gap is purely in the final
JSON-builder step.** `frontend/src/components/CapitalGainsEntryManager.tsx` has a complete, separate
"Schedule 115AD scrip details" UI section (line 360, its own `RowSection`/`ScheduleTotals`,
distinct from "Schedule 112A scrips"), `app/schemas/return_draft.py:684-685` carries both
`schedule112A: list[Scrip112A]` and `schedule115AD: list[Scrip115AD]` as genuinely separate fields
on `CapitalGainsSchedule`, and `frontend/src/utils/mapCapitalGainsToDraftPatch.ts:238`/
`mapAisToDraftPatch.ts:372` both correctly route FII-flagged scrips into `schedule115AD`
specifically (with a dedicated passing test, `mapCapitalGainsToDraftPatch.test.ts:141`,
`'routes FII/FPI scrips → schedule115AD'`). The split survives all the way to
`app/engine/draft_to_itr2_input.py:161`, where `_map_112a_scrips()` reads
`for row in (*schedule.schedule112A, *schedule.schedule115AD):` — **unioning both lists back
together** into the single `cg_112a_scrips` field `_schedule_112a()` consumes, discarding which
of the two the row originally came from. So the underlying tax computation is unaffected (both
lists reach the calculator via the same union, matching §3.1's established disclosure-vs-
correctness distinction), but the one place that needs to keep the two schedules distinct — the
final ITD JSON builder — is exactly where the distinction is lost.

**Impact:** for any FII/FPI-flagged ITR-2 return with 112A-eligible (STT-paid equity/MF/business-
trust-unit) transactions, the filed JSON's scrip-level detail lands in the wrong schedule entirely
— `Schedule112A` instead of `Schedule115AD` — even though the Schedule-CG-level aggregate figures
these scrips roll up into are correctly routed (§3.1's fix). This is a structural misplacement,
not a wrong-number bug (the underlying tax amount is unaffected, matching §3.1's own established
distinction between disclosure-routing and computation bugs), but it is exactly the kind of gap
§3.1's own original title named ("Schedule 115AD is not emitted as a distinct official schedule")
— just not the specific manifestation that finding's fix ended up addressing.

**Severity:** CRITICAL (structurally wrong schedule for the exact taxpayer population — FII/FPI —
this table exists for; matches this document's established bar for CRITICAL when a whole
official-form table is unreachable for its intended population).

**Remediation:** the fix is narrower than it first appears, since the frontend/draft split already
exists end-to-end — only `_map_112a_scrips()` and the ITD builder need to stop collapsing it.
Keep `schedule.schedule112A` and `schedule.schedule115AD` as two separate lists through
`_map_112a_scrips()` (`draft_to_itr2_input.py:161`) instead of unioning them into one
`cg_112a_scrips`, add a `cg_115ad_scrips` field to `ITR2Input` alongside it, add a
`_schedule_115ad()` function mirroring `_schedule_112a()`'s row-building logic exactly (they share
the identical `Schedule112A115ADType` row shape per the schema), and emit `"Schedule112A"` from
the former and `"Schedule115AD"` from the latter in the object `produce_itd_json` returns at line
2773 (an FII/FPI assessee would typically populate only `schedule115AD`, but nothing prevents
both being non-empty in principle, so emit whichever of the two lists is non-empty rather than an
`is_fii_fpi`-only gate).

> **Fix status (2026-09-09): fixed and verified — implemented closer to the "route by FII/FPI
> status, not by which list it arrived in" design than the remediation note above proposed.**
> `app/schemas/itr2.py`'s `ITR2Input` gained a `cg_115ad_scrips: List[CG112AScrip]` field alongside
> the existing `cg_112a_scrips`. `app/engine/draft_to_itr2_input.py`'s `_map_112a_scrips()` now
> maps `schedule.schedule112A` and `schedule.schedule115AD` into two separate lists (via a new
> shared `_map_112a_scrip_rows()` row-builder) instead of unioning them before the calculator ever
> sees them, returning `(scrips_112a, scrips_115ad, skipped_count)`.
>
> `app/engine/itd/itr2.py` gained a shared `_112a_style_schedule(source_rows, suffix)` builder
> (parametrized on the `"112A"`/`"115AD"` field-name suffix, since both official schedules share an
> identical row type and aggregate-field shape) and a shared `_112a_source_rows()` helper (unifying
> the explicit-scrip and 112A-eligible-`CGTransaction` sourcing `_schedule_112a()` always had, so
> neither new function duplicates that logic). `_schedule_112a()` and the new `_schedule_115ad()`
> now each gate on `input_data.filing_profile.is_fii_fpi` and — **this is the one deliberate
> deviation from the remediation note's original "emit whichever list is non-empty" suggestion** —
> each unions *both* `cg_112a_scrips` and `cg_115ad_scrips` as its source, rather than reading only
> its "own" list. This was a correctness fix found while writing the regression tests below: the
> pre-existing FII/FPI test (`test_fii_fpi_capital_gains_route_to_section_115ad_fields_and_si_codes`)
> supplies its FII/FPI scrip through the older `cg_112a_scrips` field — a plausible, realistic
> construction pattern for any caller that predates `cg_115ad_scrips` and doesn't distinguish the
> two. Reading only `cg_115ad_scrips` for an FII/FPI assessee would have silently dropped that
> scrip from disclosure entirely (neither schedule would show it) despite the calculator still
> correctly taxing it (the calculator's own merge point, below, was already changed to union both
> lists regardless). Routing by FII/FPI status alone — not by which of the two lists a scrip
> happens to sit in — matches how `_schedule_cg()`'s own aggregate-level 112A/115AD routing already
> works, and guarantees no scrip is ever silently lost regardless of which list supplied it.
>
> `app/engine/calculators/itr2.py`'s 112A merge point (the ₹1.25L-threshold union point) now reads
> `[*input_data.cg_112a_scrips, *input_data.cg_115ad_scrips]` instead of `cg_112a_scrips` alone, so
> tax computation is unaffected by the split — both lists were already being taxed identically
> before this fix (via the draft mapper's old union), and still are now (via the calculator's own
> union) — only the *disclosure schedule* changes, not the *amount*.
>
> `produce_itd_json()` now registers `"Schedule115AD": _schedule_115ad(input_data)` alongside the
> existing `"Schedule112A"` entry.
>
> Four regression tests added to `tests/test_itr2_itd_builder.py`:
> `test_schedule_115ad_receives_fii_fpi_scrips_instead_of_schedule_112a` (a resident and an FII/FPI
> assessee with identical scrip data produce identical `capital_gains_income` but opposite
> Schedule112A/Schedule115AD presence) and
> `test_schedule_115ad_still_receives_scrips_supplied_via_cg_112a_scrips` (the "old field" case
> described above — confirms no silent data loss). Both confirmed via `git stash` (scoped to the
> four fix files: `itd/itr2.py`, `draft_to_itr2_input.py`, `calculators/itr2.py`, `schemas/itr2.py`
> — keeping the new tests unstashed) to fail on pre-fix code with `KeyError: 'Schedule115AD'`. Full
> combined regression suite: 791 passed, the same 6 pre-existing HUF-verification/representative-
> capacity failures as `HEAD` (confirmed unrelated and pre-existing via the same stash technique —
> see §8.0's fix note for the full list). Existing `test_112a_and_vda_rows_are_complete_signed_and_
> schema_valid` (non-FII, `cg_112a_scrips`) and `test_fii_fpi_capital_gains_route_to_section_115ad_
> fields_and_si_codes` (FII/FPI, `cg_112a_scrips`, asserts on `ScheduleCGFor23`/`ScheduleSI` only,
> not on `Schedule112A`/`Schedule115AD` presence) both still pass unmodified — no existing test
> needed updating.

## 3.11 Schedule VDA (2026-09-08 re-audit) — confirmed correct, no new finding

Cross-referenced Schedule VDA (form p. 51) against schema `ScheduleVDA` and
`_schedule_vda()` (`itd/itr2.py:1751-1766`). The schema's `HeadUndIncTaxed` enum is restricted to
the single literal value `"CG"` — not a range of possible heads — so the hardcoded
`"HeadUndIncTaxed": "CG"` is schema-correct by construction, not a shortcut: ITR-2's own form
scope categorically excludes business income ("For Individuals and HUFs **not having** income
from profits and gains of business or profession"), so VDA-as-business-income is not a case this
form or schedule can ever represent — it would be filed via ITR-3 instead. `IncomeFromVDA` is
correctly clamped to a minimum of `0` (`max(_ZERO, consideration - cost)`) when not explicitly
supplied, matching the form's own "enter nil in case of loss" instruction and the schema's
`minimum: 0` bound. `TotIncCapGain` is a straight sum of the row-level clamped incomes, consistent
with the schema. No discrepancy found.

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

## 3.4a Full form-order re-audit (2026-09-08) — Schedule OS's own headline aggregate is hardcoded to zero

Cross-referenced Schedule OS (form pp. 52-56) against schema `ScheduleOS`/`IncOthThanOwnRaceHorse`
and the current `_schedule_os()` (`itd/itr2.py:847-1124`) in full. §3.4's fix is confirmed still
correct and extensive on every category it addresses (dividend 22e/22f split with per-quarter date
ranges, unexplained-income 68/69/69A/69B/69C/69D, Section 89A with country rows, gift/56(2)(x)
breakdown, lottery/gaming quarterly breakdown, NRI DTAA rows, deductions) — no regression. This
pass found one field §3.4's otherwise-thorough fix missed entirely.

### New finding — `GrossIncChrgblTaxAtAppRate` (Schedule OS item "1", the schedule's own headline total) is hardcoded to `0` and never computed from the real components sitting right next to it

**Evidence:** the official form's Schedule OS item 1 is explicitly defined as a sum:
*"Gross income chargeable to tax at normal applicable rates (1a+1b+1c+1d+1e)"* — 1a Dividends,
1b Interest, 1c Rental income from machinery/plant/buildings, 1d Section 56(2)(x) income, 1e any
other income. `_schedule_os()`'s `block` dict literal (`itd/itr2.py:880`) initializes
`"GrossIncChrgblTaxAtAppRate": 0` and — confirmed by grepping the entire file for this exact key —
**it is never assigned again anywhere**, while its five constituent fields
(`DividendGross`/`InterestGross`/`RentFromMachPlantBldgs`/`Tot562x`/`AnyOtherIncome`) are all
correctly populated with real values a few lines later in the same function (lines 941-1006). The
schedule's own item "6" (`BalanceNoRaceHorse`, *"Net Income from other sources chargeable at
normal applicable rates (1(after reducing DTAA) − 3 + 4 + 5 − 5a)"*) IS correctly populated from
the real calculator total (`_to_rupees(os_excl_race_horse)`, line 938) — so the filed JSON shows a
schedule where the very first line item (the sum the rest of the schedule's arithmetic is built
on) is always `0`, while a downstream line six rows later, in the *same* JSON object, correctly
shows the real non-zero total it's supposed to be derived from — a directly visible, checkable
self-contradiction within one schedule, not merely an omission.

**Impact:** every ITR-2 return with any dividend, interest, rental, 56(2)(x), or other "normal
rate" other-source income (i.e. most real returns) files a Schedule OS whose own headline
aggregate figure is wrong (zero) while the schedule's total six lines later is correct — worse
than a simple missing-disclosure gap, since the two figures visibly disagree with each other under
the form's own explicitly-stated arithmetic relationship.

**Severity:** CRITICAL (a required, headline field on the most commonly-populated income schedule
in the form, always wrong when non-zero income exists, and internally inconsistent with a sibling
field in the same object — matches this document's established CRITICAL bar).

**Remediation:** set `block["GrossIncChrgblTaxAtAppRate"]` after the dividend/interest/rental/gift/
other-income fields are populated:
`DividendGross + InterestGross + RentFromMachPlantBldgs + Tot562x + AnyOtherIncome`, matching the
form's own stated "1a+1b+1c+1d+1e" formula exactly. Add a regression test asserting
`GrossIncChrgblTaxAtAppRate` is non-zero and correctly summed whenever these five inputs are
non-zero — the same cross-foot discipline this codebase already applies elsewhere (Schedule S/HP's
`raise ValueError` cross-foots) would have caught this immediately.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_os()` now sets
> `block["GrossIncChrgblTaxAtAppRate"]` from the block's own final
> `DividendGross`/`InterestGross`/`RentFromMachPlantBldgs`/`Tot562x`/`AnyOtherIncome` values (all
> five are stable by the point in the function this is computed — verified by tracing every
> assignment to each), placed alongside the existing `IncChargeableSpecialRates` cross-foot for the
> same "compute from already-finalized sibling fields, don't re-derive independently" discipline.
>
> **A second, separate, pre-existing bug was found while writing the regression test for this
> fix, not fixed here**: `os_other_income_entries` ("any other income," item 1e, disclosed via
> `AnyOtherIncome`/`OthersInc`) is **never summed into `result.other_sources_income` by the
> calculator at all** — grepped `app/engine/calculators/itr2.py` and
> `app/engine/schedules/other_sources.py` for `os_other_income_entries`: zero references anywhere
> outside the ITD builder itself. This means "any other income" a taxpayer discloses is correctly
> shown in Schedule OS's own `AnyOtherIncome` field (and now correctly included in
> `GrossIncChrgblTaxAtAppRate`, per this fix) but is **not actually taxed** — a real, undertaxation
> bug, first noticed because it made the regression test's "item 1 must equal item 6" assertion
> fail for a genuine reason unrelated to this fix (item 6, `BalanceNoRaceHorse`, correctly derives
> from `result.other_sources_income`, which excludes this component; item 1 now correctly includes
> it, so the two only remain equal when no "any other income" is disclosed — the test was adjusted
> to use only dividend/interest/rent/56(2)(x), which are all confirmed correctly taxed, rather than
> silently working around or masking this separate finding). Not fixed in this pass — out of scope
> for the specific `GrossIncChrgblTaxAtAppRate` fix requested; flagged here as a new, real, CRITICAL
> candidate finding for a future pass (likely fix: sum `os_other_income_entries` amounts into
> `r.other_sources_income` in `calculators/itr2.py`, matching how `os_machinery_plant_rent`/
> `os_special_rate_entries` are already added there).
>
> Regression test `test_schedule_os_gross_inc_chrgbl_tax_at_app_rate_sums_its_own_components`
> (`tests/test_itr2_itd_builder.py`) confirmed via `git stash` (scoped to `itd/itr2.py`) to fail on
> pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 794
> passed, the same 6 pre-existing failures as `HEAD` (see §8.0's fix note for the list; unrelated
> to this change).

> **Fix status (2026-09-09): the `os_other_income_entries` undertaxation gap noted above is also
> fixed and verified — this closes the last open item in this entire document.** The real fix
> required more care than the original note's "likely fix" suggested: `input_data.
> os_other_income_entries` was added directly into `r.other_sources_income` in
> `app/engine/calculators/itr2.py`, but investigating the real v2 draft pipeline first (rather than
> shipping that change alone) surfaced a genuine double-taxation risk the naive fix would have
> introduced — `app/engine/draft_to_itr2_input.py`'s `_map_other_sources()` call (shared with
> ITR-1) already sums every `draft.otherSources.otherIncome` row, generic-nature rows included,
> into `OtherSourcesIncome.other_income`, which itself already reaches GTI via `compute_os()`.
> Since `os_other_income_entries` is populated from the *same* rows (minus the MACHINERY_RENT/
> PASS_THROUGH natures, which the mapper already backs out of the generic aggregate for the
> identical reason — see the existing comment this fix extends), taxing `os_other_income_entries`
> directly without also backing its total out of the generic aggregate would have double-taxed
> every "any other income" row for every real taxpayer using the actual frontend, while only
> *fixing* undertaxation for the narrower case of a caller constructing `ITR2Input` directly
> (exactly how the original finding's own test was written, and precisely why it didn't surface
> this side effect). Fixed by widening the existing MACHINERY_RENT/PASS_THROUGH back-out block in
> `draft_to_itr2_input.py` to also subtract `os_other_income_entries`'s own total, so the two
> fields partition (not overlap) the same underlying rows — `os_other_income_entries` becomes the
> sole path to taxation for generic "other income," matching how it was clearly intended to work
> as `ITR2Input`'s own first-class typed field. Three tests: two new
> (`test_os_other_income_entries_are_taxed_not_just_disclosed`, proving taxable income itself
> shifts by exactly the disclosed amount, not just a JSON field;
> `test_os_other_income_entries_are_not_double_counted_via_the_draft_pipeline`, proving the real
> pipeline taxes it exactly once) plus one existing test updated
> (`test_pass_through_income_is_disclosed_and_not_double_counted` in
> `tests/test_draft_to_itr2_input.py`, whose own expected `other_income` value legitimately changed
> now that generic rows are backed out the same way PASS_THROUGH rows already were) — all three
> confirmed via `git stash` (scoped to `calculators/itr2.py`/`draft_to_itr2_input.py`) to fail
> against pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/
> `test_capital_gains_loss_foundation` regression suite: 827 passed, only the same 6 pre-existing
> failures (unrelated to this fix, not newly introduced). **Every finding tracked anywhere in this
> document — the original audit's P0/P1 list, the 2026-09-08 form-order re-audit's ten CRITICAL
> findings, and §8.0a — is now closed.**

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

## Part A-GEN — Full form-order re-audit (2026-09-08)

A fresh pass, driven strictly by the official ITR-2 form PDF's own page order (`Reference Docs by
CBDT & ITD\Official ITR FORMS\ITR-2-2026-Eng.pdf`, pp. 39-41) rather than by the prior findings
list, cross-referencing every Part A-GEN field against `Official JSON Schema\ITR-2_2026_Main_V1.1
(2).json`'s `PersonalInfo`/`FilingStatus`/`AssesseeName`/`Address`/`AlternateAddress`/
`AssesseeRep`/`CompDirectorPrvYrDtls`/`HeldUnlistedEqShrPrYrDtls`/`JurisdictionResPrevYrDtls`
definitions, then against `app/schemas/itr1.py`'s shared `PostalAddress`/`FilingAddress` (reused
by ITR-2), `app/schemas/itr2.py`'s `ITR2FilingProfile`, `app/engine/itd/itr2.py::_part_a_gen1()`,
and `frontend/src/components/PersonalInfoTab.tsx`.

**Confirmed correct, no new finding:** the backend field-length/pattern/min-max constraints are
comprehensively and precisely matched to the schema — `AssesseeName.SurNameOrOrgName` (maxLength
75, minLength 1), `FirstName`/`MiddleName` (maxLength 25), `Address`/`AlternateAddress.ResidenceNo`
(maxLength 50, minLength 1), `PinCode` (`[1-9][0-9]{5}`, no leading zero), `EmailAddress` (the
exact CBDT regex), `MobileNo`/`CountryCodeMobile` (integer, `[1-9][0-9]{4,9}`), `AssesseeRep.*`,
`CompDirectorPrvYrDtls.DIN` (`[0-9]{8}`), `HeldUnlistedEqShrPrYrDtls`'s eleven share/cost fields,
`LEIDtls.LEINumber` (exactly 20 chars), `TotalPrStayIndiaPrevYr`/`TotalPrStayIndia4PrecYr` (0-365 /
0-1461) — all match `ITR2FilingProfile` (`app/schemas/itr2.py`) and `FilingAddress`
(`app/schemas/itr1.py`) field-for-field, including the two subtly different "SebiRegnNo" key name
and mandatory-vs-optional shape the schema actually uses (already corrected in Phase 3/4).

### New finding — shared country-code list doesn't match any of the three schema enums it's used for

**Evidence:** the ITR-2 schema defines *three different* country-code enumerations, not one:
`CountryCode` (250 codes, includes `"91"` India — used by `Address.CountryCode`/
`AlternateAddress.CountryCode`), `CountryCodeExcludingIndia` (249 codes = `CountryCode` minus
`"91"`), and the inline `JurisdictionResPrevYrDtls.JurisdictionResidence` enum (250 codes =
`CountryCodeExcludingIndia` **plus** `"9998"` — "Not Applicable (Not Resident in any Country)").
The frontend's single shared list, `frontend/src/constants/itdCountryCodes.ts`'s
`ITD_COUNTRY_CODES` (249 entries), is used for *all* of these regardless of which one actually
applies at that call site (`PersonalInfoTab.tsx` for the Part A-GEN(e) jurisdiction-of-residence
table, `HousePropertyEntryManager.tsx` for property country). A programmatic diff against the
schema's three enums found:
- `ITD_COUNTRY_CODES` is missing `"93"` (Afghanistan) — **absent from every country dropdown in
  the app**, not just one field, since it's short by exactly this one code from all three schema
  enumerations.
- It is missing `"9998"` ("Not Applicable — Not Resident in any Country") — the one code specific
  to `JurisdictionResidence` — so an NRI/RNOR taxpayer who is not tax-resident anywhere cannot
  express that through `PersonalInfoTab.tsx`'s jurisdiction-of-residence dropdown at all, even
  though `JurisdictionResidenceEntry.jurisdiction_code` (`app/schemas/itr2.py:87`) would accept the
  string unvalidated.
- It wrongly includes `"91"` (India) — valid for `Address.CountryCode` (where
  `HousePropertyEntryManager.tsx` correctly needs it, e.g. for a property located in India) but
  **not** valid for `JurisdictionResidence`, so the same jurisdiction-of-residence dropdown lets a
  preparer select "91 — India" as a declared foreign jurisdiction of residence, which the official
  schema's `Draft4Validator` will reject at compute/submit time (enum mismatch) since `"91"` isn't
  a member of `JurisdictionResidence`.

**Impact:** narrow (only reachable for NRI/RNOR taxpayers filling the jurisdiction-of-residence
table, or anyone whose foreign country happens to be Afghanistan), and always fails loudly at the
schema-validation gate rather than silently producing wrong tax figures — but it is a genuine
gap in three different directions (one systemic omission, one wrong-enum-reused-elsewhere
inclusion, one missing legitimate value) from a single root cause: one shared list standing in for
three distinct schema enumerations.

**Severity:** P1 (schema-rejection risk + a legitimate disclosure value the taxpayer cannot enter;
not a silent-corruption risk).

**Remediation:** either split `ITD_COUNTRY_CODES` into the three schema-accurate lists (add a
`CountryCodeExcludingIndia`-flavoured export, reused by both the jurisdiction-of-residence and any
Schedule FA country dropdown — see Task/Schedule FA re-audit for whether FA has the same defect —
and a distinct `JurisdictionResidence`-flavoured export that adds the `"9998"` sentinel on top),
or keep one canonical 250-entry list matching the largest (`CountryCode`) enum and pass an
`excludeIndia`/`extraOptions` prop per call site. Either way, add `"93"` (Afghanistan) to the base
list — it is missing from all three schema enums' frontend representation today.

**Confirmed while auditing Schedule FA (§10.2)**: `app/engine/itd/country_codes.py`'s
`ITD_COUNTRY_CODE_TO_NAME` (the backend's own lookup, built during the Schedule FA fix by
"transcribing the schema's own `CountryCodeExcludingIndia` enum... cross-checked pair-for-pair")
already has all 249 correct entries including `"93"` — the frontend fix here can be a straight
resync from this already-correct backend source rather than a fresh transcription.

### New finding — six country-name labels are mojibake-garbled (display-only, values unaffected)

**Evidence:** `frontend/src/constants/itdCountryCodes.ts` has six entries whose `label` text was
corrupted by a UTF-8-as-Latin-1 double-encoding pass at some point (the `value` codes themselves
are correct ASCII digits and unaffected):

| Line | Current (garbled) | Should be |
|---|---|---|
| 4 | `'Ã…LAND ISLANDS'` | `'ÅLAND ISLANDS'` |
| ~ | `'CÃ”TE D\'IVOIRE'` | `'CÔTE D\'IVOIRE'` |
| ~ | `'CURAÃ‡AO'` | `'CURAÇAO'` |
| ~ | `'RÃ‰UNION'` | `'RÉUNION'` |
| ~ | `'SAINT BARTHÃ‰LEMY'` | `'SAINT BARTHÉLEMY'` |
| ~ | `'TIMOR-LESTEÂ (EAST TIMOR)'` | `'TIMOR-LESTE (EAST TIMOR)'` |

**Impact:** cosmetic only — the submitted JSON carries only the numeric `value` code, never the
`label`, so this cannot corrupt a filed return. It is a real, user-visible rendering defect in the
dropdown UI for six country names.

**Severity:** P2 (cosmetic).

### New finding — `required`/`pattern` markers throughout `PersonalInfoTab.tsx` (and, by the same
pattern, likely the rest of the ITR-2 frontend) are inert, not blocking

**Evidence:** every `Field`/`SelectField` in `PersonalInfoTab.tsx` (`Field` at line 79,
`SelectField` at line 155) renders a plain HTML `<input required pattern=... maxLength=... />` /
`<select required>`. These constraint-validation attributes only take effect when a real
`<form>` element's native submit/`reportValidity()` fires. `PersonalInfoTab` is rendered directly
inside `ITRComputationPage.tsx` (line 2032) with **no wrapping `<form>` element anywhere in that
page** — grepped for `<form` in `ITRComputationPage.tsx` and found zero matches. Saving and
computing both happen via direct `PUT /v2/clients/.../itr/...` and `POST
/v2/tax-summary/compute` calls triggered from button `onClick` handlers, which never invoke
native HTML constraint validation. This means every `required`/`pattern`/`maxLength` marker in
Part A-GEN — surname, PAN, DOB, mobile, email, SEBI registration number format, DIN format,
jurisdiction/TIN, director/unlisted-equity row fields — is currently decorative (an asterisk in
the label, `LabelText` at line 82/157) rather than a functioning gate. A preparer can leave any of
these blank or malformed and still successfully save the draft and trigger a compute; the actual
rejection only happens later, server-side, in `ITR2FilingProfile`'s Pydantic validators or the
final `Draft4Validator` schema check — both of which do correctly and safely catch it (this is not
a submission-correctness risk), but only after a wasted round trip and with a less specific error
message than the inline field-level feedback the `required`/`pattern` markup visually promises.

**Impact:** this is the exact same "cosmetic-only frontend validation" pattern already documented
for the Schedule IT challan editor in §3.8/Phase 3e ("shows red inline errors... but has no
blocking `isValid` check anywhere") — but confirmed here to be the *general* pattern across the
whole `PersonalInfoTab`, not a one-off in the challan editor. Given no `<form>` wraps any tab in
`ITRComputationPage.tsx`, this most likely holds for every other tab/schedule editor in the ITR-2
frontend too (Schedule S/HP/CG/OS/deductions editors, etc.) — this finding is recorded here once,
cross-referenced rather than re-discovered, in every subsequent section of this re-audit that
would otherwise repeat the identical observation.

**Severity:** P1 (UX/late-discovery quality gap, not a correctness or submission-safety gap — the
backend gate is real and effective).

**Remediation:** either wrap each tab in a real `<form onSubmit>` that calls
`event.preventDefault()` after running `form.reportValidity()` (cheapest, reuses the existing
`required`/`pattern` attributes as real gates), or add an explicit blocking `isValid`/error-summary
check before the save/compute button handlers proceed (matching the Schedule IT remediation
already planned in §3.8). Out of scope to fix broadly in this audit pass — flagged for the
consolidated P1 remediation list (§18).

### New finding — a stale code comment and this doc's own Phase 4 note both misstate current
representative-assessee support

**Evidence:** `app/engine/filing_gateway_v2.py:1298-1300`'s `_itr2_filing_profile()` docstring
reads *"since ITR-2 (unlike ITR-1/ITR-4) does not support REPRESENTATIVE at all"* — but the very
same function's current body (line 1312) accepts `verification.capacity in {"SELF",
"REPRESENTATIVE", "KARTA"}`, and lines 1364-1370/1486-1487 fully construct and pass through a
representative profile when capacity is `"REPRESENTATIVE"`. `ITR2FilingProfile`'s
`validate_conditional_filing_facts` (`app/schemas/itr2.py:252-255`) requires
`assessee_representative` to be set if and only if `verification_capacity == "R"`, and
`app/engine/itd/itr2.py:159/205-212` correctly emits `AsseseeRepFlg`/`AssesseeRep` conditionally.
Representative-assessee filing for ITR-2 is, in other words, **fully and correctly implemented
end-to-end today** — the docstring is simply out of date. This doc's own "Phase 4" section above
(the paragraph beginning *"`AsseseeRep`/`AsseseeRepFlg` — `AsseseeRepFlg` is correctly hardcoded
`"N"`... so ITR-2 genuinely never has a represented return, unlike ITR-1/ITR-4"*) repeats the same
now-incorrect claim and should be read as superseded by this note rather than authoritative.

**Impact:** none on filed returns — this is a documentation/comment accuracy issue only, not a
behavior bug. Recorded because the user's audit instructions asked for every discrepancy,
including where this document's own prior claims no longer match the code.

**Severity:** P2 (documentation accuracy only).

**Remediation:** correct the docstring at `filing_gateway_v2.py:1298-1300` to describe the actual
current behavior (representative capacity is supported, validated, and serialized) the next time
that function is touched; no code behavior change required.

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
>
> **Update (2026-09-05): §5.1/§5.2/§5.3's completeness gaps substantially closed too, in the same
> pass.** Investigating "salary detail breakdown" found `_schedule_s()` was recomputing
> `NetSalary`/`AllwncExtentExemptUs10`/`DeductionUnderSection16ia` locally from only
> `hra_exempt_amount + lta_exempt_amount`, instead of reading `result.schedules["salary"]` — the
> real, already-computed `SalaryResult` the calculator produces via
> `app/engine/schedules/salary.py::compute()`, which already has a complete per-exemption
> breakdown (gratuity/commuted-pension/leave-encashment/VRS/retrenchment/transport/children-
> education/hostel/uniform-allowance, each separately exempted per its own statutory formula) —
> the exact same "recompute instead of trust the calculator" bug class as §6.1's Schedule HP fix,
> just discovered one schedule over. Concretely, three real defects fixed:
>
> 1. `ValueOfPerquisites`/`ProfitsinLieuOfSalary` were hardcoded to `0` regardless of
>    `source.perquisites_value`/`profits_in_lieu_of_salary` — real, user-suppliable fields the
>    calculator already taxes as part of gross salary. Now populated (attributable to a specific
>    employer's row only when there is exactly one TDS1 entry — `SalaryIncome` is a single
>    aggregate across every employer, so a genuine multi-employer per-employer split isn't
>    determinable from this input shape; `Salary` (17(1)) is correctly back-solved as
>    `GrossSalary - ValueOfPerquisites - ProfitsinLieuOfSalary` rather than left equal to
>    `GrossSalary`, matching the real Section 17 relationship instead of implicitly assuming both
>    are always zero).
> 2. `AllwncExemptUs10Dtls` was hardcoded to an empty array. Now populated with one row per
>    exemption category the calculator actually granted a nonzero amount for (LTA, gratuity,
>    commuted pension, leave encashment, retrenchment, VRS, transport, children-education, hostel,
>    uniform), using the exact `SalNatureDesc` enum codes the official schema defines for each.
>    HRA (`10(13A)`) is deliberately excluded from this array — it already has its own dedicated
>    `Section10_13A` structure, and duplicating it risked double-disclosure.
> 3. `Increliefus89A` was hardcoded to `0` regardless of `result.relief_89` — a taxpayer claiming
>    salary-arrears relief under Section 89 had it correctly applied to their overall tax
>    liability but never disclosed in Schedule S at all. Now reads the real value.
>
> Switching `NetSalary`/`AllwncExtentExemptUs10`/`DeductionUnderSection16ia`/`DeductionUS16`/
> `EntertainmntalwncUs16ii`/`ProfessionalTaxUs16iii` to read directly from `SalaryResult` also
> incidentally fixed a fourth, smaller defect: under the new regime, entertainment allowance and
> professional-tax deductions are correctly zeroed by the calculator (Section 16(ii)/(iii) don't
> apply under 115BAC), but the previous code read the *raw* `source.entertainment_allowance`/
> `professional_tax_paid` input fields directly, disclosing a deduction the calculator never
> actually applied.
>
> The original mismatch-detection cross-foot (item 1's fix, above) is now a cleaner gross-to-gross
> comparison (`tds1_entries` sum vs `sal.gross_salary`) instead of the previous net-derived
> standard-deduction-going-negative check — functionally equivalent for catching the same
> divergence, but no longer coupled to the specific arithmetic path that produced it.
>
> Checked whether this is usable end-to-end via the v2 pipeline before considering it closed
> (matching the §6.1 HP lesson: check the frontend before assuming a gap needs new UI). It already
> is — `_map_salary()` (`app/engine/draft_to_itr1_input.py`, shared with ITR-1) already sums
> `Employer.perquisites`/`profitsInLieu`/`gratuity`/`commutedPension`/`leaveEncashment`/etc. into
> the aggregate `SalaryIncome` correctly (that function's own docstring documents its own earlier
> ITR-1 audit-fix history for these exact fields), so no v2-pipeline mapper changes were needed —
> this fix alone makes the real data already collected from the frontend actually reach the
> official JSON.
>
> Three regression tests added to `tests/test_itr2_itd_builder.py`
> (`test_schedule_s_serializes_real_perquisites_profits_in_lieu_and_relief_89`,
> `test_schedule_s_reports_real_section_10_exemption_breakdown`, plus the original mismatch test
> re-verified against the redesigned cross-foot), each confirmed via `git stash` to fail pre-fix.
> Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` plus every non-glob-matching sibling file (see the
> process note on commit `6e8cccf`) green: 784 passed.
>
> **Still open**: `NatureOfSalary`/`NatureOfPerquisites` detail arrays (event/category-level rows
> within a single employer, e.g. which specific perquisite types make up the total) remain
> hardcoded empty — the input schema has no per-category breakdown for these, only aggregate
> `perquisites_value`/`profits_in_lieu_of_salary` totals; and the full `Section10_13A` HRA
> structure (`ActlHRARecv`/`ActlRentPaid`/`Placeofwork`) remains unpopulated beyond the exempt
> amount itself — `SalaryIncome` only carries the *already-computed* `hra_exempt_amount`, not the
> raw rent/city/actual-HRA-received components the official schema's detailed structure wants,
> even though those raw components do exist on the frontend's `Employer.rentPaid`/`city`/
> `isMetroCity`/`hra` fields. Populating `Section10_13A` fully would need new `SalaryIncome` input
> fields to carry those raw components through — a schema change beyond this JSON-builder fix, and
> the multi-employer per-perquisite-category attribution problem (item 1 above) would need a real
> per-employer schema redesign, not a builder fix, to resolve properly.

## 5.5 Full form-order re-audit (2026-09-08) — uncommitted in-progress rewrite found, with a real bug

Cross-referenced Schedule S (form pp. 41, official ITR-2 form) against schema `ScheduleS`/
`Salaries`/`AddressDetail`/`NatureOfSalaryDtlsType`/`NatureOfPerquisitesType`/
`NatureOfProfitInLieuOfSalaryType`/`NOT89AType`/`AllwncExemptUs10DtlsType`. **Important context for
this section:** the working tree currently has a substantial **uncommitted** rewrite of
`_schedule_s()` (`app/engine/itd/itr2.py`), `app/engine/schedules/salary.py`, `app/schemas/itr2.py`
(`EmployerFilingDetail`), and `app/schemas/return_draft.py` (`Employer`) — confirmed via `git diff
--stat` (4 files, 149 insertions / 47 deletions) at the start of this session, predating this
audit. This rewrite is a genuine, substantial attempt to close exactly the "Still open" gaps
§5.4 documents above (`NatureOfSalary`/`NatureOfPerquisites`/`NatureOfProfitInLieuOfSalary` detail
arrays, the full `Section10_13A` HRA structure, and the full 89A structure with country rows). It
is **not part of any commit** — `git log` shows no matching commit — so the findings below describe
uncommitted working-tree state, not what is currently deployed or what `HEAD` computes.

**Confirmed correct in the new code:** `EmployerFilingDetail` gained
`income_notified_89a`/`income_notified_other_89a`/`income_notified_prior_year_89a` (all
`Decimal, ge=0`, matching schema's non-negative integer bounds) and the builder now populates
`IncomeNotified89A`/`IncomeNotifiedOther89A`/`IncomeNotifiedPrYr89A` from real per-employer data
instead of the old hardcoded `0`/`0`. `Section10_13A` is now built from real
`actual_hra_received`/`actual_rent_paid`/`salary_for_hra`/`is_metro_city` detail fields (computing
`Placeofwork`, `ActlRentPaid10Per`, `Sal40Or50Per`, `EligbleExmpAllwncUs13A` per the real Section
10(13A) formula) instead of the old hardcoded `Placeofwork: "2"` with four zeroed sub-fields.
`TotalGrossSalary` is now cross-footed against the sum of per-employer gross rather than trusting
the calculator's aggregate blindly, and a new-regime branch correctly zeroes the whole HRA
computation (`hra_received = rent_paid = hra_salary = salary_rate = hra_calc = _ZERO`) since HRA
exemption doesn't apply under 115BAC — matching how the rest of this codebase already handles new
regime for Section 16(ii)/(iii) per §5.4's earlier fix.

### New finding — a per-employer exemption-rows computation (including a synthesized 10(13A) row) is built and then silently discarded

**Evidence:** inside the per-employer loop in the uncommitted `_schedule_s()`, a local
`exemption_rows` list is computed from `detail.section10_exemption_rows`, and — when that
specific employer has HRA data — an additional synthesized `{"SalNatureDesc": "10(13A)", ...}`
row is appended to it:
```python
exemption_rows = [
    {"SalNatureDesc": row["SalNatureDesc"], ...}
    for row in detail.section10_exemption_rows if row.get("SalOthAmount", 0) > 0
]
if detail.actual_hra_received > 0 and detail.actual_rent_paid > 0 and detail.salary_for_hra > 0:
    hra_exempt = min(...)
    exemption_rows.append({"SalNatureDesc": "10(13A)", ...})
row["Salarys"]["NatureOfSalary"] = {"OthersIncDtls": detail.nature_of_salary_rows}   # <- next line
if employer_tan:
    row["TANofEmployer"] = employer_tan
employers.append(row)
```
This `exemption_rows` local is never assigned to `row` (the per-employer dict) or to any other
output structure — the very next line reassigns `row["Salarys"]["NatureOfSalary"]` (already set
identically two lines earlier when `row` was first constructed, making that a second, redundant
assignment) instead of consuming `exemption_rows`. The variable, and the HRA-row synthesis logic
that computed it, is dead: built, mutated, then dropped. Separately, a schedule-level (not
per-employer) `exemption_rows` is computed later from `_SALARY_EXEMPTION_ROWS`/`sal.*` fields and
correctly flows into the schedule's own `AllwncExemptUs10` block — that one is fine; only the
per-employer local of the same name is the dead one. (`ScheduleS`'s `AllwncExemptUs10` is a
schedule-level, not a per-`Salaries`-item, field per the schema — so the per-employer computation
was misguided in shape from the start, not merely mis-wired: even fixed, per-employer exemption
rows have nowhere to live in the official structure.)

**Impact:** none on the actually-serialized JSON today, since the entire block never runs against
real user input yet (see next finding) — but it represents ~10 lines of incomplete/dead logic that
would need to be either wired up correctly or deleted before this rewrite is committed.

**Severity:** P2 while uncommitted (dead code in a working-tree diff, not shipped behavior); would
be worth a second look once this rewrite is finalized, to confirm the shape mismatch above is
understood before deleting or repurposing it.

### New finding — the new detail-array fields have no frontend UI to populate them

**Evidence:** grepped `frontend/src` for `salaryNatureRows`, `perquisiteNatureRows`,
`profitInLieuNatureRows`, `incomeNotified89A`, `incomeNotifiedOther89A`,
`incomeNotifiedPriorYear89A`, `incomeNotified89ACountryRows` (the exact new field names added to
`Employer` in the uncommitted `return_draft.py` diff). No matches in
`frontend/src/components/EmployerEntryManager.tsx` (the actual salary/employer editor) or anywhere
else that constructs a form control for them; the only frontend hits are unrelated same-substring
matches (`section89AOS` aggregates in `ITRComputationTabs.tsx`, which is Schedule OS's *own*,
differently-modeled retirement-account-in-notified-country line item, not Schedule S's per-employer
89A fields). This means even once the dead-code issue above is fixed and this rewrite is committed,
every one of these new fields would default to empty/zero for every real return, since nothing in
the UI can set them — the backend plumbing exists ahead of any way for a preparer to exercise it.

**Impact:** none yet (no reachable path), but confirms the "Still open" items from §5.4 are not
actually closed end-to-end by this uncommitted work — only the JSON-builder half exists.

**Severity:** P1 once this backend rewrite is committed (a real, schema-modeled capability with a
completely unreachable UI is the same class of gap as every other "captured on the frontend but
not serialized" finding elsewhere in this doc, just inverted — serialized but not capturable).

### New finding — the new detail-row list fields are untyped, unvalidated `dict[str, Any]` arrays

**Evidence:** `EmployerFilingDetail.nature_of_salary_rows` / `nature_of_perquisites_rows` /
`nature_of_profit_in_lieu_rows` / `income_notified_89a_country_rows` (all in the uncommitted
`app/schemas/itr2.py` diff) are typed `list[dict[str, Any]]` with no Pydantic model behind them,
unlike every other structured row type audited so far in this document (`CompanyDirectorEntry`,
`UnlistedEquityEntry`, `JurisdictionResidenceEntry`, etc., all of which have exact
field-name/pattern/enum/bounds validation). The schema requires each row to carry a closed-enum
`NatureDesc` (`"1"`-`"17"`/`"OTH"` for salary, a different 21-value enum for perquisites, a 4-value
enum for profit-in-lieu), an `OthAmount` bounded `0`-`99999999999999`, and — for
`income_notified_89a_country_rows` specifically — a `NOT89ACountrycode` restricted to exactly
`"US"`/`"UK"`/`"CA"`. None of that is enforced before the raw dicts reach
`app/engine/itd/itr2.py`'s `{"OthersIncDtls": detail.nature_of_salary_rows}` passthrough, so a
malformed row (wrong key name, out-of-enum `NatureDesc`, non-integer `OthAmount`) would only be
caught at the final official-schema `Draft4Validator` check, not at the Pydantic input-validation
layer the rest of this codebase relies on for early, specific errors.

**Impact:** none yet (unreachable — see the no-UI finding above), but worth fixing in the same
pass that wires up a UI for these fields, before real user input can reach them.

**Severity:** P2 (would be P1 once reachable from the UI — matches this document's established
severity convention of rating unreachable-today gaps lower than the same defect once exercisable).

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
> **Update (2026-09-05): closed.** Lender identity/PAN, loan account number, sanction date, and
> outstanding balance (`Section24BDtls[]`); co-owner rows (`CoOwners[]`); and tenant rows
> (`TenantDetails[]`) are now backed by real input models — `HomeLoanDetail`, `CoOwnerDetail`,
> `TenantDetail` (`app/schemas/itr2.py`), added as `home_loan_details`/`co_owner_details`/
> `tenant_details` lists on `PropertyFilingDetail`. `_schedule_hp()` now serializes real rows and
> **cross-foots** `home_loan_details` interest against the property's actual computed Section
> 24(b) interest (raising if they disagree, matching this file's own established cross-foot
> discipline), rather than accepting an arbitrary user-supplied total. A `co_owned=True` flag with
> no `co_owner_details` is now rejected at construction time — the exact "flag with no detail"
> bug class this fix's own §6.1 root cause already was.
>
> Investigating the v2 pipeline wiring found this was a smaller gap than expected: the frontend
> (`HousePropertyEntryManager.tsx`) and draft schema (`HouseProperty.homeLoans`/`coOwners`/
> `tenantDetails`, using `HomeLoan`/`CoOwner`/`TenantDetail` in `app/schemas/return_draft.py`)
> **already existed** — this data was being collected from real taxpayers and then silently
> discarded, because `filing_gateway_v2.py`'s `_itr2_property_filing_details()` only ever mapped
> the flat `isCoOwned`/`ownershipShare` scalars and never read any of the three detail arrays at
> all. Wired all three through. Confirmed the frontend's `interestOnLoan` field has no UI control
> of its own (only ever defaults to `0`), so `_map_house_property()`'s existing "fall back to
> `sum(homeLoans[].interestUs24B)` when the top-level scalar is zero" branch is what real frontend
> traffic always exercises — meaning the new per-loan cross-foot check cannot conflict with the
> calculator's own computed interest for any draft actually produced by this frontend.
>
> Pre-construction interest amortization and property completion date/status remain out of scope
> — the official schema does not carry dedicated fields for either as part of `Section24BDtls`, so
> they are a different (and smaller) kind of gap than the "no backing model at all" one this note
> originally described.
>
> Two regression tests added to `tests/test_itr2_itd_builder.py` (serialization + cross-foot
> rejection) and one to `tests/test_filing_gateway_v2_itr2.py` (real v2-pipeline wiring), each
> confirmed via `git stash` to fail pre-fix. Also caught and fixed, in the same pass: 4 pre-existing
> `test_itr2_input_validation.py` tests (`HP-004`/`HP-007`) constructed `co_owned=True` without
> `co_owner_details` and needed updating for the new construction-time requirement — not a
> regression in those rules themselves, just fixture rows written before this requirement existed.
> Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` plus every non-glob-matching sibling file
> (`test_draft_to_itr{1,2,4}_input*.py`, `test_filing_gateway_v2_itr{2,4}.py`, `validate_itr1_json.py`
> — see the note below on why these are now checked every time) green: 782 passed.
>
> **Process note**: this same investigation surfaced that commit `53ff0a6` (the §5.4 Schedule S
> fix, earlier in this Phase 5 pass) had silently broken 12 of 23 tests in
> `test_filing_gateway_v2_itr2.py` — undetected for several commits because that filename doesn't
> start with `test_itr2_` and so was never caught by this session's `tests/test_itr2_*.py`
> regression glob. Root cause there was a test fixture (`_filing_ready_itr2_draft()`) that set
> `TdsCredit.taxDeducted` but never `grossAmount`, which the shared `_map_tds()` helper needs for
> `TDS1Entry.income_chargeable` — genuinely incomplete test data, not a flaw in the Schedule S fix
> (confirmed by a one-line fixture correction, committed separately as `6e8cccf`, making all 23
> tests pass again). Every subsequent regression run in this file, and this session going forward,
> uses the expanded file list above instead of the bare `test_itr{1,2,4}_*.py` glob.
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

## 6.4 Full form-order re-audit (2026-09-08)

Cross-referenced Schedule HP (form pp. 41-42) against schema `ScheduleHP`/`PropertyDetails`/
`Rentdetails`/`CoOwners`/`TenantDetails`/`AddressDetailWithZipCode` and the current (committed)
`app/engine/itd/itr2.py::_schedule_hp()`. **Confirmed still correct** (no regression since the
§6.1 fix): every `Rentdetails` field is read from the real per-property `HPResult`, not
re-derived; `Section24BDtls`/`CoOwners`/`TenantDetails` are populated from real
`home_loan_details`/`co_owner_details`/`tenant_details`; the loan-interest cross-foot is present;
`AddressDetailWithZipCode.CountryCode` is always emitted (required by schema) with a correct
default.

### New finding — `PropertyOwnerOther` (the "Other" owner-type description) is captured on the frontend but silently dropped before reaching the ITD builder

**Evidence:** the official form's Schedule HP asks for property ownership as one of Self/Minor/
Spouse/Others, and schema `PropertyDetails.PropertyOwnerOther` (maxLength 50) exists specifically
to describe who "Others" refers to when `PropertyOwner: "OT"` is selected.
`frontend/src/components/HousePropertyEntryManager.tsx:92-93` already has this fully wired: a
`propertyOwnerType` selector offering `OT`/"Other", and a conditional `propertyOwnerOther` text
field (`required`, `maxLength={50}`) that appears exactly when `OT` is selected — and
`return_draft.py:344`'s `HouseProperty.propertyOwnerOther: str` carries the value. But
`app/schemas/itr2.py:768-791`'s `PropertyFilingDetail` — the class `_schedule_hp()` actually reads
from — has **no `property_owner_other` field at all**, and `filing_gateway_v2.py`'s ITR-2-specific
`PropertyFilingDetail(...)` construction (around line 1552-1561) passes `property_owner=
row.propertyOwnerType` but never `row.propertyOwnerOther`. (The same file *does* correctly wire an
identically-named `property_owner_other` for a different, ITR-1-style normalizer path at lines
754-778/1021-1067 — confirming the field is understood and handled correctly elsewhere, just
missed for ITR-2's own property-filing-detail construction specifically.) `_schedule_hp()`
consequently never emits a `PropertyOwnerOther` key at all, for any property, regardless of what
the taxpayer entered.

**Impact:** a taxpayer whose house property is owned by someone other than self/minor-child/spouse
(e.g. a different relative, an HUF, a trust) and who fills in the required "who" description on
the frontend has that description **silently discarded** — the filed JSON shows `"PropertyOwner":
"OT"` with no supporting detail. This is the same "captured on the frontend, dropped before the
JSON" severity class as this document's §3.1-§3.7 CRITICAL findings, just found in a schedule
whose other gaps (§6.1) were already closed.

**Severity:** CRITICAL for affected returns (any return where `PropertyOwner == "OT"` is
selected) — likely a small fraction of all ITR-2 returns by frequency, but a complete,
silent information-loss bug for every one of them, exactly matching this document's existing
bar for CRITICAL (not merely High) severity.

**Remediation:** add `property_owner_other: Optional[str] = Field(default=None, max_length=50)`
to `PropertyFilingDetail` (`app/schemas/itr2.py`), thread it through the ITR-2-specific
`PropertyFilingDetail(...)` construction in `filing_gateway_v2.py` (`row.propertyOwnerOther`), and
emit `"PropertyOwnerOther": detail.property_owner_other` in `_schedule_hp()` when
`detail.property_owner == "OT"` (omit the key otherwise, matching this codebase's established
"no empty placeholder" convention). Consider a model validator requiring
`property_owner_other` to be set when `property_owner == "OT"`, matching the `co_owned` →
`co_owner_details` precedent already established in this same class (`app/schemas/itr2.py`'s
`validate_co_owner_details`).

> **Fix status (2026-09-09): fixed and verified, exactly as remediated above (including the
> suggested validator).** `PropertyFilingDetail` gained `property_owner_other: Optional[str] =
> Field(default=None, max_length=50)` plus a new `validate_property_owner_other` model validator
> (`@model_validator(mode="after")`, mirroring `validate_co_owner_details`'s own "flag with no
> detail" precedent exactly) requiring it whenever `property_owner == "OT"`.
> `_itr2_property_filing_details()` (`filing_gateway_v2.py`) now passes
> `property_owner_other=row.propertyOwnerOther[:50] or None`. `_schedule_hp()` (`itd/itr2.py`) now
> emits `"PropertyOwnerOther": detail.property_owner_other` only when `property_owner == "OT"` —
> the new validator guarantees the value is present whenever that key is emitted, so no additional
> null-check is needed at the emission site.
>
> Three regression tests: `test_property_filing_detail_requires_property_owner_other_when_owner_is_others`
> (construction-time rejection, matching the existing `co_owned`/`co_owner_details` test's own
> pattern) and `test_schedule_hp_serializes_property_owner_other_only_when_owner_is_others` (both
> directions — real value correctly serialized for `"OT"`, key correctly absent for the default
> `"SE"`), both added to `tests/test_itr2_itd_builder.py`. Confirmed via `git stash` (scoped to
> `itd/itr2.py`/`filing_gateway_v2.py`/`schemas/itr2.py`) to fail on pre-fix code. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 799 passed, the same 6 pre-existing
> failures as `HEAD` (see §8.0's fix note for the list; unrelated to this change).

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

## 7.5 Full form-order re-audit (2026-09-08) — `IncNotChrgblToTax` holds the wrong figure entirely

Cross-referenced Schedule EI (form p. 62) against schema `ScheduleEI` and `_schedule_ei()`
(`itd/itr2.py:1902-1929`). The official form's item ordering is: 1 Interest income, 2
Agricultural income (gross/expenditure/unabsorbed-loss/net), 3 Other exempt income, **4 Income
claimed as not chargeable to tax as per DTAA (Non-Residents only)** — a country/nature/article
detail table whose own row "III" is explicitly labeled *"Total Income from DTAA claimed as not
chargeable to tax"* — 5 Pass-through income claimed as not chargeable to tax (Schedule PTI), 6
Total (1+2+3+4+5). The schema's property ordering mirrors this exactly, placing
`IncNotChrgblToTax` immediately after `IncNotChrgblAsPerDTAA` (the DTAA detail array) — confirming
`IncNotChrgblToTax` is item 4's own "III" total, a DTAA-specific figure, not a general label.

### New finding — `IncNotChrgblToTax` is populated from `interest_inc` (item 1's own figure), not from any DTAA data

**Evidence:** `_schedule_ei()` computes `interest_inc = exempt.ppf_interest +
exempt.sukanya_samriddhi_interest + exempt.tax_free_bond_interest + exempt.nre_interest` and
correctly assigns it to `"InterestInc"` (item 1) — then, separately,
**also** assigns the exact same `interest_inc` value to `"IncNotChrgblToTax"`
(`_to_rupees(interest_inc)`, line 1926) — the field that per the schema's own ordering and the
form's own row "III" label should hold the DTAA-claimed-non-chargeable total, which this codebase
has no input for at all (`"IncNotChrgblAsPerDTAA": {"IncNotChrgblAsPerDTAADtls": []}` is
unconditionally empty, two lines above). For any resident taxpayer with real PPF/Sukanya
Samriddhi/tax-free-bond/NRE interest, this makes Schedule EI show that same interest figure a
second time, mislabeled as a DTAA-exemption total that does not exist for that taxpayer — the
schedule's own arithmetic note ("4" feeds into "6 Total (1+2+3+4+5)") would then double-count
`interest_inc` if a reviewer worked the form's own stated formula by hand, even though this
codebase's own `total_exempt` variable (used for `TotalExemptInc`) is computed independently and
correctly (`interest_inc + others + net_agricultural_income`, not from the mislabeled field) — so
the schedule's bottom-line total happens to still be right, matching this document's now-familiar
pattern (CLAUDE.md's own documented precedent: "a JSON field can be schema-valid... while still
holding the wrong number, if the ITD builder maps the wrong calculator field into it").

**Impact:** every resident taxpayer with any of the four interest types this codebase captures
files a Schedule EI whose DTAA-total line is a duplicate of their interest-income line rather than
the correct `0` (no DTAA data captured) — visible, checkable, and specifically confusing since the
schema field name (`IncNotChrgblToTax`) and its neighbor (`IncNotChrgblAsPerDTAA`) leave little
ambiguity about what it's meant to represent. `TotalExemptInc` itself is unaffected (computed
independently), so this is a disclosure-correctness bug, not a tax-amount bug.

**Severity:** High (a required field showing a specific wrong, non-zero, mismatched-concept value
— worse than a zeroed placeholder, since it actively misrepresents interest income as a DTAA claim
— but the bottom-line total is unaffected).

**Remediation:** set `"IncNotChrgblToTax": 0` when no DTAA rows exist (or sum the real
`IncNotChrgblAsPerDTAADtls` amounts once that detail array is populated — see the secondary
finding below); remove the erroneous `interest_inc` assignment to this field entirely.

### Secondary finding — DTAA exempt-income detail (item 4) and PTI-exempt income (item 5) are entirely unimplemented

**Evidence:** `IncNotChrgblAsPerDTAA.IncNotChrgblAsPerDTAADtls` and `PassThrIncNotChrgblTax` are
both unconditionally hardcoded (empty array / `0`) with no input field feeding either — items 4
and 5 of the official form have no representation in this codebase's `ITR2Input` at all. Given
Schedule FSI/TR (a later section of this re-audit) already models foreign-source income and DTAA
relief for the *taxable* portion, item 4 here would need a parallel, smaller structure specifically
for *non-taxable* DTAA-exempt income — not yet present.

**Severity:** Medium (a real gap, but narrower in taxpayer population — non-resident/DTAA-eligible
filers specifically — than the `IncNotChrgblToTax` mislabeling above, which affects any resident
with ordinary exempt interest).

---

# 7a. Schedule CYLA / BFLA / CFL — loss set-off and carry-forward

## 7a.1 Full form-order re-audit (2026-09-08) — confirmed correct, no new finding

Cross-referenced Schedule CYLA (form p. 56), BFLA (form p. 57), and CFL (form pp. 57-58) against
schema `ScheduleCYLA`/`ScheduleBFLA`/`ScheduleCFL` and `_schedule_cyla()`/`_schedule_bfla()`/
`_schedule_cfl()` (`itd/itr2.py:331-509`). All three are thoroughly and correctly implemented; no
new gap found despite specifically checking the two things most likely to hide a bug:

- **`ScheduleCYLA.TotalLossSetOff.TotHPlossCurYrSetoff` has a schema-enforced `maximum: 200000`**
  (the Section 71(3A) statutory cap on house-property loss set against other heads). Traced to
  `app/engine/schedules/loss_setoff/cyla.py:232`, `hp_eligible = min(hp_loss, Decimal("200000"))`
  — the cap is correctly applied at the calculator level before the figure ever reaches the
  builder, so this schema bound can never be violated by real data.
- **CFL's already-fixed year-slot-type distinction** (§9.4's fix: `OthSrcLossRaceHorseCF` only
  valid on the 4 most recent year slots, `additionalProperties: false` on both slot types,
  `DateOfFiling` unconditionally required) is confirmed present and correct in the current code —
  no regression since that fix.

`OthSrcExclRaceHorse`'s `TotOthSrcLossNoRaceHorseSetoff`/`BalOthSrcLossNoRaceHorseAftSetoff` being
hardcoded to `0` in `_schedule_cyla()` was checked and is correct by design, not a gap: Indian tax
law (Section 71) has no brought-forward carry-forward concept for ordinary other-sources losses
(only the current year's own loss can be set off, and only race-horse losses under a distinct
Section 74A regime survive to future years) — so there is genuinely nothing to report in these
fields for any real taxpayer.

---

# 8. Deductions

## 8.0 Full form-order re-audit (2026-09-08) — Schedule VIA is schema-invalid whenever any Chapter VI-A deduction is actually claimed

Cross-referenced Schedule VIA (form p. 58) against schema `ScheduleVIA`/`DeductUndChapVIA`/
`UsrDeductUndChapVIA` and `_schedule_via()` (`itd/itr2.py:1773-1821`) — found before reaching the
existing §8.1-§8.3 findings below, and severe enough to place first.

**Evidence:** the schema defines `ScheduleVIA` as exactly two required sub-objects,
`UsrDeductUndChapVIA` (the taxpayer's raw claimed amounts, one named integer field per section —
`Section80C`, `Section80D`, `Section80G`, `Section80GGA`, etc.) and `DeductUndChapVIA` (the same
sections after statutory capping — `Section80D` capped at 100000, `Section80DD` at 125000,
`Section80CCD1B` at 50000, `Section80GG` at 60000, `Section80U` at 125000, `Section80TTA` at
10000, `Section80TTB` at 50000, `Section80RRB`/`Section80QQB` at 300000, `AnyOthSec80CCH` at
288000, etc.) — with `DeductUndChapVIA.Section80D`/`Section80G`/`Section80GGA` all **required**,
unconditionally, alongside `TotalChapVIADeductions`. `_schedule_via()`'s actual return value is:
```python
return {
    "UsrDeductUndChapVIA": {"TotalChapVIADeductions": _to_rupees(result.deductions_total)},
    "DeductUndChapVIA": {"TotalChapVIADeductions": _to_rupees(result.deductions_total)},
    "DeductUndChapVIAList": via_entries,
}
```
Neither sub-object emits a single one of the ~20 named per-section fields the schema actually
defines — not even the three the schema marks required (`Section80D`, `Section80G`,
`Section80GGA`). The function *does* build a real, carefully-mapped per-section breakdown
(`via_section_map`, translating internal deduction keys to official section codes, and
`via_entries`, a list of `{Section, Amount}` rows) — but places it under `"DeductUndChapVIAList"`,
a key that **does not exist anywhere in the official schema's `ScheduleVIA` definition**. With
`additionalProperties: false` enforced throughout this schema (confirmed on every object dumped in
this entire re-audit so far), emitting an undefined key is itself an independent schema violation,
on top of the three missing required fields.

**Confirmed no test coverage exists for this**: grepped `tests/test_itr2_itd_builder.py` for
`DeductUndChapVIA`/`schedule_via`/`ScheduleVIA` — zero matches. This is consistent with the bug
having gone unnoticed: it only manifests once `_schedule_via()` is actually invoked with real
non-zero deductions (`result.deductions_total > 0`, its own early-return guard), and no existing
regression test exercises that path against the official schema validator.

**Impact:** any ITR-2 return claiming *any* Chapter VI-A deduction — 80C, 80D, 80G, and every
other section this codebase already supports at the calculator level — produces JSON that fails
official schema validation on at least four independent grounds (three missing required fields
plus one disallowed extra key) the moment Schedule VIA is populated. Given the vast majority of
real taxpayers claim at least one VI-A deduction (80C alone is close to universal), this is not an
edge case — it is very close to "no real ITR-2 return with deductions can currently pass schema
validation," the most severe class of finding this document defines.

**Severity:** CRITICAL — likely the single highest-impact finding in this entire re-audit by
breadth of affected returns, given how close to universal Chapter VI-A deduction claims are.

**Remediation:** rebuild `_schedule_via()` to populate every named section field on both
`UsrDeductUndChapVIA` (raw claimed amounts from `breakdown`, uncapped) and `DeductUndChapVIA` (the
same amounts after applying each section's own statutory cap — the `via_section_map`'s existing
code-to-section knowledge is exactly what's needed to route `breakdown[key]` to the right named
field on each object), remove the non-existent `DeductUndChapVIAList` key, and always include
`Section80D`/`Section80G`/`Section80GGA` (defaulting to `0` when unclaimed, since they are
unconditionally required even at zero) plus `TotalChapVIADeductions` on `DeductUndChapVIA`. Add a
regression test that runs a populated return with at least one VI-A deduction through the full
official-schema `Draft4Validator`, not just a hand-inspection of the returned dict — the gap here
is exactly the kind a schema-validation assertion would have caught immediately.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_via()` (`itd/itr2.py`) now populates
> every named per-section field on both `DeductUndChapVIA` and `UsrDeductUndChapVIA` from
> `result.schedules["deductions"].breakdown` (each section's own statutory-capped, GTI-capped
> amount — exactly what `DeductUndChapVIA` wants), via a new `_VIA_SECTION_TO_FIELD` map from the
> engine's internal breakdown keys to the official schema field names. `Section80D`/`Section80G`/
> `Section80GGA` are always included (default `0`) since the schema requires them unconditionally;
> `TotalChapVIADeductions` is computed as the sum of the emitted per-section rupee figures (not an
> independently-rounded copy of `result.deductions_total`), so the schedule's own total always
> cross-foots against its own section fields. The non-existent `DeductUndChapVIAList` key is
> removed entirely. A `ValueError` is raised if any breakdown key has no official-schema field
> mapping (defensive — should be unreachable for ITR-2 since the only such keys are
> business-income-linked sections ITR-2's own form scope excludes).
>
> **A second, related bug was found and fixed while implementing this**: `result.breakdown` only
> carries a clean per-section `"80C"` key once `_cap_breakdown_to_gti()`
> (`app/engine/schedules/deductions/__init__.py`) has actually run, which itself only happens when
> the *aggregate* GTI cap binds — the common case (deductions comfortably below GTI, most real
> returns) leaves the combined `"80C+80CCC+80CCD(1)"` key (the shared ₹1.5L section-80CCE ceiling
> amount) in the breakdown untouched instead. Naively treating that combined key as an
> unrepresentable section would have made every ordinary 80C claim raise the new `ValueError`
> above. Fixed by decomposing it the same way ITR-1's own already-working Schedule VIA builder does
> (`itd/itr1.py`'s `deduction()` closure): subtract whatever is separately recorded under
> `"80CCC"`/`"80CCD(1)"` from the combined figure to recover the 80C-only portion, avoiding
> double-counting a taxpayer who also separately claims 80CCC/80CCD(1).
>
> **Explicitly not attempted, documented as a known limitation in code**: `UsrDeductUndChapVIA` is
> meant to carry the taxpayer's own claimed (pre-cap) amount per section, distinct from
> `DeductUndChapVIA`'s post-cap amount. This codebase does not track a genuinely separate raw
> figure per section today — each of the ~20 section modules under
> `app/engine/schedules/deductions/` already applies its own statutory cap before returning
> `allowed_deduction`, and most sections are also bounded by the Pydantic input layer before compute
> ever runs — so both objects are populated from the same capped breakdown. This is an honest
> interim state (in every case this pipeline can currently produce, "claimed" and "allowed" already
> coincide), not a silent approximation; a genuinely separate raw-claim figure would need each
> section module to additionally report its own pre-cap input, a larger change not attempted here.
>
> Four regression tests added to `tests/test_itr2_itd_builder.py`
> (`test_schedule_via_serializes_real_per_section_amounts_not_only_a_total`,
> `test_schedule_via_omits_unclaimed_sections_and_matches_zero_deduction`, plus the two Schedule
> 115AD tests below, which exercise the same file) — the two VIA-specific tests confirmed via
> `git stash` (scoped to the four fix files, keeping the tests) to fail on pre-fix code: one with
> `KeyError`/wrong-value assertions, the other already passing pre-fix (a "still correct" check, not
> a bug-catching one). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` plus
> `test_draft_to_itr{1,2,4}_input*.py`/`test_filing_gateway_v2_itr{2,4}.py` regression suite: 791
> passed, the same 6 pre-existing failures as `HEAD` (all in `test_itr2_input_validation.py`/
> `test_filing_gateway_v2_itr2.py`, all HUF-verification-capacity and representative-capacity
> fixture/validator issues unrelated to Schedule VIA — confirmed via the same `git stash` to fail
> identically with or without this fix, i.e. pre-existing, not a regression).

## 8.0a None of the six dedicated Chapter VI-A detail schedules are built at all

**Evidence:** beyond the top-level `ScheduleVIA` aggregate (§8.0), the official schema defines six
further, fully independent top-level schedules for the deductions that require donee/insurer/
dependent-level disclosure: `Schedule80D` (health-insurance premium detail, with separate
self/family/senior-citizen/parent sub-blocks each carrying their own `Sch80DInsDtls[]` insurer
rows), `Schedule80G` (donation donee name/PAN/address/mode-of-payment rows, form p. 59),
`Schedule80GGA` (scientific-research/rural-development donation rows), `Schedule80GGC` (political
party contribution rows), `Schedule80DD` (dependent-with-disability rows, Form 10-IA references),
and `Schedule80U` (self-disability rows, Form 10-IA references) — form pp. 59-60. Grepped
`app/engine/itd/itr2.py` for every one of these six schedule names and for a `_schedule_80*`
function-naming pattern: **zero matches for all six** — none is ever constructed, referenced, or
emitted, regardless of what the taxpayer has claimed.

**Impact:** even after §8.0's `ScheduleVIA` fix populates the per-section capped/claimed amounts
correctly, a return claiming (say) a real 80G donation or 80D health-insurance premium would show
a non-zero `Section80G`/`Section80D` figure with **no corresponding detail schedule at all** to
substantiate it — the donee name, PAN, and payment-mode breakdown 80G disclosure exists for, or
the insurer/policy detail 80D disclosure exists for, is simply absent from the filed return. This
compounds §8.0's finding rather than duplicating it: §8.0 is about the aggregate schedule being
schema-invalid; this is about the six schedules that back up each aggregate figure with taxpayer-
identifying and payee-identifying detail not existing at all.

**Severity:** CRITICAL — six entire official schedules with zero implementation, affecting every
taxpayer who claims 80D (health insurance, extremely common) or 80G (donations, common) at
minimum.

**Remediation:** implement each of the six schedules from the canonical draft's already-existing
detail-row models (`Schedule80GGAEntry`/`Schedule80GGCEntry` are confirmed to already exist per
§8.1 below; check whether equivalent 80D/80G/80DD/80U row models exist yet, or need adding) —
substantial, multi-schedule work, reasonably split across several sittings by schedule rather than
attempted as one change, given the size of `Schedule80D`'s own nested structure alone.

> **Status (2026-09-09): still open — explicitly out of scope for §8.0's fix.** §8.0's fix (the
> `ScheduleVIA` aggregate) landed; this finding (the six separate detail schedules) was
> deliberately not attempted in the same pass, matching the "Schedule VIA" scope the fix was
> requested for — it is a materially larger body of work (six new typed models plus frontend UI
> plus six builder functions) than the single-function fix §8.0 needed. Tracked here as the
> concrete next step in this cluster.

> **Fix status (2026-09-09): fixed and verified — all six schedules built end-to-end.** Research
> before implementing found the scope was smaller than this finding's own remediation note
> assumed: the shared `app/engine/schedules/deductions/` eligibility engine (already used by
> `compute_deductions()` in `app/engine/calculators/itr2.py` for §8.0's own `ScheduleVIA` fix)
> already computes full per-section eligibility detail — per-insurer 80D policy rows, per-donation
> 80G/80GGA rows, per-contribution 80GGC rows, 80DD/80U disability detail — via the identical
> `compute_all()`/`section_80*.compute_details()` machinery ITR-1 already uses in production for
> the same six schedules (`app/engine/itd/itr1.py`'s `_schedule_80d/g/gga/ggc/dd/u()`, confirmed
> field-for-field identical against ITR-2's own official schema). The canonical draft
> (`app/schemas/return_draft.py`) already carries every needed structured field too
> (`Section80D`, `Donation80G`, `Schedule80GGAEntry`/`Schedule80GGCEntry`,
> `ChapterVIA.section80DD*`/`section80U*`), and the frontend's own `DeductionsWorkspace.tsx`
> already renders all of it (its own comment already anticipated ITR-2's extra
> `Form10IAFilingDate`/`FormAckNum11A` fields via a `fullForm10IA = form === 'ITR-2' || form ===
> 'ITR-3'` gate) — so this was purely a **backend wiring + builder** gap, not new frontend work,
> once traced end-to-end. Fixed by: (1) adding `schedule_80d`/`schedule_80gga`/`schedule_80ggc`/
> `schedule_80dd`/`schedule_80u` to `ITR2Input` (`app/schemas/itr2.py`) and wiring them from the
> draft in `app/engine/draft_to_itr2_input.py` via the same shared mapper functions
> (`_map_80d_schedule`/`_map_80gga`/`_map_80ggc`/`_map_disability_schedules`) ITR-1/ITR-4 already
> use; (2) fixing a real, previously-undetected bug found along the way in
> `app/engine/calculators/itr2.py`: `is_80dd_severe`/`is_80u_severe` were derived from
> `deductions_chapter6a.schedule_80dd`/`schedule_80u`, a nested field `_map_deductions()` never
> populates for either ITR-1 or ITR-2 — always `None`, making severity detection a dead branch
> that silently defaulted to non-severe regardless of the taxpayer's real selection; switched to
> the top-level `input_data.schedule_80dd`/`schedule_80u` fields ITR-1's own calculator actually
> reads; (3) adding six `_schedule_80*()` builder functions to `app/engine/itd/itr2.py`, adapted
> from ITR-1's proven implementation with two deliberate ITR-2-specific differences: Schedule80DD/
> 80U here also emit `Form10IAFilingDate`/`FormAckNum11A` (ITR-2/ITR-3-only schema fields —
> `DisabilityScheduleBase` in `app/schemas/itr1.py` gained two new optional fields to carry them,
> a safe additive change since ITR-1/ITR-4 simply never populate them), and Schedule80DD here
> allows an HUF-member dependent (ITR-1 rejects it since ITR-1 is individual-only; ITR-2 also
> files for HUF assessees, for whom this is a valid dependent per the official schema's own
> `DependentType` enum). One new comprehensive regression test in `tests/test_itr2_itd_builder.py`
> (`test_chapter6a_detail_schedules_serialize_real_claimed_data_end_to_end`, exercising all six
> schedules together against the real official schema) plus an omission-symmetry test
> (`test_chapter6a_detail_schedules_are_omitted_entirely_when_unclaimed`), both confirmed via
> `git stash` to fail against pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 825 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced).

---

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

## 9.3a Full form-order re-audit (2026-09-08) — Schedule AMTC's per-year credit rows use entirely wrong field names, and one total field holds a row count instead of an amount

Cross-referenced Schedule AMTC (form pp. 60-61) against schema `ScheduleAMTC`/`ScheduleAMTCDtls`
and `_schedule_amtc()` (`itd/itr2.py:2207-2241`).

### New finding — `ScheduleAMTCDtls` row keys don't match the schema at all

**Evidence:** the schema's per-year row type (`ScheduleAMTCDtls`) requires exactly `AssYr`
(enum-restricted to `"2013-14"` through `"2025-26"` — prior years only, matching the form's own
rows i-xiii), `Gross`, `AmtCreditSetOfEy`, `AmtCreditBalBroughtFwd`, `AmtCreditUtilized`,
`BalAmtCreditCarryFwd`. `_schedule_amtc()` instead emits `{"AssessmentYear": ...,
"AmtTaxCreditBF": ..., "TaxSection115JD": ..., "AmtTaxCreditUtilisedCY": ..., "AmtCreditCF":
...}` — **none of the five keys the code emits matches any of the six the schema defines**, and
`additionalProperties: false` means every one of them is independently rejected, on top of all
six required fields being absent. Every `ScheduleAMTCDtls` row is unconditionally schema-invalid.

Beyond the naming mismatch, the underlying data model may not carry enough information to fill
the correct fields even once renamed: the schema wants three *distinct* historical figures per
year (`Gross`, the year's original AMT-credit-generating amount; `AmtCreditSetOfEy`, how much of
it was already set off in earlier years; `AmtCreditBalBroughtFwd`, the resulting balance) but
`input_data.amt_input.amt_credits[].credit_brought_forward` appears to carry only one figure —
worth confirming when this is fixed whether the input schema needs extending, not just the
builder's key names.

### New finding — `TotSetOffEys` (a monetary total) is populated with a row count

**Evidence:** the schema confirms `TotSetOffEys` is `{"type": "integer", "minimum": 0, "maximum":
99999999999999}` with no count-like semantics — matching the form's own AMTC summary row "Total
of AMT credit set-off in earlier years" (a rupee total, the sum of every year's own
`AmtCreditSetOfEy`). `_schedule_amtc()` sets `"TotSetOffEys": len(rows)` — literally the *number*
of AMT-credit-year rows (e.g. `3` for three years of brought-forward credit), not a monetary sum
of anything. For a taxpayer with real prior set-off history, this field would show a small integer
(a row count, coincidentally sometimes a plausible-looking number) in place of the real rupee
total, an entirely wrong figure that happens to look superficially legitimate.

**Impact (both findings together):** any ITR-2 return with brought-forward AMT credit
(`amt_input.amt_credits` non-empty) produces a schema-invalid `Schedule AMTC` — a smaller
population than the VI-A deductions gap (§8.0) since AMT applies only to taxpayers who were
subject to Alternate Minimum Tax in a prior year, but a complete, unconditional failure for every
one of them.

**Severity:** CRITICAL (guaranteed schema rejection for the entire affected population, plus a
wrong-value bug on `TotSetOffEys` independent of the naming issue).

**Remediation:** rename every `ScheduleAMTCDtls` row key to the schema's own names, source
`Gross`/`AmtCreditSetOfEy` from the input model (extending `AMTCredit` if those figures aren't
captured separately from the brought-forward balance today), and change `TotSetOffEys` to
`sum(row["AmtCreditSetOfEy"] for row in rows)`. Add a schema-validating regression test — as with
§8.0, this class of bug (plausible-looking but entirely wrong field names) is exactly what a real
`Draft4Validator` assertion catches immediately and a hand-inspected dict does not.

> **Fix status (2026-09-09): fixed and verified, with the data-model gap resolved honestly rather
> than deferred.** `_schedule_amtc()` (`itd/itr2.py`) now emits all six real field names
> (`AssYr`/`Gross`/`AmtCreditSetOfEy`/`AmtCreditBalBroughtFwd`/`AmtCreditUtilized`/
> `BalAmtCreditCarryFwd`) on every row. Confirmed the underlying data-model gap this finding
> flagged as worth checking: `AMTCreditItem` does only carry one figure per year
> (`credit_brought_forward`), with no separate original-year `Gross` or already-set-off-in-earlier-
> years figure anywhere in this codebase. Rather than extend the schema (a larger, UI-touching
> change), the fix uses an honest degenerate mapping — `Gross = AmtCreditBalBroughtFwd =
> credit_brought_forward`, `AmtCreditSetOfEy = 0` — which keeps the schema's own implied identity
> (`Gross - AmtCreditSetOfEy == AmtCreditBalBroughtFwd`) exactly true, matches §8.0's
> `UsrDeductUndChapVIA`/`DeductUndChapVIA` fix's precedent for the same "one figure standing in for
> several, documented, not silently wrong" situation, and correctly makes `TotSetOffEys` genuinely
> `0` (a real, honest monetary sum — not the previous `len(rows)` row count, and not a fabricated
> nonzero total either).
>
> **A second, separate, more severe bug was found and fixed in the same pass, not previously
> documented anywhere in this doc**: for a return with *more than one* year of brought-forward AMT
> credit, the previous code computed each row's `AmtTaxCreditUtilisedCY` as
> `min(credit.credit_brought_forward, result.amt_tax)` — applying the *full* current-year AMT-tax
> offset capacity (`result.amt_tax`) independently to every single row, rather than tracking how
> much of that capacity earlier rows had already consumed. For two credit years each smaller than
> `result.amt_tax`, this double-counted (or worse, N-counted) the same offset capacity across every
> row — a real overstatement of AMT credit utilized, not merely a naming/schema-validity issue.
> Fixed by processing years oldest-first (FIFO, sorted by `assessment_year` — matching the official
> form's own chronological row ordering) against a single `remaining_capacity` accumulator
> decremented as each row consumes it, so a later (newer) row only ever receives what's left over.
>
> **A third, smaller gap also closed**: the schema's `AssYr` enum is a closed set of 13 specific
> prior years (`"2013-14"`–`"2025-26"`) — `AMTCreditItem.assessment_year`'s Pydantic pattern
> (`^20[0-9]{2}-[0-9]{2}$`) is far broader and would accept an out-of-range year (including the
> current AY, which belongs in `ScheduleAMT` instead) without complaint. `_schedule_amtc()` now
> raises a clear `ValueError` naming the invalid year rather than silently producing schema-invalid
> JSON, matching the fail-loud discipline already established elsewhere in this file (Schedule FA's
> ownership-status checks, §8.0's VIA unmapped-section check).
>
> Three regression tests added to `tests/test_itr2_itd_builder.py`:
> `test_schedule_amtc_uses_correct_official_field_names_and_schema_validates`,
> `test_schedule_amtc_applies_fifo_across_multiple_years_not_double_counting` (two years of credit
> supplied out of chronological order in the fixture, confirming the builder still sorts oldest-
> first: the older year absorbs its full ₹900,000 before the newer year receives only the
> ₹160,316 actually left over — a pre-fix run would have wrongly given the newer year its full
> ₹500,000 too), and `test_schedule_amtc_rejects_out_of_range_assessment_year`. All three confirmed
> via `git stash` (scoped to `itd/itr2.py`) to fail on pre-fix code. Full combined `test_itr1_*`/
> `test_itr2_*`/`test_itr4_*` regression suite: 797 passed, the same 6 pre-existing failures as
> `HEAD` (see §8.0's fix note for the list; unrelated to this change).

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

> **Fix status (2026-09-05): a severe, universal correctness bug found and fixed in Schedule FSI;
> the completeness gap this item describes remains open.** See §10.2's "Update" note for the full
> write-up (found while fixing the country-code issue documented there): `_schedule_fsi()` was
> serializing its five per-head income fields as plain integers when the official schema requires
> each to be a nested tax-breakdown object, plus three fabricated top-level fields with no schema
> basis at all — every Schedule FSI disclosure this builder ever produced was schema-invalid.
> Fixed and regression-tested. Schedule TR1 had no equivalent structural defect (its fields were
> already correctly-shaped plain scalars) — only its own `CountryName`-based row-matching bug,
> also fixed in the same pass. The category/treaty/conversion/Form-67/timing/limitation detail
> this item describes is unaffected and remains open.

> **New finding (full form-order re-audit, 2026-09-08): the `countryCode` field for FSI, TR, and
> FA is unconstrained free text — no dropdown, no validation, no guidance toward the exact numeric
> code the schema requires.** `ITR2SchedulesWorkspace.tsx`'s shared `controlFor()` (line 80) picks
> a `<select>` only for keys listed in its `options` map (`head`, `reliefSection`, `assetType`,
> `incomeHead`, `section`) — `countryCode` is not among them, so it falls through to the generic
> `<input type="text">` branch at line 97, for all three of `createForeignSourceIncomeEntry()`
> (FSI), `createForeignTaxReliefEntry()` (TR), and `createForeignAssetEntry()` (FA). The schema's
> `CountryCodeExcludingIndia` field these all map to is a closed 249-value enum of specific numeric
> strings (`"2"` for USA, `"44"` for UK, etc., per §4's `JurisdictionResidence`-family evidence
> earlier in this document) — a preparer has no way to discover or correctly enter these values
> through a plain text box, and would naturally type a country *name* instead, which the schema
> would reject outright. This is a different, more severe manifestation of the same root problem
> as §4's `ITD_COUNTRY_CODES` finding (`PersonalInfoTab.tsx`/`HousePropertyEntryManager.tsx` at
> least offer a dropdown, just an imperfect one) — here there is no dropdown backing the field at
> all, for three entire schedules covering all foreign income/asset disclosure.
>
> **Severity:** High (near-certain schema rejection for any real foreign-income/asset entry made
> through this UI, though it is confined to the FSI/TR/FA path specifically and does not corrupt
> data already entered correctly by a preparer who happens to know the numeric codes).
>
> **Remediation:** add `countryCode: ITD_COUNTRY_CODES` (or its `CountryCodeExcludingIndia`-correct
> variant, once §4's finding splits the list) to `controlFor()`'s `options` map so FSI/TR/FA gain
> the same dropdown `PersonalInfoTab.tsx` already has, closing this and §4's finding together in
> one pass since they share the same underlying fix.

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

> **Fix status (2026-09-05): the three categories with a real code path (bank account, immovable
> property, other asset) were producing invalid or wrong data and are now fixed and
> schema-correct; the other seven categories remain genuinely unbuilt and now fail closed instead
> of being silently misclassified.**
>
> Writing the first-ever Schedule FA tests found `_schedule_fa()` (`itr2.py:1815`) was far more
> broken than "under-modeled": two of its three implemented branches were producing
> **schema-invalid JSON on every single row**, not merely incomplete detail.
>
> 1. **Bank accounts (`DetailsForiegnBank`)**: field names were correct, but `"ZipCode":
>    item.account_or_asset_identifier[:8]` used the first 8 characters of the **account number**
>    as the postal code, because `ForeignAssetEntry` had no dedicated zip field at all. Schema-valid
>    (any short string satisfies `ZipCode`'s pattern) but entirely fabricated data.
> 2. **Immovable property (`DetailsImmovableProperty`)**: the code emitted `AddressOfProp`,
>    `DateOfImp`, `PeakValueOfProp`, `IncFromProp` — **none of which are valid property names**
>    for the official type (the real names are `AddressOfProperty`, `TotalInvestment`,
>    `IncDrvProperty`, with no `DateOfImp` field at all) — and omitted `Ownership`, `NatureOfInc`,
>    `IncTaxAmt`, `IncTaxSch`, `IncTaxSchNo` entirely, all of which are required.
>    `additionalProperties: false` means every prior immovable-property disclosure was rejected.
> 3. **"Other assets" (`DetailsOthAssets`)**: the code emitted `NameOfInst`, `AddressOfInst`,
>    `AcctNumOrIdtyNum`, `OwnerStatus`, `PeakBalanceDuringYear`, `ClosingBalance`, `IncFromOthSrc`
>    — **none of which are valid property names** for this type either (the real names are
>    `NatureOfAsset`, `Ownership`, `TotalInvestment`, `IncDrvAsset`, `NatureOfInc`, `IncTaxAmt`,
>    `IncTaxSch`, `IncTaxSchNo`). Wrong properties present, every required property absent — the
>    most severe of the three.
> 4. **All ten categories' `else`-branch fallback**: any asset type other than bank account or
>    immovable property (custodial account, equity/debt interest, insurance, financial interest,
>    signing authority, trust, other foreign-sourced income) was silently folded into
>    `DetailsOthAssets` — misclassifying it into the wrong official category entirely, not just
>    omitting detail (a custodial account disclosed as a generic "other asset" is a different
>    factual claim to ITD, not a subset of one).
>
> **Fix**: added `zip_code` (required), `nature_of_asset`, `nature_of_income`, and
> `income_tax_schedule_item_no` to `ForeignAssetEntry` (`app/schemas/itr2.py`); corrected all
> field names for immovable property and other-asset rows to the real schema names; added
> `Ownership`/`OwnerStatus` enum validation (bank accounts use `OWNER`/`BENEFICIAL_OWNER`/
> `BENIFICIARY`, every other category uses `DIRECT`/`BENEFICIAL_OWNER`/`BENIFICIARY` — two
> different enums for what looks like the same concept); the `else` branch now raises a clear
> `ValueError` naming the unsupported category instead of misclassifying it. Also fixed the v2
> pipeline's `_map_foreign_assets()` (`app/engine/draft_to_itr2_input.py`), which defaulted
> `ownership_status` to the wrong-case `"Owner"` regardless of category (now `"OWNER"` for bank
> accounts, `"DIRECT"` otherwise, matching the real enums) and had no way to supply the three new
> fields at all — added `zipCode`/`natureOfAsset`/`natureOfIncome`/`incomeTaxScheduleItemNo` to
> the draft-side `ForeignAssetEntry` (`app/schemas/return_draft.py`) and wired them through.
>
> Five regression tests added to `tests/test_itr2_itd_builder.py`, each confirmed via `git stash`
> to fail pre-fix (three with a `ForeignAssetEntry` construction error alone, since `zip_code`
> didn't exist as a field before this fix). Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` suite
> green (633 passed); `test_draft_to_itr2_input.py`/`test_return_draft_schema.py` checked directly
> (44 passed, no regression).
>
> **Still open**: the other seven official categories (custodial account, equity/debt interest,
> insurance, financial interest, signing authority, trust, other foreign-sourced income) each need
> their own typed input model — the official schema requires fields this generic
> `ForeignAssetEntry` has no equivalent for (e.g. equity/debt's `InitialValOfInvstmnt`/
> `TotGrossProceeds`, insurance's `ContractDate`/`CashValOrSurrenderVal`, trust's settlor/trustee/
> beneficiary names) — plus frontend UI for all ten categories (currently one generic form).
> Building these out is a genuinely large, multi-category feature addition, not a bug fix; it now
> fails closed with a clear message instead of silently misclassifying, which is the safe interim
> state until each category is built. The immovable-property and other-asset frontend forms also
> have no fields yet for `nature_of_income`/`nature_of_asset`/`income_tax_schedule_item_no` — a
> v2-pipeline taxpayer entering either asset type today will get a clean, informative
> `FilingGatewayV2Error` (via `filing_gateway_v2.py`'s existing exception handling) rather than a
> silent schema-invalid submission, until that frontend work lands.
>
> **Update (2026-09-05): the systemic `country_code`/`CountryName` issue is fixed.** `country_code`
> on `ForeignAssetEntry`/`FSICountryEntry`/`TR1Entry` was passed as BOTH `CountryName` (a free-text
> name) and `CountryCodeExcludingIndia` (one specific ITD-bespoke numeric code from a 249-entry
> enum, e.g. `"2"` for USA, `"44"` for the UK — not ISO alpha or numeric-3) using the exact same
> raw value for both fields. **Correction to this note's own earlier claim**: `OSDtaaEntry` was
> misidentified as part of this systemic issue — re-checking found it already has a genuinely
> separate `country_name` field, correctly used for `CountryName` alongside `country_code` for
> `CountryCodeExcludingIndia` (`app/engine/itd/itr2.py`'s OS-DTAA block); it was never broken.
>
> Fixed by transcribing the schema's own `CountryCodeExcludingIndia` enum + description (249
> entries, cross-checked pair-for-pair against the enum list, not just the description text) into
> `app/engine/itd/country_codes.py`'s `ITD_COUNTRY_CODE_TO_NAME` lookup table, then deriving
> `CountryName` from it (`country_name(item.country_code)`) at all three real sites (Schedule FA's
> three asset-type branches, Schedule FSI, Schedule TR1) instead of reusing the raw code. An
> unrecognized code now raises a clear error naming it, rather than silently passing through
> whatever string was supplied (this is a closed official enum, not free text). Also fixed
> Schedule TR1's own DTAA/non-DTAA relief aggregation, which matched rows via `e.country_code ==
> r["CountryName"]` — harmless only because `CountryName` used to equal the raw code too; now
> compares against `CountryCodeExcludingIndia` instead.
>
> Confirmed the real frontend is unaffected: `frontend/src/constants/itdCountryCodes.ts` already
> has the identical 249-entry ITD code list wired to a proper dropdown for House Property and
> Personal Info address fields (confirming the codebase's own established convention that
> `country_code` fields hold ITD's numeric codes, not ISO alpha) — but the currently-shipped
> generic Schedule FSI/TR/FA workspace (`ITR2SchedulesWorkspace.tsx`) renders `countryCode` as a
> plain text field with no dropdown at all, so a real user typing e.g. `"USA"` there would already
> have produced schema-invalid JSON before this fix (via `CountryCodeExcludingIndia`'s own enum
> constraint) — this fix surfaces that with a clear, actionable error instead of a confusing
> downstream schema-validation failure; it does not newly block anything that previously worked.
> Wiring the same `ITD_COUNTRY_CODES` dropdown into the generic FSI/TR/FA workspace is a real,
> separate frontend-completeness gap, logged here but not fixed in this pass.
>
> **Separately discovered, unrelated to country codes, and fixed in the same pass**: writing the
> first-ever schema-validating test for Schedule FSI found `_schedule_fsi()` was serializing
> `IncFromSal`/`IncFromHP`/`IncCapGain`/`IncOthSrc`/`TotalCountryWise` as plain integers, when the
> official schema requires each to be a NESTED object (`ScheduleFSIIncType`/
> `TotalScheduleFSIIncType`: `IncFrmOutsideInd`/`TaxPaidOutsideInd`/`TaxPayableinInd`/
> `TaxReliefinInd`) — and was separately emitting three fabricated top-level fields
> (`TaxPaidOutsideIndia`/`TaxPayableInIndia`/`TaxReliefAvailable`) that do not exist in the real
> schema at all. With `additionalProperties: false` and all five nested objects required, **every
> Schedule FSI disclosure this builder has ever produced was schema-invalid** — a universal defect
> for any taxpayer with foreign-source income, undiscovered only because Schedule FSI had zero
> test coverage before this pass. Fixed by restructuring each row into the correct nested shape;
> since `FSICountryEntry` carries only one tax-paid/payable figure per jurisdiction (not per income
> head), the per-head tax breakdown is attributed to a specific head only when exactly one head has
> nonzero income for that country — the same single-attributable-source precedent already
> established for Schedule S's per-employer perquisites — with every other head correctly reporting
> zero tax rather than a guessed split. `TotalCountryWise` (the aggregate row) is unambiguous and
> always uses the real jurisdiction-level figures.
>
> Four regression tests added to `tests/test_itr2_itd_builder.py`
> (`test_schedule_fa_fsi_tr_derive_real_country_name_from_the_code`,
> `test_schedule_fa_rejects_unrecognized_country_code`,
> `test_schedule_fsi_income_fields_are_nested_tax_objects_not_plain_integers`, plus the earlier
> Schedule FA tests re-verified against real country names), each confirmed via `git stash` to fail
> pre-fix. Full `test_itr1_*`/`test_itr2_*`/`test_itr4_*` plus every non-glob-matching sibling file
> green: 787 passed.

---

# 11. Schedule SPI and PTI

## 11.1 SPI is compressed to a generic clubbing row

The frontend exposes name, PAN, relationship, amount, and head around `ITR2SchedulesWorkspace.tsx:121`, but not the complete section 64 clause, source-income, loss, and schedule-linkage structure.

**Severity: Medium to High**

> **Full form-order re-audit (2026-09-08): the top-level wiring is confirmed correct**
> (`_schedule_spi()`, `itd/itr2.py:2248-2263`, correctly wraps rows under the schema's actual key
> `"SpecifiedPerson"` — a genuine schema-name match, unlike §8.0/§9.3a's findings elsewhere in this
> re-audit — and every row field name matches `SpecifiedPerson`'s schema definition exactly). Two
> narrower gaps found on top of this section's existing "compressed" framing:
> - `SPIEntry.head_of_income` (`app/schemas/itr2.py:612`) is typed `Literal["SAL", "HP", "CG",
>   "OS"]` — the schema's own `HeadIncIncluded` enum additionally allows `"EI"` (Exempt Income),
>   which this model simply cannot represent. A specified person's clubbed exempt income (e.g. a
>   minor child's exempt interest) has no way to be disclosed under the correct head.
> - `SPIEntry` has no Aadhaar field at all, only `pan: Optional[str]` — the schema's
>   `AaadhaarOfSpecPerson` (sic, the official schema's own spelling) provides for a specified
>   person identified by Aadhaar instead of PAN, which this model cannot represent either.
> - `SPIEntry.amount_included: Decimal = Field(..., ge=0)` is more restrictive than the schema's
>   `AmtIncluded` (`minimum: -99999999999999` — negative values, i.e. clubbed losses, are
>   schema-legal). Narrow in practice (a clubbed loss is an unusual case) but worth noting given
>   this document's explicit brief to check minimum/maximum bounds.
>
> **Severity of these three:** Medium (narrow taxpayer populations: EI-head clubbing,
> Aadhaar-only specified persons, and clubbed losses are all uncommon relative to the section's
> ordinary PAN-identified salary/HP/CG/OS clubbing case, which is fully correct).
>
> **Separately flagged, not resolved here:** `_schedule_si()` (`itd/itr2.py:1828-1895`) explicitly
> excludes internal section `"111"` (accumulated PF) from `SplCodeRateTax` rows, with a comment
> reasoning that "the official schema's `SplRatePercent` enum has no 0 value." But the schema's own
> `SecCode` enum explicitly defines `"1"` for exactly *"111 - Tax on accumulated balance of
> recognised PF"*, and the official form itself lists it as SI row 1 (pulling from Schedule OS's
> `2ciii`/`2civ` cells) with no printed flat percentage — Section 111 is taxed via an "average
> rate" mechanism (Rule 1, Part A, Fourth Schedule), not a flat rate, so the row likely still
> belongs in the table with whatever real average-rate percentage the calculator would compute,
> not literally excluded. This needs the calculator's own PF-average-rate logic traced to confirm
> before concluding either way — flagged rather than resolved, since it's a computation-semantics
> question (out of proportion to the remaining scope of this pass) rather than a clear-cut
> serialization gap.

## 11.2 PTI is compressed

The frontend exposes entity name/PAN, income head, section, income amount, and TDS credit around line 122, but this is insufficient for all pass-through income distinctions and credit linkage.

**Severity: High for affected taxpayers**

> **Full form-order re-audit (2026-09-08): the JSON-builder layer itself is confirmed correct, no
> new finding.** Checked `_schedule_pti()` (`itd/itr2.py:2270-2305`) key-by-key against schema
> `SchedulePTIDtls`/`SchedulePTIType`/`SchedulePTITypeOS23FBB` — every field name matches exactly
> (`InvstmntCvrdUs115UA115UB`, `BusinessName`/`BusinessPAN`, `IncFromHP`, the full
> `CapitalGainsPTI` nested block with `ShortTermCG`/`STCG_Sec111A`/`STCG_Others`/`LongTermCG`/
> `LTCG_Sec112A`/`LTCG_Others`, `IncOthSrc`/`OS_Dividend`/`OS_Others`), including the subtle
> distinction that `SchedulePTITypeOS23FBB` (used for the OS/exempt blocks) requires only 3 fields
> while `SchedulePTIType` (used for HP/CG) requires 4 (`CurrYrLossShareByInvstFund` additionally)
> — the code's two separate helper functions (`regular()`/`other()`) already match this exactly.
> This section's existing "compressed" framing is about upstream data richness (§11.2's own
> point — the frontend/`PTIEntry` model can't distinguish 111A-STT-paid STCG from other STCG, or
> 112A from other LTCG, since `PTIEntry.income_head` is only `Literal["HP", "STCG", "LTCG",
> "OS"]`), which is real and unchanged, not a JSON-builder gap.
>
> One narrower, newly-confirmed gap: `IncClmdPTI.TotalSec23FBB`/`Sec23FBB` (Section 10(23FBB)
> exempt pass-through income) are unconditionally hardcoded to zero — `PTIEntry` has no field for
> exempt PTI income at all, matching the same "no input capture" pattern as several other findings
> in this document. Severity Medium (a narrower sub-case of pass-through income specifically).

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

> **Full form-order re-audit (2026-09-08): §12.1's/§12.2's own points are confirmed still
> accurate.** `_schedule_5a()` (`itd/itr2.py:2312-2332`) correctly matches every field name in
> schema `Schedule5A2014`/`Sch5AIncType` — no new bug found in the JSON builder itself. One item
> worth verifying in a future pass, not confirmed either way here: the builder derives each head's
> total receipts as exactly double the spouse's own apportioned share (`amount * 2`), which
> presumes an exact 50/50 apportionment always — plausible given Portuguese Civil Code's
> community-property default, but not verified against whether the input model can represent an
> unequal split if one legitimately exists.

---

# 12a. Schedule AL — Assets and Liabilities

## 12a.1 Full form-order re-audit (2026-09-08) — immovable-property disclosure is captured but never serialized

Cross-referenced Schedule AL (form p. 66) against schema `ScheduleAL`/`MovableAsset`/
`ImmovableDetails` and `_schedule_al()` (`itd/itr2.py:2169-2187`). Not previously covered anywhere
in this document.

**Confirmed correct:** every one of `MovableAsset`'s 8 required fields
(`CashInHand`/`DepositsInBank`/`SharesAndSecurities`/`InsurancePolicies`/
`LoansAndAdvancesGiven`/`JewelleryBullionEtc`/`ArchCollDrawPaintSulpArt`/
`VehiclYachtsBoatsAircrafts`) is correctly named and populated from real input.

### New finding — `AssetLiabilityInput.immovable_property` is captured but `ImmovableDetails` is always emitted empty

**Evidence:** `AssetLiabilityInput` (`app/schemas/itr2.py:648-660`) has a real
`immovable_property: Decimal = Field(default=Decimal("0"), ge=0)` field — but `_schedule_al()`
never reads it; the function unconditionally sets `"ImmovableDetails": []` regardless of its
value. A taxpayer who owns land or a building and has total income exceeding ₹1 Crore (the
threshold that makes Schedule AL applicable at all) would have their real, captured immovable-
property value silently omitted from the one schedule that exists specifically to disclose it.

**A direct fix is smaller than it looks, but not free**: the schema's `ImmovableDetails` row
requires `Description` (maxLength 25) and a full `AddressAL` object alongside `Amount` — all
required — but the input model captures only a single aggregate rupee figure, with no per-property
description or address. A correct fix needs either extending `AssetLiabilityInput` to a real
per-property list (matching how House Property's own multi-row model works), or — as a narrower
interim fix — emitting one synthetic row with a generic description when the aggregate is
non-zero, accepting that it under-discloses property count/location detail.

**Impact:** every taxpayer with both real immovable property and >₹1 Crore income (Schedule AL's
own applicability threshold) files an incomplete Schedule AL — a real, visible gap for the exact
population this schedule exists to serve, though narrower in reach than the VI-A findings (§8.0/
§8.0a) since Schedule AL only applies above the ₹1 Crore threshold at all.

**Severity:** High (a real, captured value silently dropped, for a schedule that specifically
targets higher-income taxpayers already more likely to draw scrutiny).

**Remediation:** at minimum, emit one `ImmovableDetails` row (`Description: "Immovable property"`,
`Amount: immovable_property`, `AddressAL` populated from the taxpayer's own primary address as a
placeholder) when `immovable_property > 0`, and track proper per-property capture as a follow-up
UI/schema improvement.

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

   > **Fixed 2026-09-05** — see §6.1/§6.2's fix write-ups. The correctness bug (self-occupied
   > interest reported uncapped; `RentNotRealized`/`ArrearsUnrealizedRentRcvd`/per-row `IncomeOfHP`
   > silently recomputed instead of read from the real calculator result) is fixed. Section 24(b)
   > loan-lender detail rows, co-owner rows, and tenant rows are now backed by real typed models
   > and wired end-to-end through the v2 pipeline — the frontend UI for all three already existed
   > (`HousePropertyEntryManager.tsx`) and was being silently discarded before this fix, not
   > actually missing. Pre-construction interest amortization and property completion date/status
   > remain out of scope (the official schema has no dedicated fields for either within
   > `Section24BDtls`).

8. Replace generic Schedule FA rows with category-specific foreign bank, custodial, equity/debt, insurance, trust, signing-authority, property, and other-asset editors and serializers.

   > **Partially fixed 2026-09-05** — see §10.2's fix write-up. Two of the three implemented
   > categories (immovable property, other assets) were producing schema-INVALID JSON on every
   > row (wrong field names, required fields missing), not just incomplete detail; the third (bank
   > account) had a fabricated ZipCode. All three are now schema-correct and regression-tested.
   > The other seven categories still need dedicated typed models and UI — they now fail closed
   > with a clear error instead of being silently misclassified as generic "other assets."

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

    > **Substantially fixed 2026-09-05** — see §5.4's fix write-up and its "Update" note.
    > Perquisites, profits in lieu, the full Section 10 exemption breakdown (gratuity, leave
    > encashment, VRS, retrenchment, transport, children-education, hostel, uniform, LTA), and
    > Section 89A relief are now all real, sourced from the calculator's already-computed
    > `SalaryResult` (previously hardcoded to zero/empty) — confirmed already reachable end-to-end
    > from the real frontend via the shared `_map_salary()` mapper, no v2-pipeline changes needed.
    > Still open: `NatureOfSalary`/`NatureOfPerquisites` per-category detail arrays (only aggregate
    > totals exist in the input schema) and the full `Section10_13A` HRA structure (raw rent/city
    > components, not just the computed exempt amount) — both need new input schema fields, not
    > just a builder fix; multi-employer per-perquisite attribution also needs a schema redesign.

## P2 — Quality and maintainability

12. Replace frontend monetary `number` values with decimal strings.

13. Add populated-data preservation tests for every canonical category.

14. Add semantic reconciliation between canonical input, prepared input, calculator result, and CBDT JSON.

15. Add explicit unsupported-case errors instead of silently omitting data.

---

# 18a. Part B-TI and Part B-TTI — total income and tax-liability computation

## 18a.1 Full form-order re-audit (2026-09-08) — not previously covered in this document

Cross-referenced Part B-TI (form pp. 67-68) against `_partb_ti()` (`itd/itr2.py:2580-2629`) and
Part B-TTI (form pp. 68-69) against `_partb_tti()` (`itd/itr2.py:2636-2719`). Confirmed the
bottom-line figures that actually determine tax payable — `TotalIncome`/`TotalTI`
(`_to_rupees_rounded10(result.taxable_income)`), `NetTaxLiability`, `GrossTaxLiability`,
`AdvanceTax`/`TDS`/`TCS`/`SelfAssessmentTax`, `RefundDue` — are all sourced directly and correctly
from the calculator's own `ITR2Result` fields, independent of the sub-block issues below, so none
of these findings put the actual amount payable/refunded at risk. The issues found are in
disclosure sub-blocks that either duplicate or feed into those bottom-line figures.

### New finding — Part B-TI's `ShortTerm20Per`/`ShortTermAppRate` are swapped, and `ShortTerm30Per` is always zero

**Evidence:** `app/engine/calculators/itr2.py:319-320`, `_post_loss_cg_baskets()`, defines:
```python
normal_stcg = cyla.stcg30_remaining   # 30% normal-rate STCG
section_111a = cyla.stcg20_remaining  # 20% 111A STCG
```
— i.e. the dict key `"normal_stcg"` holds the **30%/slab-rate** bucket and `"111a"` holds the
**20%-flat** bucket (matching Schedule SI's own rate table: 111A/115AD(1)(b)(ii) proviso = 20%;
the FII-specific 115AD(1)(ii) STT-not-paid bucket = 30%; everything else = slab/"applicable"
rate). `_partb_ti()` then does:
```python
stcg_20 = _to_rupees(post_loss.get("normal_stcg", _ZERO))   # <- actually the 30%/slab bucket
stcg_111a = _to_rupees(post_loss.get("111a", _ZERO))        # <- actually the 20% bucket
...
"ShortTerm20Per": stcg_20,        # gets the 30%/slab-bucket value
"ShortTerm30Per": 0,              # hardcoded, never receives normal_stcg for FII/FPI
"ShortTermAppRate": stcg_111a,    # gets the real 20%-bucket (111A) value
```
So `ShortTerm20Per` (should hold 111A income) actually holds the ordinary/slab-rate bucket, and
`ShortTermAppRate` (should hold ordinary/slab-rate income) actually holds the 111A bucket — the
two are swapped. Separately, `ShortTerm30Per` — the field that should hold an FII/FPI's real
115AD(1)(ii) 30%-flat STCG (confirmed to exist and be correctly *taxed*, via
`compute_115ad_stcg_other(post_loss_cg["normal_stcg"])`, per §3.1's fix write-up) — is
unconditionally `0`, so that disclosure never appears here regardless of taxpayer status. This
extends the forward-pointer left in §3.9 during the Schedule CG re-audit.

**Correctness note:** `TotalShortTerm = stcg_20 + stcg_111a` is simple addition, so the *sum* is
unaffected by which named field holds which addend, and `GrossTotalIncome`/`TotalIncome` are
independently sourced from the calculator's own totals (confirmed above) — so tax payable is not
at risk. This is a disclosure-correctness bug: the per-rate-bucket breakdown a reviewer or the
taxpayer themselves would read off this JSON is definitively wrong for both an ordinary taxpayer
(111A vs. slab-rate STCG swapped) and an FII/FPI taxpayer (30%-bucket income invisible).

**Severity:** High (disclosure-correctness, not amount-correctness — matches this document's
convention of rating swapped/wrong sub-fields below CRITICAL when the bottom-line total is
independently sourced and unaffected).

**Remediation:** `ShortTerm20Per = post_loss.get("111a")`; `ShortTermAppRate =
post_loss.get("normal_stcg")` when not FII/FPI, else `0`; `ShortTerm30Per =
post_loss.get("normal_stcg")` when FII/FPI, else `0` (mirroring how `_schedule_cg()` itself
already branches on `is_fii_fpi` for the equivalent Schedule CG fields).

> **Fix status (2026-09-09): fixed and verified.** `_partb_ti()` (`app/engine/itd/itr2.py`) now
> takes `input_data` as well as `result`, computes `is_fii_fpi` the same way `_schedule_cg()`/
> `_schedule_115ad()` already do, and routes exactly as remediated: `ShortTerm20Per` always reads
> the true `"111a"` basket; `ShortTermAppRate` reads `"normal_stcg"` unless `is_fii_fpi`, in which
> case it is `0`; `ShortTerm30Per` reads `"normal_stcg"` only when `is_fii_fpi`, else `0`. Two new
> regression tests in `tests/test_itr2_itd_builder.py`
> (`test_partb_ti_short_term_buckets_are_not_swapped_for_ordinary_taxpayer`,
> `test_partb_ti_short_term_30per_receives_fii_fpi_normal_rate_stcg`), confirmed via `git stash` to
> fail against pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression
> suite: 804 passed, only the same 6 pre-existing failures (unrelated to this fix, not newly
> introduced).

### New finding — `AssetOutIndiaFlag` (Part B-TTI, required) is hardcoded `"NO"`, directly contradicting a populated Schedule FA

**Evidence:** the schema marks `AssetOutIndiaFlag` required on `PartB_TTI`, with description *"It
is to know if the assessee has any interest in any asset/signing authority in any account located
outside India"* — exactly the form's own item 19 question, which explicitly instructs *"Ensure
Schedule FA is filled up if the answer is Yes"*. `_partb_tti()` sets `"AssetOutIndiaFlag": "NO"`
unconditionally (`itd/itr2.py:2708`), with no reference to `input_data.foreign_assets` anywhere in
the function. Any taxpayer with real Schedule FA entries — already confirmed correctly serialized
for bank accounts, immovable property, and other assets in §10.2 — would file a return where
Schedule FA is populated but Part B-TTI's own flag says "No foreign assets," a direct, checkable
self-contradiction between two parts of the same JSON.

**Severity:** CRITICAL (required field, unconditionally wrong whenever Schedule FA is populated,
and directly contradicts a schedule the form itself cross-references by name).

**Remediation:** `"AssetOutIndiaFlag": "YES" if input_data.foreign_assets else "NO"`.

> **Fix status (2026-09-09): fixed and verified.** `_partb_tti()` now sets
> `"AssetOutIndiaFlag": "YES" if input_data.foreign_assets else "NO"`. Regression test
> `test_asset_out_india_flag_reflects_real_schedule_fa_presence` (`tests/test_itr2_itd_builder.py`)
> asserts both directions (populated Schedule FA → `"YES"`, none → `"NO"`), confirmed via `git
> stash` (scoped to `itd/itr2.py`) to fail on pre-fix code. Full combined `test_itr1_*`/
> `test_itr2_*`/`test_itr4_*` regression suite: 793 passed, the same 6 pre-existing failures as
> `HEAD` (see §8.0's fix note for the list; unrelated to this change).

### ~~New finding — `"GrossTaxPayable"` is not a real schema key~~ — retracted, this finding was wrong

**Retraction (2026-09-09):** re-checked directly against the schema before attempting to fix this
finding, and it does not hold. `GrossTaxPayable` **is** a real, and in fact **required**, property
of `PartB_TTI.ComputationOfTaxLiability` — `{"type": "integer", "minimum": 0, "maximum":
99999999999999, "default": 0}`, present in `ComputationOfTaxLiability.required` alongside
`GrossTaxPay` (a separate, correctly-named, unrelated field for eligible-startup ESOP-deferred-tax
figures — both objects genuinely coexist in the schema, confirmed by direct property-list lookup).
The original audit pass's claim that `GrossTaxPayable` "does not exist anywhere in the schema" was
a research error — attempting the fix by deleting the key immediately surfaced this via a live
`Draft4Validator` failure (`'GrossTaxPayable' is a required property`) before it was committed.
Left here, struck through, as a record rather than silently removed — the correction is the
important part, not hiding that the miss happened.

**What was actually wrong, and what was fixed**: `GrossTaxPayable` was present but hardcoded to
`0` — the real bug, just misdiagnosed as "the key shouldn't exist" rather than "the key's value is
wrong." Per the form's own item 8 ("Gross tax payable (higher of 1d and 7)"), it should be
`max(TaxPayDeemedTotIncUs115JC, GrossTaxLiability)` — a `0` value directly contradicted its own
sibling field `GrossTaxLiability` one line above on every return with any tax liability at all
(the exact "sibling fields must agree" pattern this document keeps finding across schedules).

> **Fix status (2026-09-09): fixed and verified, scoped honestly.** `GrossTaxPayable` is now
> `max(tax_payable_deemed_total_income, _to_rupees(result.gross_tax_liability))`, where
> `tax_payable_deemed_total_income` is the same local value the function already used (and still
> uses) for the top-level `TaxPayDeemedTotIncUs115JC` field — item "1d" itself, which this builder
> does not yet compute (a separate, already-tracked gap — see the `CreditUS115JD`/
> `TaxPayAfterCreditUs115JD` finding immediately below, and §9.3a's Schedule AMTC field-naming
> finding it depends on). Deriving `GrossTaxPayable` from the *same* placeholder rather than a
> second independent hardcoded value keeps the two fields internally consistent, is fully correct
> for the vast majority of returns (AMT does not apply, so item 1d is genuinely `0` and item 8
> correctly degenerates to `GrossTaxLiability`), and will self-correct automatically once 1d itself
> is wired up — rather than needing a second fix later. Regression test
> `test_gross_tax_payable_reflects_real_gross_tax_liability` (`tests/test_itr2_itd_builder.py`)
> asserts `GrossTaxPayable == GrossTaxLiability > 0` for a taxable return, confirmed via `git stash`
> to fail on pre-fix code (`GrossTaxPayable` was `0`). Same full regression suite result as the
> `AssetOutIndiaFlag` fix above (793 passed, 6 pre-existing unrelated failures).

### New finding — `CreditUS115JD`/`TaxPayAfterCreditUs115JD` (AMT credit utilization) never read from Schedule AMTC's own figures

**Evidence:** both hardcoded to `0` (`itd/itr2.py:2691-2692`) regardless of
`_schedule_amtc()`'s own `TaxSection115JD` (§9.3a, confirmed the field-naming there needs fixing
too, but the underlying AMT-credit-utilization computation exists). Form item 9 ("Credit u/s 115JD
of tax paid in earlier years") and item 10 ("Tax payable after credit u/s 115JD") are both
consequently always shown as not applicable, even for a taxpayer with real brought-forward AMT
credit being utilized this year.

**Severity:** High (narrower population — AMT-credit taxpayers only — but a real, silently wrong
pair of fields for that population, compounding §9.3a's Schedule AMTC findings).

**Remediation:** wire `CreditUS115JD` from the same AMT-credit-utilization total §9.3a's fix would
produce, and compute `TaxPayAfterCreditUs115JD` accordingly.

### Secondary finding — surcharge "before marginal relief" breakdown fields are always zero

**Evidence:** `Surcharge25ofSI`, `Surcharge25ofSIBeforeMarginal`, `SurchargeOnAboveCroreBeforeMarginal`
are all hardcoded `0`; only `SurchargeOnAboveCrore`/`TotalSurcharge` (the final, after-marginal-
relief figures) are populated from `result.surcharge`. The form's own item 5 explicitly asks for
both the before- and after-marginal-relief surcharge in parallel columns — the "before" figures
are pure disclosure (the after-relief figure is what's actually charged), so this doesn't affect
tax payable, but is a real, visible gap for any taxpayer whose income triggers surcharge at all.

**Severity:** Medium (disclosure-only; the calculator would need to additionally expose its own
pre-marginal-relief surcharge figure, which may not currently be a separately tracked
intermediate value — worth checking `app/engine/common/surcharge.py`-equivalent before assuming
this is a builder-only fix).

---

# 18b. Tax Payments (Item 20) and Verification

## 18b.1 Full form-order re-audit (2026-09-08)

Cross-referenced Item 20 (Tax Payments — form pp. 69-71: Advance/Self-Assessment tax, TDS-Salary,
TDS-Other, TCS) and Verification (form p. 71) against `_schedule_it()`, `_schedule_tds1/2/3()`,
`_schedule_tcs()`, and `_verification()`/`_verification_block()`
(`itd/itr2.py:2425-2531`, `itd/common.py:160-178`).

**Confirmed still correct, no regression**: TDS-2/TDS-3/TCS (§3.6/§3.7's fixes) and the Schedule IT
challan-completeness gate (§3.8's fix) all match their current form exactly on re-inspection —
consistent with Phase 4's own prior key-by-key re-audit of these same functions.

### New finding — `AssesseeVerPAN`'s schema pattern requires an *individual's* PAN specifically, but ITR-2 also files for HUF assessees with no separate Karta-PAN field to supply it

**Evidence:** the schema's `Verification.Declaration.AssesseeVerPAN` pattern is
`[A-Z]{3}[P][A-Z][0-9]{4}[A-Z]` — note the literal `[P]` in the fourth position, which in a PAN
encodes the holder-category as "Individual" specifically (an HUF's own PAN has "H" in that
position). This is *more restrictive* than the general PAN pattern (`[A-Z]{5}[0-9]{4}[A-Z]`) used
everywhere else in this schema — it structurally cannot accept an HUF's PAN. `_verification_block()`
(`itd/itr2.py`) calls the shared `_verification(name, profile.father_name, profile.pan, ...)`
using `profile.pan` — `ITR2FilingProfile`'s single PAN field, which for an HUF return
(`assessee_status == HUF`, required to verify as Karta or representative per
`ITR2FilingProfile`'s own validator) is the **HUF's own PAN** (category "H"), not a natural
person's. There is no separate field anywhere in `ITR2FilingProfile` for the Karta's own
individual PAN — grepped for `karta_pan`/`kartaPan` across the schema module, zero matches. The
form's own declaration text supports this reading: *"I, ___, son/daughter of ___, solemnly
declare... I am making return in my capacity as ___ and I am also competent to make this return
and verify it. I am holding permanent account number ___"* — a personal declaration naturally
made (and PAN-identified) by the individual signing on the HUF's behalf, i.e. the Karta, not the
HUF entity itself.

**Impact:** every HUF ITR-2 return would emit `AssesseeVerPAN` set to the HUF's own PAN, which
fails the schema's individual-only pattern — meaning **every HUF return currently produced by this
pipeline is schema-invalid at the Verification block**, independent of anything else in the
return being correct. (Individual-assessee returns, the majority case, are unaffected — their own
PAN already has "P" in the required position.) Noted for context, not re-verified here: ITR-4's
`_verification_from_profile()` (`itd/itr4.py:227-238`) passes `profile.pan` through the identical
shared `_verification()` helper the same way — worth checking whether ITR-4's own official schema
carries the same individual-only PAN restriction, which would make this a cross-form gap for real
HUF filings on both forms, not an ITR-2-only issue; out of scope to confirm within this ITR-2
audit.

**Severity:** CRITICAL for HUF taxpayers specifically (100% failure rate for that population,
schema-guaranteed) — a smaller population than Individual assessees, but a complete block for all
of them, matching this document's CRITICAL bar.

**Remediation:** add a `karta_pan: Optional[str]` field to `ITR2FilingProfile` (pattern
`^[A-Z]{3}P[A-Z][0-9]{4}[A-Z]$`), required when `assessee_status == HUF`, and pass it (falling
back to `profile.pan` only for Individual assessees) into `_verification()`'s `pan` argument.

> **Fix status (2026-09-09): fixed and verified.** Added `karta_pan: Optional[str]`
> (pattern `^[A-Z]{3}P[A-Z][0-9]{4}[A-Z]$`) to `ITR2FilingProfile` (`app/schemas/itr2.py`), with a
> new `@model_validator` requiring it whenever `assessee_status == HUF` (matching this schema's
> existing "flag with no backing detail" precedent — `co_owned`/`co_owner_details`,
> `property_owner="OT"`/`property_owner_other`). `_verification_block()`
> (`app/engine/itd/itr2.py`) now selects `profile.karta_pan` for HUF assessees and
> `profile.pan` otherwise, exactly as the remediation above specified — `PersonalInfo.PAN`
> (Part A-GEN1) is unaffected, only the Verification declaration's PAN changes. Wired end-to-end:
> `kartaPan` added to `FilingStatus` (`app/schemas/return_draft.py`,
> `frontend/src/domain/returns/types.ts`, `frontend/src/domain/returns/factory.ts`), mapped in
> `filing_gateway_v2.py::_itr2_filing_profile()`, and surfaced in `PersonalInfoTab.tsx` as a
> conditional "Karta's PAN" field shown only when `itrForm === 'ITR-2' && verification.capacity
> === 'KARTA'`. Three new regression tests in `tests/test_itr2_itd_builder.py`
> (`test_itr2_filing_profile_requires_karta_pan_for_huf_assessee`,
> `test_verification_uses_karta_pan_for_huf_assessee_not_the_hufs_own_pan`,
> `test_verification_still_uses_the_assessees_own_pan_for_individual_filers`), confirmed via
> `git stash` to fail against pre-fix code. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 802 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced). `npm run build` passes cleanly. ITR-4's equivalent `_verification_from_profile()`
> gap (noted above as "out of scope to confirm") was deliberately **not** investigated or fixed —
> this fix is scoped to ITR-2 only, per this session's request.

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

# 20. Phase 8 re-audit (2026-09-09) — independent, schema-first pass across the entire pipeline

With every finding this document previously tracked fixed and verified, this pass is the "local-
correctness exit gate" the standing plan (`zippy-juggling-sprout.md`) calls for before declaring
ITR-2 production-ready: **another full, independent, schema-first re-audit, not trusting any prior
"fixed" claim without re-checking it against the current code.** Matching the 2026-09-08 pass's own
proven methodology (which found ten CRITICAL bugs the prior "all closed" framing had missed), this
pass split the form into six areas — Part A/Verification/Part B-TI/Part B-TTI; Schedule S/HP/CYLA/
BFLA/CFL; Schedule CG/VDA/112A/115AD/SI; Schedule OS/PTI/EI; the foreign/AL/AMT/AMTC/5A/ESOP/tax-
payment schedules; and a direct top-level schema-vs-builder completeness sweep — each independently
cross-referencing the official JSON schema, the official form PDF, and the CBDT Validation Rules PDF
against the current code, not against this document's own prior claims.

**Result: this pass is not clean.** It found **26 new findings, roughly half of them CRITICAL** —
several severe enough that they reverse specific "confirmed correct" claims this document made as
recently as the fixes earlier in this same day. Per the standing plan's own instruction ("if not
clean, loop back into another fix cycle rather than proceeding"), **ITR-2 is not yet
production-ready** — the classification in §21 Final assessment is revised accordingly. Findings are grouped
by the area that found them; severity uses this document's established CRITICAL (schema-invalid or
wrong tax amount) / High (real disclosure gap or CBDT-rule violation, no tax impact) / Medium
(cosmetic/completeness) scale.

## 20.1 Chapter VI-A: five more detail schedules were never built at all — §8.0a's own scope undercounted the true list

**Evidence:** a direct sweep of the official schema's top-level `ITR2` property list against every
`"Schedule..."` key actually emitted by `build_itr2_json()` found five more entirely-missing
official schedules, in the exact same family §8.0a just fixed six of: **`Schedule80C`,
`Schedule80E`, `Schedule80EE`, `Schedule80EEA`, `Schedule80EEB`.** §8.0a's own finding and
remediation explicitly scoped itself to "the six dedicated Chapter VI-A detail schedules" without
ever checking the schema's own full property list — an undercount, not a completeness bug in the
fix itself.

Grepped `app/engine/itd/itr2.py` for all five schema keys: zero matches, same as §8.0a's own
"zero matches" evidence pattern. The underlying data is fully ready and simply discarded, exactly
like the six already-fixed schedules were:
- `_map_deductions()` (`app/engine/draft_to_itr1_input.py`, shared with ITR-2) already computes
  `schedule_80c_entries` — but `draft_to_itr2_input.py` never passes it into `ITR2Input` at all
  (confirmed: `ITR2Input` has zero fields for `schedule_80c_entries`/`schedule_80e_entries`/loan
  rows for 80EE/80EEA/80EEB, unlike `ITR1Input`, which has all of them).
- ITR-1's own proven builders (`_schedule_80c()`, `_schedule_deduction_loan()` — a single generic
  function already parameterized by `section` for 80E/80EE/80EEA/80EEB) exist in
  `app/engine/itd/itr1.py:856-883,1078-1134` and, per a direct field-by-field check against ITR-2's
  own official schema (`Schedule80C`/`Schedule80E`/`Schedule80EE`/`Schedule80EEA`/`Schedule80EEB`),
  match ITR-2's field names exactly (`Schedule80CDtls`/`IdentificationNo`/`Amount`/`TotalAmt` for
  80C; `LoanTknFrom`/`BankOrInstnName`/`LoanAccNoOfBankOrInstnRefNo`/`DateofLoan`/`TotalLoanAmt`/
  `LoanOutstndngAmt`/`Interest{Section}` for the four loan schedules, plus `VehicleRegNo` for 80EEB
  and `PropStmpDtyVal` for 80EEA).
- The frontend already fully captures this data: `Investment80C[]` rows with identification numbers
  (`DeductionsWorkspace.tsx`'s "Section 80C / 80CCC / 80CCD" panel) and a dedicated
  `DeductionLoanManager` row editor (line 349) for all four loan sections, wired through the same
  shared `Deductions.loans.loans: list[DeductionLoan]` canonical structure ITR-1/ITR-4 already use.

**Impact:** every ITR-2 taxpayer claiming Section 80C (PPF/ELSS/life insurance/EPF/tuition — the
single most commonly claimed deduction on any Indian return) or an education/home/EV loan interest
deduction (80E/80EE/80EEA/80EEB) has a correct `ScheduleVIA` aggregate figure with zero backing
detail schedule to substantiate it — the identical "aggregate right, detail schedule missing
entirely" defect class §8.0a fixed for 80D/80G/80GGA/80GGC/80DD/80U, just for five schedules that
finding's own scope never covered.

**Severity:** CRITICAL — same population-reach reasoning as §8.0a's own severity rating; 80C alone
is claimed by the overwhelming majority of old-regime filers.

**Remediation:** identical pattern to §8.0a's own fix — add `schedule_80c_entries`,
`schedule_80e_entries`, and per-section loan-row lists to `ITR2Input`; wire them from the draft via
the same shared `_map_deduction_loans()`/`_map_deductions()` functions ITR-1/ITR-4 already use; add
`_schedule_80c()` and `_schedule_deduction_loan()` (or import/adapt ITR-1's own, already-generic
implementations) to `itd/itr2.py`; wire dispatch into `build_itr2_json()` alongside the other six.

> **Fix status (2026-09-09): fixed and verified.** Wired end-to-end exactly per the remediation
> plan above, with one refinement found while implementing: `_chapter6a_detail_schedules()`'s own
> `claimed()` helper needed the same "80C" combined-key decomposition `_schedule_via()` already
> applies (`app/engine/itd/itr2.py`) — a real 80C claim is only present under its own `"80C"`
> breakdown key once the aggregate GTI cap actually binds; in the common case (deductions
> comfortably below GTI) it's still folded into the raw `"80C+80CCC+80CCD(1)"` combined key, which
> the bare `claimed("80C")` lookup would have silently read as zero. `ITR2Input`
> (`app/schemas/itr2.py`) gained `schedule_80c_entries`, `schedule_80e_entries`,
> `loan_details_80ee_list`, `loan_details_80eea_list`, `loan_details_80eeb_list`, and
> `property_stamp_duty_value_80eea`; `draft_to_itr2_input.py` wires them from the draft via the
> shared `_map_deduction_loans()`; `calculators/itr2.py`'s `compute_deductions()` call now passes
> all five through (the shared eligibility engine already accepted them — only the ITR-2 call site
> never supplied them); `itd/itr2.py` gained `_schedule_80c()` and `_schedule_deduction_loan()`
> (adapted from ITR-1's own proven, already-generic implementations, confirmed field-for-field
> identical against ITR-2's own schema) plus dispatch in `_chapter6a_detail_schedules()`. One
> existing test (`test_schedule_via_serializes_real_per_section_amounts_not_only_a_total`)
> legitimately needed updating: it claimed 80C via the aggregate `amount_80c` alone with no backing
> `schedule_80c_entries` — valid before this fix (no detail schedule existed to require it), but the
> CBDT Category A validator genuinely requires at least one identified row whenever 80C is claimed,
> matching real ITD filing behavior now that `Schedule80C` is actually built. Two new regression
> tests in `tests/test_itr2_itd_builder.py`
> (`test_five_more_chapter6a_detail_schedules_serialize_real_claimed_data`, exercising all five
> schedules together; the existing omission-symmetry test extended to cover all eleven schedules
> now), both confirmed via `git stash` to fail against pre-fix code (Pydantic rejected all five new
> fields as extra/forbidden, confirming they didn't exist before). Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation`
> regression suite: 837 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced).

## 20.2 Part A, Verification, Part B-TI, Part B-TTI

### New finding — `PartB_TTI.NetTaxLiability` holds the fully-aggregated post-interest total, not "Balance Tax After Relief" — the exact bug CLAUDE.md documents as already found and fixed for ITR-1, never ported to ITR-2

**Evidence:** `itd/itr2.py:3560` sets `"NetTaxLiability": _to_rupees(result.net_tax_liability)`.
Per the official form (p.69), item **12** "Net tax liability (10 – 11d)" is computed *before*
interest/fees; item **13e** ("Total Interest and Fee Payable") and item **14** "Aggregate liability
(12 + 13e)" come after. `ITR2Result.net_tax_liability` (`calculators/itr2.py:1128-1136`) is
`gross_tax_liability - relief_89 - relief_90_91 + total_interest + late_fee_234f + fees_234i` — the
*final*, item-14-equivalent figure, interest and fees already included. This is precisely the bug
class CLAUDE.md's own architecture section documents as already fixed in ITR-1
(`itd/itr1.py:628-639`, whose comment explicitly warns "the schema's own `description` field for a
JSON key does not necessarily match what a same/similarly-named internal calculator variable
holds") — but the identical fix was never applied to ITR-2. This document's own §18a.1 currently
(wrongly) states `NetTaxLiability` is "sourced directly and correctly."

**Impact:** every ITR-2 return with any 234A/B/C interest or 234F late fee discloses an inflated
item 12 that is really item 14's figure — and since `AggregateTaxInterestLiability` (item 14, line
3569) also reads `result.net_tax_liability`, the JSON shows `NetTaxLiability ==
AggregateTaxInterestLiability`, a direct self-contradiction (item 12 must be strictly less than
item 14 whenever any interest/fee applies).

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** `_partb_tti()` now computes
> `balance_tax_after_relief = max(0, gross_tax_liability - relief_89 - relief_90_91)` and emits it
> as `NetTaxLiability` — the same ITR-1 fix (`itd/itr1.py:628-639`), extended for ITR-2's extra
> `relief_90_91` (Section 90/90A/91) term. `AggregateTaxInterestLiability` is left reading
> `result.net_tax_liability` unchanged, since that calculator field genuinely is the item-14
> quantity already. Items 8-10 (the AMT-credit/115JD chain feeding item 10) remain a
> separately-tracked gap (§9.3) under which item 10 passes through equal to item 7
> (`GrossTaxLiability`) today — this fix stays scoped to the item-12-vs-item-14 mislabeling only,
> and will self-correct once that chain is wired, matching how `GrossTaxPayable` already
> degenerates the same way. Regression test
> `test_net_tax_liability_is_balance_before_interest_not_the_final_aggregate` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix.

### New finding — `IntrstPay.TotalIntrstPay` excludes the late-filing fee (234F) disclosed one field above it

**Evidence:** `itd/itr2.py:3513`: `total_interest = result.interest_234a + result.interest_234b +
result.interest_234c` (234A/B/C only). Line 3565 separately emits the real, nonzero
`LateFilingFee234F`, but `TotalIntrstPay` (line 3567) never includes it, even though the form's own
item 13e = 13a+13b+13c+**13d**+13da (13d being the 234F fee) — a within-object arithmetic violation
of the field's own documented formula.

**Impact:** for any late-filed return, the itemized `IntrstPay.TotalIntrstPay` under-reports by
exactly the 234F fee, even though the bottom-line `AggregateTaxInterestLiability` (via
`net_tax_liability`) happens to still include it — an internally inconsistent breakdown.

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** `TotalIntrstPay` now sums
> `total_interest + result.late_fee_234f + result.fees_234i` (234A+234B+234C+234F+234-I), matching
> the form's own 13a+13b+13c+13d+13da formula. Found and fixed an incidental sibling bug in the
> same dict along the way: `FeeFurnish234I` (item 13da) was itself hardcoded `0` even though the
> calculator already computes `result.fees_234i` — left unfixed, it would have made the corrected
> `TotalIntrstPay` no longer cross-foot against its own displayed components, so both were fixed
> together. Regression test `test_total_intrst_pay_includes_the_234f_late_fee_and_234i_fee` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix.

### New finding — `PartB-TI.IncFromOS.IncChargblSplRate`/`FromOwnRaceHorse` hardcoded `0`, contradicting Schedule OS's own populated totals — violates CBDT Validation Rules 500-502

**Evidence:** `itd/itr2.py:3458-3463`:
```python
"IncFromOS": {
    "OtherSrcThanOwnRaceHorse": _to_rupees(result.other_sources_income),
    "IncChargblSplRate": 0,
    "FromOwnRaceHorse": 0,
    "TotIncFromOS": _to_rupees(result.other_sources_income),
},
```
`result.other_sources_income` already includes lottery/gaming, unexplained income, NRI/FII
special-rate OS income, DTAA-OS income, and race-horse profit — all folded into the single "normal
rate" field while `_schedule_os()` correctly computes the special-rate and race-horse sub-totals
from the same data. CBDT Validation Rules **500/501/502** (p.34) explicitly require these two
figures to be "consistent with income offered in Schedule OS."

**Impact:** for any taxpayer with lottery/unexplained-income/NRI-special-rate-OS/race-horse income,
Part B-TI's items 4b/4c stay 0 while 4a silently absorbs them — a direct violation of three
numbered CBDT rules, though item 4d (`TotIncFromOS`) and GTI stay numerically correct by
coincidence.

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** `_partb_ti()` now calls `_schedule_os()` a
> second time (a pure function of the same `result, input_data` it already receives) and reads
> `IncChargeableSpecialRates`/`BalanceOwnRaceHorse` straight from its output for `IncChargblSplRate`/
> `FromOwnRaceHorse` (the latter floored at 0, matching the form's own "enter nil if loss" note on
> item 4c). `OtherSrcThanOwnRaceHorse` is derived as `TotOthSrcNoRaceHorse - IncChargeableSpecialRates`
> (Schedule OS's own item 7 minus item 2, i.e. item 6) rather than the whole blended total — this
> guarantees `4a+4b+4c == TotIncFromOS` by construction and can never drift from what Schedule OS
> itself discloses, directly satisfying rules 500-502 rather than independently re-deriving the
> split (a second, drift-prone source of truth). Regression test
> `test_partb_ti_inc_from_os_splits_special_rate_and_race_horse_income_consistent_with_schedule_os`
> in `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix.

### New finding — `IncChargeTaxSplRate111A112`/`IncChargeableTaxSplRates` undercount vs. Schedule SI's true total — violates CBDT Validation Rule 374/376

**Evidence:** `itd/itr2.py:3468,3471` sum only `post_loss["111a"] + post_loss["112"] +
post_loss["112a_gross"]` (+ VDA for the second field). Schedule SI also carries lottery (115BB),
115BBE, 115BBF, 115BBG, 115BBA, 115BBJ, DTAA-OS, and PTI special-rate entries — all excluded. CBDT
rule **374** requires this figure "consistent with **all the special incomes of Schedule SI**" (the
form's own "etc." after "111A, 112, 112A"); rule **376** requires it match Schedule SI's own total
column.

**Impact:** any taxpayer with special-rate income beyond 111A/112/112A/VDA gets an understated item
10/13, contradicting Schedule SI and violating an explicit numbered rule; actual tax payable is
independently computed elsewhere and unaffected.

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** Both `IncChargeTaxSplRate111A112` and
> `IncChargeableTaxSplRates` now read `result.schedules["si"].total_special_rate_income` (Schedule
> SI's own full column-(i) total, already `sum(entry.taxable_income for entry in si_entries)` by
> construction) instead of the narrower `post_loss_cg`-derived CG-only subset. Confirms both form
> items are meant to hold the identical quantity — item 10's own form text ("111A, 112, 112A
> **etc.**") plus rule 374's explicit "consistent with **all** the special incomes of Schedule SI"
> rule out the narrower reading. This also automatically stays consistent with `_schedule_si()`'s
> own `TotSplRateInc` field (both now derive from the identical source), so the two schedules can no
> longer disagree with each other. Regression test
> `test_inc_charge_tax_spl_rate_111a_112_and_spl_rates_cover_full_schedule_si_total` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix.

### New finding — Schedule CFL's current-year loss is never disclosed in its own dedicated field and is wrongly merged into "earlier years'" losses (also breaks Part B-TI cross-check, CBDT rule 486)

See §20.3's own write-up of this same defect (found independently by both the Part-B and the
CYLA/BFLA/CFL passes) for full evidence — flagged here too because it directly falsifies Part
B-TI's own `LossesOfCurrentYearCarriedFwd` cross-schedule identity (rule 486: "'Losses of current
year to be carried forward' at Part B-TI should equal 'Total of Current Year Losses' of Schedule
CFL" — but no such total is ever emitted for ITD to check against).

> **Fix status (2026-09-09): fixed and verified — see §20.3's own fix-status note for full
> evidence.** `CurrentAYloss` is now emitted with real per-head figures whenever a fresh
> current-year loss exists, giving ITD's own `validateItr` the total rule 486 cross-checks
> `LossesOfCurrentYearCarriedFwd` against.

### Supplementary note — widens an already-tracked finding's severity/population

§9.3's existing "AMTC credit fields never read, narrower population" framing undersells the scope:
`GrossTaxPay.TaxInc17` (item 8a) is *also* hardcoded `0` (`itd/itr2.py:3557`) regardless of AMT
status, and `TaxPayAfterCreditUs115JD` (item 10) derives from it — so item 10 stays `0` on **every**
taxable return, not just AMT-credit ones. Re-scope when this cluster is next fixed.

### Areas re-checked, confirmed clean

PersonalInfo/Address/AlternateAddress, FilingStatus (all 7 required fields, enum parity, seventh-
proviso sub-flags), Verification (HUF/individual PAN routing), `AssetOutIndiaFlag`/`GrossTaxPayable`
(both re-confirmed still correctly fixed), STCG-bucket routing (re-confirmed still correctly fixed),
`TaxesPaid` totals.

## 20.3 Schedule S, HP, CYLA, BFLA, CFL

### New finding — Schedule CYLA's six capital-gains sub-baskets always report zero income, directly contradicting Schedule BFLA in the same JSON

**Evidence:** `itd/itr2.py:337-342` reads `getattr(cyla, "stcg20_income", ...)` etc. from
`result.schedules["cyla"]` — a `CYLAResult` instance. **`CYLAResult` has no `stcg20_income` (or
sibling) attributes at all** — those field names exist only on `CYLAInput`, the object *passed
into* `compute()`, not what it returns. `_positive_val`'s `getattr(obj, attr, _ZERO)` silently
returns `0` for every missing attribute, so all six of `STCG20Per`/`STCG30Per`/`STCGAppRate`/
`STCGDTAARate`/`LTCG12_5Per`/`LTCGDTAARate`'s `IncCYLA.IncOfCurYrUnderThatHead`/
`IncOfCurYrAfterSetOff` fields are unconditionally zero, regardless of real capital-gains income.
The correct data (`cyla.cg_gross_income["stcg20"]` etc., or the pre-existing
`cyla.stcg20_remaining`) exists on the object and is never read for this schedule.

Verified directly: a taxpayer with ₹5,00,000 real 111A STCG produces `"STCG20Per":
{"IncCYLA": {"IncOfCurYrUnderThatHead": 0, ..., "IncOfCurYrAfterSetOff": 0}}` in Schedule CYLA,
while the *same* `cyla.stcg20_remaining` correctly produces `"IncOfCurYrUndHeadFromCYLA": 500000`
in Schedule BFLA one field over — **the filed JSON directly contradicts itself between two
schedules for the identical basket in the identical return.** Confirmed pre-existing (unrelated to
this session's `cyla.py` refactor — `_schedule_cyla()` itself is untouched in the working-tree
diff), not a regression.

**Impact:** every ITR-2 return with any STCG/LTCG income — the primary use case this form exists
for — files a Schedule CYLA showing zero capital-gains income in every rate basket while Schedule
BFLA/CG/Part B-TI in the same JSON correctly show the real figures. Very likely to trigger a
`validateItr` rejection or a CPC cross-schedule mismatch.

**Severity:** CRITICAL — likely the single highest-reach defect found in this entire re-audit pass,
given how close to universal nonzero capital-gains income is on this form.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_cyla()` (`app/engine/itd/itr2.py`)
> now reads the six per-bucket gross-income figures from `cyla.cg_gross_income` — the dict already
> added to `CYLAResult` for Table E's own source-bucket × target-bucket matrix, which holds exactly
> the `max(0, raw_income)` value each `IncOfCurYrUnderThatHead` field needs — instead of the
> nonexistent `stcg20_income`/etc attributes. `HPlossCurYrSetoff`/`OthSrcLossNoRaceHorseSetoff`
> (the per-bucket cross-head-setoff attribution sub-fields) were left untouched, staying `0` as
> before — that finer-grained attribution isn't tracked anywhere yet and is out of this fix's
> scope; only the `getattr`-on-a-nonexistent-attribute bug that zeroed the *income* fields was
> fixed. One new regression test in `tests/test_itr2_itd_builder.py`
> (`test_schedule_cyla_reports_real_capital_gains_income_not_zero`), asserting both that Schedule
> CYLA's own income figures are correct AND that they now agree with Schedule BFLA's corresponding
> fields for the identical basket in the identical return (the exact self-contradiction this finding
> describes) — confirmed via `git stash` to fail against pre-fix code (`0 == 200000`). No existing
> test in this codebase ever exercised `ScheduleCYLA`/`ScheduleBFLA` at all before this fix. Full
> combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation`
> regression suite: 828 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced).

### New finding — Schedule CFL mislabels the current year's own fresh losses as "earlier years'" brought-forward losses; `CurrentAYloss` is never populated

**Evidence:** `itd/itr2.py:493-497` builds `TotalOfBFLossesEarlierYrs`/`TotalLossCFSummary` both
from `summary(flattened, ...)`, where `flattened` includes **both** genuinely brought-forward losses
(`bfla.entries`) **and** this year's own fresh unabsorbed losses (`cyla.entries`, tagged
`assessment_year="2026-27"`), unfiltered by year. The per-year loop (lines 474-492) correctly skips
AY "2026-27" (since `year_keys` only spans AY2018-19 through AY2025-26), but the *aggregate* has no
equivalent filter — so a fresh current-year loss silently lands inside a field whose own name says
"Earlier Yrs," and `CurrentAYloss` (the schema's dedicated slot, description "Current Year Losses")
never appears in the output at all. `TotalOfBFLossesEarlierYrs` and `TotalLossCFSummary` are
therefore always byte-identical — which cannot be correct once any current-year loss exists (the
form has these as two distinct rows: earlier-years total vs. grand total including current year).

Verified directly: a fresh AY2026-27 LTCG loss of ₹50,000 plus a genuine AY2023-24 STCG
brought-forward loss of ₹30,000 produces `TotalOfBFLossesEarlierYrs: {..., TotalLTCGPTILossCF:
50000, ...}` — the fresh loss counted as an earlier year's.

**Impact:** any return with a fresh current-year capital/HP loss being carried forward (a routine
scenario) permanently misclassifies that loss's origin year in the filed record, omits the
dedicated current-year field the schema provides for it, and breaks the Part B-TI cross-check (CBDT
rule 486 — see §20.2).

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_cfl()` now partitions `flattened` by
> `entry.assessment_year_of_loss == "2026-27"` before summarizing: `TotalOfBFLossesEarlierYrs` (form
> row ix) is now built from the earlier-years-only partition; `CurrentAYloss` (row xi) is emitted
> from the current-year-only partition, and only when it is non-empty (matching this builder's own
> "no empty placeholder objects" convention elsewhere); `TotalLossCFSummary` (row xii, "Total loss
> carried forward to future years") is left reading `summary(flattened, ...)` — the *unfiltered*
> total — since row xii is genuinely ix+xi combined and was already correct. `AdjTotBFLossInBFLA`
> (row x, "Adjustment of above losses in Schedule BFLA") remains unemitted — it is schema-optional
> and a distinct gap (the *portion of brought-forward losses actually absorbed this year*, not
> tracked anywhere in this builder yet), not part of this finding's own scope; noted here as a
> forward pointer, not fixed. Two new regression tests in `tests/test_itr2_itd_builder.py`:
> `test_schedule_cfl_separates_current_year_fresh_losses_from_earlier_years_brought_forward`
> (a fresh AY2026-27 LTCG loss plus a genuine AY2023-24 brought-forward STCG loss, matching this
> finding's own verification scenario — `git stash`-confirmed to fail pre-fix, reproducing exactly
> the described mislabeling) and `test_schedule_cfl_omits_current_ay_loss_when_no_fresh_loss_exists`
> (confirms the fix doesn't fabricate an empty `CurrentAYloss` block when every loss is genuinely
> brought-forward — passes both pre- and post-fix, since that path was already correct). Full
> combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 681 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).

### New finding — Schedule HP always discloses `ifLetOut: "L"` for deemed-let-out properties, never "D"

**Evidence:** `itd/itr2.py:777`: `"ifLetOut": "S" if ptype == "S" else "L"`. The schema's enum is
`["L", "D", "S"]` — "D" (deemed let out, section 23(4), for taxpayers owning more properties than
the self-occupied-exempt limit) is a distinct value `PropertyType.DEEMED_LET_OUT = "D"` already
exists for. ITR-1's and ITR-4's own builders (`itd/itr1.py:277`, `itd/itr4.py:1311`) correctly pass
`hp_input.property_type.value` through unchanged; ITR-2's alone collapses "D" into "L".

**Impact:** any multi-property owner past the self-occupied limit files a return misrepresenting a
deemed-let-out property as actually rented, with no real rent data behind it — a CPC scrutiny risk.

**Severity:** High.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_hp()` now emits `"ifLetOut": ptype`
> (`ptype = source.property_type.value`) directly, matching ITR-1's own builder exactly — the
> `"S" if ptype == "S" else "L"` collapse is removed. No other logic in the same loop branches on
> the S/L/D distinction beyond the interest computation, which already treats deemed-let-out
> correctly (section 23(4): full, uncapped interest, the same `else` branch let-out already uses —
> confirmed in `app/engine/schedules/house_property.py:90-92`, which only special-cases
> `SELF_OCCUPIED`), so no calculator change was needed. Regression test
> `test_schedule_hp_deemed_let_out_property_discloses_d_code_not_collapsed_to_l` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 682 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).

### New finding — real per-employer Section 10 exemption rows (10(6)/10(7)/10(10CC)/EIC/10(17)/etc.) are computed then discarded, not just uncaptured

**Evidence:** `itd/itr2.py:613-624` builds a local `exemption_rows` list from
`detail.section10_exemption_rows` (real, frontend-captured data — `EmployerEntryManager.tsx:129-140`'s
"Section 10 Exemption" row editor, wired end-to-end through `filing_gateway_v2.py:1621-1667` into
`EmployerFilingDetail.section10_exemption_rows`) — then never attaches it to the output; the
schedule's actual `AllwncExemptUs10Dtls` array is built separately, purely from the calculator's own
10 fixed exemption codes (LTA, gratuity, etc.), which don't cover this UI's own codes.

**Impact:** a taxpayer using this specific frontend control (embassy/foreign-service pay, MP/MLA
allowance, judges' exempt income, and 6 other codes) has that entered data silently vanish from the
filed JSON — real information loss, not merely an uncaptured field. Revises this document's own
§5.5 "P2 while uncommitted" note upward: the frontend UI is confirmed live, so this is reachable by
real taxpayers today.

**Severity:** High.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_s()` now collects
> `detail.section10_exemption_rows` (positive-amount rows only) from EVERY employer into a
> return-scope list — the discarded local variable was ALSO loop-scoped and never accumulated
> across employers even before being dropped, a second facet of the same bug — and merges it into
> the calculator-derived `exemption_rows` list before emitting `AllwncExemptUs10Dtls`. No
> double-counting risk: the frontend editor's own codes (10(6)/10(7)/10(10CC)/10(14)(i)/10(14)(ii)/
> their 115BAC variants/EIC/10(17)) are entirely disjoint from `_SALARY_EXEMPTION_ROWS`'s set
> (LTA/gratuity/pension/leave/retrenchment/VRS/transport/CEA/hostel/uniform). Found and fixed one
> incidental integrity gap while rewriting this exact block: the frontend dropdown also offers an
> "OTH" catch-all with no matching official `SalNatureDesc` enum value — passing it through
> unfiltered would have produced schema-invalid JSON (this builder's downstream
> `validate_itr2_json()` would eventually catch it, but with a generic, unhelpful message); now
> raises a specific `ValueError` naming the employer, matching this file's own established
> fail-closed convention (e.g. `_schedule_80c`'s `identifier_number` guard). Left the dedicated
> `Section10_13A` (HRA) structure's own deliberate exclusion from this generic array untouched —
> re-confirmed correct against an existing test
> (`test_schedule_s_reports_real_section_10_exemption_breakdown`'s own
> `assert "10(13A)" not in codes`), not part of this finding's evidence. Two new regression tests in
> `tests/test_itr2_itd_builder.py`: `test_schedule_s_reports_real_per_employer_section_10_exemption_rows_not_discarded`
> (two employers, each with its own distinct exemption code, plus a zero-amount row confirmed
> excluded — `git stash`-confirmed to fail pre-fix) and
> `test_schedule_s_rejects_section_10_exemption_row_with_no_valid_schema_code` (the "OTH" guard,
> also `git stash`-confirmed to fail pre-fix, since pre-fix code never read `SalNatureDesc` at all
> and raised nothing). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 684
> passed, only the same 5 pre-existing `test_itr2_input_validation.py` HUF-verification failures
> (unrelated, unchanged).

### New finding (found while fixing the discard bug above) — six of the nine Section 10 exemption codes this same frontend editor offers never reduce taxable salary at all, for ITR-1 AND ITR-2 alike

**Evidence:** `_map_salary()` (`app/engine/draft_to_itr1_input.py:333-340`, shared verbatim by both
forms — `draft_to_itr2_input.py:917` calls it directly) reads `employer.section10ExemptionRows` and
extracts only three codes into `SalaryIncome` scalar fields: `10(6)` → `sec10_6_embassy_exempt`,
`10(7)` → `sec10_7_foreign_allowance`, `10(10CC)` → `sec10_10cc_perquisite_tax`. The other six
codes the SAME frontend dropdown offers — `EIC` (judges' exempt income), `10(17)` (MP/MLA/MLC
allowance), `10(14)(i)`/`10(14)(ii)` "not otherwise entered", and their two `115BAC` new-regime
variants — have no matching `SalaryIncome` field at all and are silently dropped by `_map_salary()`
itself, before ever reaching `SalaryIncome`. `EmployerFilingDetail.section10_exemption_rows` (this
finding's own JSON-disclosure fix, immediately above) is confirmed NEVER read by
`calculators/itr2.py` (`grep employer_filing_details app/engine/calculators/itr2.py` → no hits) —
it is a pure disclosure structure with zero effect on tax computation. So for these six codes,
today's real behavior is: the taxpayer enters a genuine Section 10 exemption on the frontend, and
(from AY2026-27 Phase 8's tenth+ fixes onward) it is now correctly *disclosed* in
`AllwncExemptUs10Dtls` — but the SAME amount is never subtracted from `TotIncUnderHeadSalaries`,
so it is taxed anyway. A judge or MP/MLA using this exact control pays real, incorrect additional
tax on income the Act exempts.

**Impact:** genuine over-taxation (not merely a disclosure gap) for any ITR-1 or ITR-2 taxpayer
using this editor for EIC/10(17)/10(14)(i)-or-(ii)-"not otherwise entered"/115BAC-variant income —
a real-money defect, and shared code, so both forms need the fix together. Out of scope for this
finding (which is specifically the JSON-disclosure discard bug, already fixed above) — flagged here
as a forward pointer per this document's own discipline of not silently folding newly-discovered
bugs into an unrelated fix. Would need: new `SalaryIncome` scalar fields (or a generic list field)
for the six missing codes, `_map_salary()` changes (regression-tested against BOTH forms, since
it's shared), and `schedules/salary.py` actually subtracting them from taxable income — a
materially larger change than this fix's scope.

**Severity:** High (real tax-liability impact, but a narrow taxpayer population — judges, MPs/MLAs/
MLCs, embassy/foreign-government-service employees with a "not otherwise entered" 10(14) claim).

> **Fix status (2026-09-09): fixed and verified.** A new `SalaryIncome.other_section10_exempt`
> field (`app/schemas/itr1.py`) holds the direct pass-through sum of all six previously-dropped
> codes — no dedicated ceiling formula exists for any of them in this engine (unlike CEA/hostel,
> which share the 10(14) family but are tracked separately via the pre-existing
> `sec10_14i_prescribed_allowance`/`sec10_14ii_personal_allowance` fields; the new field does not
> touch or rename those). `_map_salary()` (`app/engine/draft_to_itr1_input.py`) now sums
> `EIC`/`10(17)`/`10(14)(i)`/`10(14)(ii)`/`10(14)(i)(115BAC)`/`10(14)(ii)(115BAC)` rows into it,
> alongside its existing 10(6)/10(7)/10(10CC) extraction — same loop, same source array, one more
> branch. `schedules/salary.py` now includes it in `exempt_allowances`, so it actually reduces
> `income_chargeable`. Since `draft_to_itr2_input.py` calls this exact same `_map_salary()`
> function, the fix applies to ITR-2 automatically, through the identical shared code path — no
> ITR-2-specific mapping change was needed. No ITD-builder change was needed either: the JSON
> disclosure side (`AllwncExemptUs10Dtls`, via `EmployerFilingDetail.section10_exemption_rows`) was
> already fixed in the immediately-preceding finding and is a separate, already-correct data path;
> this fix is calculator-only. Two new regression tests, one per form (proving the shared-function
> claim rather than assuming it): `test_remaining_section10_exemption_rows_reach_the_calculator_not_just_disclosure`
> in `tests/test_draft_to_itr1_input.py` and
> `test_remaining_section10_exemption_rows_reduce_taxable_salary_for_itr2_too` in
> `tests/test_draft_to_itr2_input.py`, both `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_draft_to_itr1_input`/`test_draft_to_itr2_input`
> regression suite: 760 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged).

### New finding — `uniform_allowance_exempt` disclosed under the wrong Section 10(14) sub-clause

**Evidence:** `itd/itr2.py:519` tags it "10(14)(ii)"; `salary.py:170-176`'s own docstring cites
"10(14)(i) / Rule 2BB(1)(f)" (actual-expenditure-based, like the other Rule 2BB(1) items correctly
tagged "10(14)(i)" nearby) — uniform allowance alone is misfiled into the fixed-statutory-rate
"10(14)(ii)" bucket.

**Impact:** no tax effect (the exempt amount is correct); the disclosed statutory sub-clause is
wrong.

**Severity:** Medium.

> **Fix status (2026-09-09): fixed and verified.** `_SALARY_EXEMPTION_ROWS`'s `uniform_allowance_exempt`
> entry now tags `"10(14)(i)"` instead of `"10(14)(ii)"`, matching the official schema's own
> description of that sub-clause ("...to the extent actually incurred...") and
> `_exempt_uniform_allowance()`'s own docstring citation. Transport/CEA/hostel are unaffected —
> confirmed still correctly `"10(14)(ii)"` (fixed statutory-rate allowances, matching that
> sub-clause's own "compensate for increased cost of living" description). Regression test
> `test_schedule_s_uniform_allowance_disclosed_under_10_14_i_not_10_14_ii` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 685 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).
>
> **Related, NOT fixed here (found while verifying this fix):** ITR-1's own `_allowance_rows()`
> (`itd/itr1.py:1315-1324`) takes a different, likely also-wrong approach — it folds
> `uniform_allowance_exempt` INTO `cea_exempt` and emits the combined total as a single `"10(14)(i)"`
> row, on the stated (and, per the same schema description just used to fix ITR-2 above, incorrect)
> premise that "the official schema has no separate code for [uniform allowance]." The schema does
> have both `10(14)(i)` and `10(14)(ii)`, and CEA is a fixed per-child/month statutory rate — the
> same "10(14)(ii): compensate for increased cost of living" category as ITR-2's own (correctly
> tagged) hostel/transport rows, not `10(14)(i)`. This looks like a genuine, separate ITR-1-only
> defect (CEA misfiled as `10(14)(i)` instead of `10(14)(ii)`, and merged with uniform allowance
> into one row instead of two) — out of scope for this ITR-2-focused fix and not independently
> re-verified against a live ITR-1 test; flagged here as a forward pointer only, per this document's
> own discipline of not silently folding newly-noticed cross-form issues into an unrelated fix.

### New finding (dormant, latent) — `IncomeNotified89AType` country rows use the wrong field names, currently unreachable

**Evidence:** `itd/itr2.py:608` passes `detail.income_notified_89a_country_rows` straight through
with no key renaming, unlike its three sibling detail-row types on the same line-block (which are
correctly transformed). Confirmed dormant: no frontend component currently populates this array (a
TS-interface-only field with zero UI wiring), so it is always `[]` today.

**Impact:** none today; will produce schema-invalid JSON the instant this field gets a frontend UI —
flagged so it isn't rediscovered from scratch later, matching this document's own established
practice for latent gaps (§5.5).

**Severity:** Low (latent).

> **Fix status (2026-09-09): fixed and verified — fixed proactively despite zero current impact,**
> **matching this document's own stated purpose for latent findings ("flagged so it isn't
> rediscovered from scratch later") — closing it now is cheaper than re-discovering and re-fixing
> it once a frontend UI lands.** `EmployerFilingDetail.income_notified_89a_country_rows`
> (`app/schemas/itr2.py`) is now typed `List[OS89ACountryEntry]` instead of a raw
> `list[dict[str, Any]]` — reusing the exact same typed model Schedule OS's own
> `OSSection89A.country_entries` already uses for the identical official `NOT89AType` structure,
> rather than duplicating it, so a country code outside `{US, UK, CA}` is now rejected at the
> schema boundary instead of ever reaching the ITD builder. `filing_gateway_v2.py`'s two
> `EmployerFilingDetail` construction sites now build `OS89ACountryEntry` instances from the raw
> frontend dict (`{"countryCode": ..., "amount": ...}`) instead of passing it through unchanged.
> `_schedule_s()` (`itd/itr2.py`) now emits `{"NOT89ACountrycode": ..., "NOT89AAmount": ...}` rows,
> matching its three sibling detail-row types in the same block. Two new regression tests:
> `test_schedule_s_income_notified_89a_country_rows_use_official_key_names` in
> `tests/test_itr2_itd_builder.py` (builder-level, using the typed `EmployerFilingDetail` input
> directly) and `test_generate_cbdt_json_itr2_transforms_income_notified_89a_country_rows` in
> `tests/test_filing_gateway_v2_itr2.py` (full pipeline, from a raw frontend-shaped dict through to
> the filed JSON), both `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_draft_to_itr1_input`/`test_draft_to_itr2_input`/
> `test_filing_gateway_v2_itr2` regression suite: 762 + 24 passed, only the same 5+1 pre-existing
> failures (the `test_itr2_input_validation.py` HUF-verification cluster plus
> `test_generate_cbdt_json_itr2_rejects_representative_verification`, both independently confirmed
> still failing identically on pre-fix code — unrelated, unchanged).

### Areas re-checked, confirmed clean

Schedule S employer identity/address/gross/perquisites/profits-in-lieu cross-footing, HRA
computation, `nature_of_salary`/`perquisites`/`profit_in_lieu` row transforms; Schedule HP
`PropertyOwnerOther`/co-owner/tenant emission and self-occupied interest derivation (aside from the
`ifLetOut` finding above); Schedule BFLA independently re-verified fully self-consistent and correct
(in direct contrast to Schedule CYLA's own breakage from the identical underlying data); Schedule
CFL per-year slot selection and race-horse 4-year-cap gating (aside from the `CurrentAYloss` finding
above).

## 20.4 Schedule CG, VDA, 112A, 115AD, SI

### New finding — Section 112A gain is corrupted by double-counted deductions for every explicit Schedule 112A/115AD scrip — fabricates a loss from a real gain

**Evidence:** `capital_gains.py:261`, inside `compute_112a()`: `total_gain += sale -
effective_cost - deductions`, where `deductions = total_deductions + expenditure`. For scrips
classified from `input_data.cg_transactions`, `total_deductions` defaults to 0 so the formula is
accidentally correct. But for the **explicit-scrip path** (`cg_112a_scrips`/`cg_115ad_scrips`,
merged in `calculators/itr2.py:527-542` via `total_deductions=scrip.total_deductions`) — a
frontend-required field (`CapitalGainsEntryManager.tsx`'s "Total deductions" input, marked
`required: true` on the dedicated Schedule 112A/115AD entry UI) that already mirrors `deemed_cost +
expenditure` — the same cost/expenditure quantity is subtracted twice.

Verified numerically: `sale=1,000,000, cost=500,000, expenditure=5,000, total_deductions=505,000`
(the frontend's own readout) → `compute_112a()` returns **total_gain = -10,000**, a fabricated loss,
against a correct gain of +495,000.

**Impact:** every taxpayer using the *primary, dedicated* Schedule 112A/115AD scrip-entry UI (not
an edge case — this is the intended entry path for listed-equity LTCG) has their 112A gain
understated by `effective_cost + expenditure` per scrip, routinely turning a large real gain into a
fabricated loss — eliminating 112A tax and potentially generating a bogus LTCL that flows into
CYLA/carry-forward. Self-contradictory too: Schedule 112A/115AD's own per-row `Balance`/
`Balance112A` (built independently, doesn't read `total_deductions`) shows the *correct* gain while
Schedule CG/SI show the wrong one, in the same filed return. No existing test sets
`total_deductions` on a `CG112AScrip`, so this is currently unguarded.

**Severity:** CRITICAL — wrong tax amount, on the single largest and most common capital-gains
category, via the primary UI path.

> **Fix status (2026-09-09): fixed and verified.** Investigating before fixing settled a question
> the finding itself left open: whether `total_deductions` truly duplicates `cost + expenditure`
> for real callers, or whether it's typically left at 0 in practice. Two pieces of evidence confirm
> it's the former — `app/engine/validators/itr2/input_rules.py`'s `ITR2-IN-112A-006` explicitly
> validates `scrip.total_deductions == cost_acq_without_index + expenditure_on_transfer` whenever
> the field is supplied nonzero, and `_112a_style_schedule()` (`app/engine/itd/itr2.py`) — the
> function that actually builds Schedule 112A/115AD's own disclosed `TotalDeductions`/`Balance`
> JSON fields — independently recomputes `deemed_cost + expense` from scratch and **never reads
> `asset.total_deductions` at all**, confirming the field has no legitimate role as a compute
> input anywhere in this codebase; its only use before this fix was to wrongly double-subtract in
> `compute_112a()`'s own tax arithmetic. Fixed by removing `asset.total_deductions` from
> `compute_112a()`'s (`app/engine/schedules/capital_gains.py`) gain formula entirely — `effective_cost`
> and `expenditure` already fully account for the same deduction, matching exactly how land/building
> assets' own `compute_stcg()`/`compute_ltcg()` already treat `total_deductions` as a
> compute-*output*, never an input. `compute_112a()` is shared with ITR-3 (`calculators/itr3.py`),
> so this fix applies there too — confirmed non-breaking via a clean `import
> app.engine.calculators.itr3`. A sibling instance of the identical bug was found and fixed in the
> same pass: Table F's own `_accrued_cg()` (`app/engine/itd/itr2.py`, this session's own earlier
> addition) used the same wrong formula for its 112A/115AD-scrip quarterly-bucket approximation —
> fixed identically. Two new regression tests in `tests/test_itr2_itd_builder.py`
> (`test_112a_scrip_total_deductions_is_not_double_counted`,
> `test_schedule_cg_table_f_112a_scrip_gain_is_not_double_counted`), both confirmed via `git stash`
> to fail against pre-fix code — the Schedule-112A test's pre-fix failure is notable in its own
> right: `capital_gains_income` came out to `0`, not the audit's own predicted `-10,000`, because
> a negative aggregate CG figure is floored elsewhere in the pipeline — meaning the real pre-fix
> behavior was "a genuine ₹495,000 gain pays zero tax," an even more direct illustration of the
> undertaxation this bug caused than the raw per-scrip arithmetic alone suggested. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation`
> regression suite: 830 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced).

### New finding (re-surfacing an already-documented, still-unfixed defect) — `EquityMFonSTT` is built one row per transaction instead of aggregated, capped at 2 items

**Evidence:** `itd/itr2.py:1423-1441` appends one row per matching `CGTransaction` to a sub-type
(`EquityOrUnitSec94TypeMFonSTT`) that has no scrip identifier and is aggregate-only, capped at
`maxItems: 2` in the schema. Already documented as a known, deliberately-deferred gap in this
document (line ~492-498, "a newly-found item for a future pass") — re-confirmed still present;
this Phase 8 pass is exactly that deferred "future pass," surfacing it again so it gets actioned.

**Impact:** outright `validateItr` schema-invalid rejection for any taxpayer with 3+ STT-paid
equity/MF STCG transactions in the year — the common case for retail equity investors, not an edge
case.

**Severity:** CRITICAL (filing-blocking).

> **Fix status (2026-09-09): fixed and verified.** `_schedule_cg()` now aggregates every matching
> 111A `CGTransaction` (`FullConsideration`/`AquisitCost`/`ImproveCost`/`ExpOnTrans`/`BalanceCG`/
> `CapgainonAssets` all summed) into a single row, emitted only when at least one matching
> transaction exists — at most one row is ever produced for a given return, since
> `MFSectionCode` ("1A" vs "5AD1biip") is derived from the filing profile's single `is_fii_fpi`
> flag, never per-transaction, so no return can legitimately need both codes. `LossSec94of7Or94of8`
> stays `0` (summed across a single row, unaffected) — the underlying section-94(7)/94(8)
> dividend-stripping figure remains its own separately-tracked, deliberately-deferred gap (no input
> field captures it at all), unrelated to this fix. Found and fixed an incidental bug in the same
> rewrite: `BalanceCG`/`CapgainonAssets` previously omitted `improvement_cost` from the subtraction
> even though the sibling `DeductSec48.TotalDedn` (computed one line below, for the identical
> transaction) already included it — the two fields disagreed on what "total deduction" meant.
> Regression test `test_equity_mf_on_stt_aggregates_transactions_instead_of_one_row_each` (three
> 111A transactions, would previously have produced three rows exceeding `maxItems: 2` and failed
> schema validation) in `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full
> combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 695 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).

### New finding — Schedule 112A/115AD's own aggregate `LTCGBeforelowerB1B2{suffix}` doesn't equal the sum of its own listed rows

**Evidence:** `itd/itr2.py:1943` clamps each row's value at `max(0, sale - cost)` per row (matching
the schema's row-level `minimum: 0`), but the aggregate at line 1962 independently recomputes
`max(0, total_sale - total_cost)` from *bucket* totals rather than summing the (already-clamped)
rows. When scrips mix gains and losses these diverge (e.g. two scrips, +20,000 and -20,000 clamped
to 0, sum of rows = 20,000 but the aggregate formula gives 0).

**Impact:** the disclosed total doesn't reconcile with its own listed rows — the tax-relevant
`Balance{suffix}`/`TotalBalance{suffix}` fields (correctly row-summed) are unaffected, so this is a
disclosure-integrity bug, not a tax-amount bug.

**Severity:** Medium.

> **Fix status (2026-09-09): fixed and verified.** `_112a_style_schedule()` (`app/engine/itd/itr2.py`,
> shared by both `_schedule_112a()` and `_schedule_115ad()`) now sums each row's own
> (already row-clamped) `LTCGBeforelowerB1B2` value for the aggregate
> `LTCGBeforelowerB1B2{suffix}`, instead of independently recomputing `max(0, total_sale -
> total_cost)` from bucket-level totals — matching the exact "sum the rows, not the bucket" pattern
> `Balance{suffix}`/`TotalBalance{suffix}` already used correctly a few lines below it. Regression
> test `test_schedule_112a_ltcg_before_lower_b1b2_sums_the_rows_not_the_bucket_totals` (two scrips,
> +20,000 and -20,000, reproducing the finding's own example exactly) in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 696 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).

### New finding — Table F (`AccruOrRecOfCG`) never discloses VDA accrual timing

**Evidence:** `_accrued_cg()` never reads `input_data.vda_transactions` at all, despite each VDA
transaction carrying its own `date_of_transfer` and directly computable income — the schema's
optional `VDATrnsfGainsUnder30Per` field is omitted entirely rather than even zero-filled.

**Impact:** a taxpayer with material VDA income gets nothing disclosed in Table F's own quarterly
234C-support breakdown for that income, unlike every other real capital-gains category this table
covers — a genuine "computed but discarded" gap, not a "no data source" case like the always-empty
DTAA/applicable-rate buckets.

**Severity:** Medium.

> **Fix status (2026-09-09): fixed and verified.** `_accrued_cg()` now iterates
> `input_data.vda_transactions`, bucketing each transaction's income (mirroring
> `_schedule_vda()`'s own income-derivation formula: `income_from_vda` when explicitly supplied,
> else `max(0, consideration_received - acquisition_cost)`) into `VDATrnsfGainsUnder30Per` by
> transfer-date quarter, the same `_cg_quarter_index()`/`add()` machinery every other real bucket
> in this table already uses. The always-zero applicable-rate/DTAA buckets are unaffected — they
> genuinely have no data source anywhere in this builder, unlike VDA. Regression test
> `test_schedule_cg_table_f_discloses_vda_accrual_timing` (two VDA transactions in different
> quarters) in `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix (`KeyError`
> on the missing field). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite:
> 697 passed, only the same 5 pre-existing `test_itr2_input_validation.py` HUF-verification
> failures (unrelated, unchanged).

### Areas re-checked, confirmed clean

Table E (`CurrYrLosses`) re-verified via two hand-worked scenarios (partial-absorption and
insufficient-capacity cases) — every field name matches, every `minimum: 0` constraint holds,
`TotLossSetOff - LossRemainSetOff` reconciles correctly in both traces. Schedule 112A/115AD routing
(mutual exclusivity, unioned explicit-scrip lists) confirmed still correct aside from the deduction-
double-count finding above. Schedule SI's FII-specific and ordinary section-code/rate mappings
confirmed exact. Schedule VDA's per-transaction loss-disallowance confirmed correctly implements
section 115BBH(2). The gross-vs-threshold 112A handling in `SumOfCGIncm`/CYLA's `ltcg125_income`
bucket confirmed intentional and internally consistent, not a bug.

## 20.5 Schedule OS, PTI, EI

### New finding — `os_pass_through_income` is disclosed but never taxed — a sibling of the just-fixed `os_other_income_entries` undertaxation gap

**Evidence:** `draft_to_itr2_input.py:937-946` correctly backs `os_pass_through_income` out of the
generic `other_income` residual (to avoid double-counting it there) — but unlike its two siblings in
the same block (`os_machinery_plant_rent`, added back at `calculators/itr2.py:453-459`; and
`os_other_income_entries`, added back at `calculators/itr2.py:491-493`, per this session's own just-
landed fix), **`os_pass_through_income` is never added back anywhere.** Grepped the calculator
end-to-end for the field: zero references outside the draft mapper's own subtraction and the
builder's disclosure/null-check use.

Verified numerically (generic-other=1000, MACHINERY_RENT=2000 net of ₹200 deductions,
PASS_THROUGH=3000, one return): calculator total comes out to 2800 (should be 5800) — the 3000
pass-through amount is silently dropped from GTI even though `NatofPassThrghIncome: 3000` appears,
correctly, in the filed JSON.

**Impact:** real, user-entered, disclosed OS pass-through income (business-trust/investment-fund
pass-through interest, captured via the frontend's own dedicated "Pass-through income at normal
rate" option) completely escapes tax. Undertaxation — the same defect class the
`os_other_income_entries` fix closed for a sibling field, left open for this one.

**Severity:** CRITICAL.

> **Fix status (2026-09-09): fixed and verified.** `input_data.os_pass_through_income` is now added
> into `r.other_sources_income` in `app/engine/calculators/itr2.py`, right alongside the
> `os_other_income_entries` addition this same fix cycle just landed — the mirror-image half of
> that fix, needed since `draft_to_itr2_input.py` already correctly backed this field out of the
> generic `other_income` aggregate (unlike `os_other_income_entries`, which needed that back-out
> added as part of its own fix), so no double-counting risk existed here; the calculator simply
> never read the field at all. Two new regression tests in `tests/test_itr2_itd_builder.py`
> (`test_os_pass_through_income_is_taxed_not_just_disclosed`, proving taxable income itself shifts
> by exactly the disclosed amount;
> `test_os_pass_through_income_is_not_double_counted_via_the_draft_pipeline`, proving the real v2
> pipeline now taxes it exactly once), both confirmed via `git stash` to fail against pre-fix code
> (income delta `0` instead of `15000`/`20000`). Full combined `test_itr1_*`/`test_itr2_*`/
> `test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation` regression suite: 832 passed, only
> the same 6 pre-existing failures (unrelated to this fix, not newly introduced).

### New finding — `InterestGross` doesn't sum its own declared sub-items; PF-proviso/NSC/bonds/securities interest is taxed through an untraceable channel

**Evidence:** `itd/itr2.py:943` computes `InterestGross = savings_bank_interest +
fixed_deposit_interest + interest_on_it_refund` only — omitting `NatofPassThrghIncome`, the four
`IntrstSec10XI*Proviso` fields, and `IntrstFrmOthers`, even though the form's own item 1b =
bi+bii+...+bix and all of those sibling sub-items are correctly populated a few lines above. The
real tax gap: these categories' amounts flow into GTI only via the generic `other_income` residual
(through the shared `_map_other_sources()`), which — unlike the three categories the
`os_other_income_entries` fix's own back-out block now covers — is never backed out for these, so
`_schedule_os()` never reads `source.other_income` anywhere at all (confirmed via grep). Verified
numerically: NSC interest alone of ₹10,000 produces `InterestGross: 0` and `GrossIncChrgblTaxAtAppRate:
0`, while `BalanceNoRaceHorse`/`TotOthSrcNoRaceHorse` correctly show 10,000 and `IntrstFrmOthers:
10000` sits disclosed with no header total it actually feeds.

**Impact:** tax computed happens to be numerically correct for this category (taxed once, via the
invisible generic-aggregate channel) — but the filed JSON is internally inconsistent:
`GrossIncChrgblTaxAtAppRate` (item 1) doesn't equal its own declared 1a+1b+1c+1d+1e formula,
`InterestGross` (item 1b) doesn't equal its own declared bi+...+bix formula, and neither reconciles
against `BalanceNoRaceHorse`. Extends this same session's own "item 1 vs item 6" self-contradiction
fix to a category it didn't cover.

**Severity:** CRITICAL.

> **Fix status (2026-09-09): the disclosure self-contradiction is fixed and verified; the
> underlying "untraceable channel" for PF-proviso/NSC/bonds interest remains open.** This finding
> compounds two distinct issues, and only the first is fixed here: (1) `InterestGross` not summing
> its own nine declared sub-items (the "self-contradiction" this fix was specifically scoped to),
> and (2) those sub-items' underlying tax reaching GTI through an untraceable generic-aggregate
> channel rather than an explicit, dedicated one. `InterestGross` (`app/engine/itd/itr2.py`) is now
> computed from all nine of its own `block[...]` sub-fields (savings/FD/refund interest,
> `NatofPassThrghIncome`, the four PF-proviso buckets, and `IntrstFrmOthers`) right where item 1
> (`GrossIncChrgblTaxAtAppRate`) reads it, so item 1 picks up the fix automatically — matching the
> exact "compute from the block's own final values" discipline the earlier `GrossIncChrgblTaxAtAppRate`
> fix established. `NatofPassThrghIncome`'s own underlying tax gap is already separately closed (see
> this document's own `os_pass_through_income` fix note above) — but the four PF-proviso fields and
> `IntrstFrmOthers` (NSC/bonds/securities interest) still reach GTI only via the generic
> `other_income` aggregate, not a dedicated, traceable path; that part of this finding is
> deliberately left open, out of scope for a disclosure-formula fix, and tracked here as a distinct
> follow-up (would need the same back-out-and-add-back treatment already applied to
> `os_pass_through_income`/`os_other_income_entries`). One new regression test in
> `tests/test_itr2_itd_builder.py` (`test_interest_gross_sums_all_nine_of_its_own_declared_sub_items`),
> confirmed via `git stash` to fail against pre-fix code (`3300 == 10800`, i.e. only the first three
> of nine sub-items were being summed). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/
> `test_cyla`/`test_capital_gains_loss_foundation` regression suite: 833 passed, only the same 6
> pre-existing failures (unrelated to this fix, not newly introduced).
>
> **Update (2026-09-09): the remaining "untraceable channel" gap is also fixed and verified.**
> `calculators/itr2.py` now explicitly adds `os_pf_interest_10_11_first_proviso +
> os_pf_interest_10_11_second_proviso + os_pf_interest_10_12_first_proviso +
> os_pf_interest_10_12_second_proviso + os_interest_from_others` to `r.other_sources_income`, right
> after the existing `os_pass_through_income` addition — the exact same fix pattern, applied to the
> sibling fields this finding named as still open. `draft_to_itr2_input.py`'s own
> `_map_os_pf_interest_provisos()`/`_map_os_interest_from_others()` already existed and correctly
> extracted these five amounts from `draft.otherSources.interest` for *disclosure* — but the
> underlying amount was never backed out of the generic `other_income` aggregate the way
> `os_machinery_plant_rent`/`os_pass_through_income`/`os_other_income_entries` already were, so
> without a matching back-out this fix would have double-taxed every PF-proviso/NSC/bonds/
> securities-interest taxpayer. The back-out block now also subtracts these five amounts, computed
> once (moved earlier in the function to where the back-out needs them, removing what was a
> duplicate second computation of the same four-tuple/scalar later in the same function). GTI
> inclusion is now traceable and independently verifiable against each field's own disclosed
> `IntrstSec10XI*Proviso`/`IntrstFrmOthers` total, rather than riding along invisibly inside a
> generic residual. Two new regression tests in `tests/test_itr2_itd_builder.py`:
> `test_os_pf_proviso_and_other_interest_are_taxed_not_just_disclosed` (calculator-level, mirroring
> `os_pass_through_income`'s own verification — taxable income must differ by exactly the disclosed
> amount) and `test_os_pf_proviso_interest_is_not_double_counted_via_the_draft_pipeline` (the real
> v2 draft pipeline, confirming the back-out and the add-back net to taxed-exactly-once, not zero
> and not double), both `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_draft_to_itr1_input`/`test_draft_to_itr2_input`
> regression suite: 764 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged). This closes the entire finding — nothing
> remains open here.

### New finding — `IncChargeableSpecialRates` (Schedule OS item 2) still incomplete despite this session's earlier fix

**Evidence:** `itd/itr2.py:1085-1090` sums 2ai+2aii+2b+2d (lottery/115BBJ/115BBE/OthersGross) but
omits **2c** (`TaxAccumulatedBalRecPF.TotalIncomeBenefit`, accumulated-PF income u/s 111 — correctly
taxed via the `_OS_HEAD_SI_SECTIONS` route in the calculator, but never folded into this disclosure
total) and **2e** (`PassThrIncOSChrgblSplRate`, structurally hardcoded to `0` — no mapper exists for
special-rate PTI-OS income at all).

**Impact:** item 2's own displayed total under-reports whenever a taxpayer has accumulated-PF income
disclosed in Schedule OS — same self-contradiction class as the two findings above, on the
special-rate side of the same schedule.

**Severity:** High (2c is an active, reachable gap; 2e is a lower-priority structural limitation with
no PTI-special-rate-OS mapper to source it from at all).

> **Fix status (2026-09-09): 2c is fixed and verified; 2e remains open, deliberately not attempted.**
> `IncChargeableSpecialRates` now includes `block["TaxAccumulatedBalRecPF"]["TotalIncomeBenefit"]`
> in its sum — no tax-computation change needed, since accumulated PF income already reaches GTI
> correctly via the calculator's own `_OS_HEAD_SI_SECTIONS` dispatch (confirmed: `"111"` is a member
> of that frozenset); this was purely a disclosure-arithmetic omission, the same class as the
> `InterestGross`/`GrossIncChrgblTaxAtAppRate` fixes earlier in this cycle. `PassThrIncOSChrgblSplRate`
> (2e) is now also included in the sum formula (as `+ 0` today) so the formula is complete-by-
> construction and self-corrects automatically the day a real mapper exists — but its own
> underlying value stays hardcoded `0`, unchanged. Re-confirmed the severity note's own assessment:
> no dispatch path for OS-head special-rate PTI exists anywhere in this engine today (unlike
> STCG/LTCG-head PTI entries, which already dispatch to Schedule SI at
> `calculators/itr2.py:968-977` by `pti.section`) — the correct rate for pass-through OS income
> depends on section 115UA(2)/115UB(1) proviso's "retains the underlying character" rule, which
> varies by what special-rate category the originating fund/trust itself earned; there is no
> existing `section`-code convention in `PTIEntry` to key that dispatch off, and inventing one is a
> genuine new-feature design, not a bug fix within this finding's own scope. Left open and
> re-documented rather than attempted. Regression test
> `test_inc_chargeable_special_rates_includes_accumulated_pf_income` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 689 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).
>
> **Update (2026-09-09): 2e is also fixed and verified — the finding is now fully closed.**
> `calculators/itr2.py`'s existing PTI dispatch loop already imported (but never used)
> `compute_115bbj`/`compute_115bba`/`compute_111` — a clear signal an OS-head branch was originally
> planned here and never finished. Added one, keyed by a new `PTI_OS_SPECIAL_RATE_SECTIONS`
> constant (`{"115BB", "115BBE", "115BBF", "115BBG", "115BBJ", "115BBA", "111"}`) — the subset of
> the existing `_OS_HEAD_SI_SECTIONS` that an OS-head PTI entry (pass-through income from a
> business trust/investment fund, section 115UA(2)/115UB(1) proviso: retains the SAME head and rate
> the fund itself earned it under) can plausibly carry. Deliberately excludes the NRI 115A-family
> "any other income chargeable at special rate" dropdown codes and 115E: both are
> `OSSpecialRateEntry`'s own disclosure surface for a taxpayer's own directly-received NRI-specific
> income (GDR dividends, FCCB interest), not an obvious category a pass-through fund's underlying
> income would itself be classified under — a narrower, more defensible scope than the full
> `_OS_HEAD_SI_SECTIONS` set, reusing only already-imported, already-tested rate functions. No
> separate GTI-inclusion change was needed: the existing unconditional `other_sources_income += ...
> income_head == "OS"` addition already counts every OS-head PTI entry regardless of rate
> classification (matching the identical, already-correct pattern the ordinary `si_entries`
> dispatch uses); the new entries' exclusion from the slab-tax base happens automatically via
> `si_result.surcharge_full_income`, the same existing mechanism. `_schedule_os()`
> (`itd/itr2.py`) now computes `PassThrIncOSChrgblSplRate` as the sum of OS-head PTI entries whose
> `section` is in `PTI_OS_SPECIAL_RATE_SECTIONS` (imported from the calculator — single source of
> truth, so disclosure can never disagree with what was actually taxed). Regression test
> `test_pti_os_head_entry_retaining_special_rate_character_is_taxed_via_schedule_si` (one
> 115BB-classified entry, one ordinary entry, confirming the special-rate entry is taxed via
> Schedule SI while the ordinary one stays slab-rate, and that GTI includes both) in
> `tests/test_itr2_itd_builder.py`. Verified via a scoped revert-and-restore (not `git stash`,
> since both touched files carry substantial unrelated uncommitted changes from earlier in this
> session that a full-file stash would also revert) — the new code was temporarily removed, the
> test confirmed to fail, then restored. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 700 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged). This was the last open finding from Phase 8's
> re-audit — all 26 are now closed.

### New finding — SchedulePTI misclassifies 111A/112A pass-through capital gains into the wrong sub-bucket

**Evidence:** `itd/itr2.py:3130-3136` always zeroes `STCG_Sec111A`/`LTCG_Sec112A` and routes the
entire amount into `STCG_Others`/`LTCG_Others` regardless of `item.section`. The tax rate itself is
correctly dispatched in the calculator (`calculators/itr2.py:927-936`, section-aware) — this is a
disclosure-classification bug only.

**Impact:** a 111A/112A PTI entry is misrepresented as "Others" in Schedule PTI, inconsistent with
Schedule SI's own 111A/112A line items for the identical income.

**Severity:** Medium.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_pti()` now routes each entry's amount
> to `STCG_Sec111A`/`LTCG_Sec112A` or `STCG_Others`/`LTCG_Others` using the exact same
> classification the calculator's own PTI dispatch loop already taxes it under
> (`calculators/itr2.py`'s `pti.section == "111A"` for STCG, `"112A" in pti.section.upper()` for
> LTCG) — mirroring, not inventing, a second classification rule, so Schedule PTI and Schedule SI
> can no longer disagree about which bucket the identical income belongs in. Regression test
> `test_schedule_pti_routes_111a_112a_pass_through_gains_to_their_own_sub_bucket` (four PTI entries:
> STCG/111A, STCG/other, LTCG/112A, LTCG/other) in `tests/test_itr2_itd_builder.py`,
> `git stash`-confirmed to fail pre-fix. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 690 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged).

### New finding — ScheduleEI's `IncNotChrgblToTax` holds the wrong value; `TotalExemptInc` doesn't sum its own declared components

**Evidence:** `itd/itr2.py:2704-2707` sets `IncNotChrgblToTax` (item 4, "DTAA-exempt income") equal
to `interest_inc` (item 1's own value) even though the paired `IncNotChrgblAsPerDTAADtls` detail
array is always empty (no mapper populates it for ITR-2 at all) — item 4 should be 0 (or the sum of
that array, once built), not a duplicate of item 1. `TotalExemptInc` (item 6) never adds
`IncNotChrgblToTax`/`PassThrIncNotChrgblTax` into its own sum despite the form's own stated "Total
(1+2+3+4+5)" formula.

**Impact:** any return disclosing exempt interest (PPF/SSY/tax-free-bond/NRE — very common) shows an
internally inconsistent Schedule EI: item 4 nonzero with no supporting detail, item 6 not equal to
the sum of items 1-5. `TotalExemptInc`'s actual tax-relief use elsewhere is independently computed
and correct — this is an arithmetic-disclosure bug, not a tax-amount one.

**Severity:** Medium-High.

> **Fix status (2026-09-09): fixed and verified.** Confirmed against the official form (Schedule EI:
> item 4 = "III Total Income from DTAA claimed as not chargeable to tax", the sum of the paired
> detail rows immediately above it — not item 1). `IncNotChrgblToTax` now computes from
> `IncNotChrgblAsPerDTAADtls` itself (`sum(row["AmountOfIncome"] ...)`), correctly `0` today since no
> mapper populates that array for ITR-2 yet — self-corrects automatically the day one exists, rather
> than needing a second, independently-maintained sum. `PassThrIncNotChrgblTax` (item 5) similarly
> has no backing concept in this engine's PTI data model (every `PTIEntry` today is taxable
> pass-through income, not a "not chargeable" classification) and stays `0` for the identical
> reason — both left as genuinely out-of-reach structural gaps, matching the finding's own framing
> ("0, or the sum of that array, once built"), not attempted here. `TotalExemptInc` now sums all
> five items (1+2+3+4+5) per the form's own declared formula, not just items 1-3. Caught and fixed a
> real bug while writing the fix: `sum(..., 0)` on an empty generator returns a plain `int`, which
> crashes `_to_rupees()`'s own `Decimal.quantize()` call — corrected to `sum(..., _ZERO)`. Regression
> test `test_schedule_ei_inc_not_chrgbl_to_tax_and_total_exempt_inc_formulas_are_correct` in
> `tests/test_itr2_itd_builder.py`, `git stash`-confirmed to fail pre-fix. Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*` regression suite: 691 passed, only the same 5
> pre-existing `test_itr2_input_validation.py` HUF-verification failures (unrelated, unchanged).

### New finding — two more real, user-suppliable data points silently dropped

`ExemptIncome.other_description` (free-text nature of "other exempt income") is never read by
`_schedule_ei()` — `OthersInc.OthersIncDtls` is hardcoded `[]` even though the scalar total is
correctly populated. The per-assessment-year PF accumulated-balance breakdown is collapsed to
scalar totals before reaching `ITR2Input`, so `TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls` (the
form's own per-year sub-table) is always `[]` even when the user entered full per-year detail.
Aggregate totals/tax are correct in both cases — completeness gaps per this project's own "implement
every schema field" standard, not tax-correctness bugs.

**Severity:** Medium.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_ei()` now emits one `OthersIncDtls`
> row (`Description`/`OthAmount`) whenever `other_exempt > 0`, using `other_description` when
> supplied and a sensible default ("Other exempt income") otherwise — `Category`/`SubCategory`
> (optional per schema, a 9-value and a 50-value enum respectively) are deliberately omitted rather
> than fabricated, since `ExemptIncome` never captured which specific statutory sub-clause applies.
> For the PF per-year breakdown: added `OSAccumulatedPFEntry` (`app/schemas/itr2.py`) and a new
> `ITR2Input.os_pf_accumulated_entries` field; `draft_to_itr2_input.py`'s `_map_os_accumulated_pf()`
> now returns the real per-year rows alongside its existing aggregate totals (previously computed
> the totals and discarded the rows they came from); `_schedule_os()` now emits
> `TaxAccmltdBalRecPFDtls` from this new field instead of hardcoding `[]`. Four new regression tests
> in `tests/test_itr2_itd_builder.py`:
> `test_schedule_ei_others_inc_dtls_reports_real_description_not_empty_array` (with and without a
> supplied description), `test_schedule_os_tax_accumulated_bal_rec_pf_reports_real_per_year_breakdown`
> (builder-level, two assessment years), and
> `test_accumulated_pf_per_year_breakdown_reaches_json_via_the_draft_pipeline` (the real v2 draft
> pipeline, confirming `_map_os_accumulated_pf()`'s own wiring) — the pre-fix code couldn't even
> construct these tests' fixtures at all (`OSAccumulatedPFEntry` didn't exist), the strongest
> possible confirmation the fix was genuinely needed. Updated one pre-existing test
> (`test_schedule_os_serializes_lottery_pf_and_gift_income`) to include the new
> `TaxAccmltdBalRecPFDtls: []` key its own assertion now needs, since it exercises the calculator-
> only path (no per-year entries supplied). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 694 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged).

### Areas re-checked, confirmed clean

The `os_other_income_entries` fix itself: independently re-verified via hand-traced arithmetic that
its own back-out logic correctly avoids double-counting between the generic aggregate,
`os_machinery_plant_rent`, and `os_other_income_entries` specifically — the newly-found gaps above
are in categories that fix never claimed to cover. Confirmed no other code path bypasses
`draft_to_itr2_input.py` to construct `ITR2Input`/`OtherSourcesIncome` directly. Gift/56(2)(x)
totaling, PTI HP/OS-head routing, unexplained-income (68/69 series) taxation, Section 89A
disclosure-only treatment, race-horse balance logic, and the always-empty `ExcNetAgriIncDtls`
(structurally out of scope, no source data model) all confirmed correct.

## 20.6 Foreign, AL, AMT, AMTC, 5A, ESOP, tax-payment schedules

### New finding — `ScheduleAMT.DeductionClaimUndrAnySec` always emits 0 via a nonexistent-attribute fallback, on 100% of the population this schedule serves

**Evidence:** `itd/itr2.py:2973-2983`: `"DeductionClaimUndrAnySec":
_to_rupees(getattr(amt, "total_deductions", _ZERO))`. `amt` is an `AMTResult`
(`app/engine/schedules/amt.py:40-52`), which has no `total_deductions` field at all — the `getattr`
default silently returns 0 unconditionally. The real figure is recoverable as
`amt.adjusted_total_income - result.taxable_income`, but nothing computes or stores it that way.
`_schedule_amt()` only returns non-`None` when `amt.amt_applicable` is `True`, which the engine only
sets when the real addback is nonzero (`amt.py:136`) — meaning **every single return for which
Schedule AMT is emitted at all** has a guaranteed-wrong `DeductionClaimUndrAnySec`, directly
self-contradicting the correctly-computed sibling field `AdjustedUnderSec115JC` two lines below on
the same object.

**Impact:** every AMT-applicable ITR-2 return discloses ₹0 "deduction claimed under section" on the
one schedule that exists specifically to disclose it, while showing the correct nonzero adjusted
total income immediately after.

**Severity:** CRITICAL — guaranteed wrong on 100% of the affected population.

> **Fix status (2026-09-09): fixed and verified.** `_schedule_amt()` (`app/engine/itd/itr2.py`) now
> computes `DeductionClaimUndrAnySec` as `adjusted_total_income - result.taxable_income` — exactly
> the finding's own suggested recovery, confirmed exact (not merely approximate) by tracing
> `compute()`'s own arithmetic (`app/engine/schedules/amt.py`): `adjusted_income = income +
> addition_total` where `income` is passed in as precisely `result.taxable_income` at the
> calculator's own call site, with no intermediate rounding on either side of the subtraction. No
> change to `amt.py` itself was needed or made — this stays a builder-only fix, confirmed safe for
> ITR-3 (which also calls `compute_amt()`) since ITR-3 has no `_schedule_amt()`/`_schedule_amtc()`
> functions at all yet and doesn't serialize this schedule. One new regression test in
> `tests/test_itr2_itd_builder.py`
> (`test_schedule_amt_deduction_claim_reflects_the_real_addback_not_zero`), asserting both the
> correct addback figure and the form's own D1-style chain identity (`TotalIncItemPartBTI +
> DeductionClaimUndrAnySec == AdjustedUnderSec115JC`) — confirmed via `git stash` to fail against
> pre-fix code (`0 == 2500000`). Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/
> `test_capital_gains_loss_foundation` regression suite: 834 passed, only the same 6 pre-existing
> failures (unrelated to this fix, not newly introduced).

### New finding — `ScheduleTR1`'s DTAA/non-DTAA relief split double-counts when the same country has TR1 entries under mixed relief sections

**Evidence:** `itd/itr2.py:2797-2798` computes `dtaa`/`non_dtaa` by re-searching the *entire*
`input_data.tr1_entries` list for entries matching each row's `country_code` and checking whether
*any* such entry uses a DTAA-type section — instead of reading each row's own already-carried
`ReliefClaimedUsSection`. Nothing prevents two `TR1Entry` rows sharing a country with different
relief sections (a realistic scenario for a taxpayer with two income sources in the same country
under different TINs) — in that case, both rows get counted into *both* `dtaa` and `non_dtaa`.

**Impact:** `TotalTaxReliefOutsideIndia` (and its DTAA/non-DTAA split) overstates the real relief for
any taxpayer with more than one Schedule TR1 row in the same country under mixed relief sections,
and becomes internally inconsistent with the individual `ScheduleTR` rows sitting next to it in the
same JSON.

**Severity:** CRITICAL (silent overstatement of a disclosed relief total).

> **Fix status (2026-09-09): fixed and verified.** `_schedule_tr1()` (`app/engine/itd/itr2.py`) now
> reads each row's own `item.relief_section` directly inside the same loop that builds its `rows`
> entry, instead of re-searching the whole `tr1_entries` list by country code — a per-row test
> instead of a per-country one, eliminating the double-count entirely. Caught and fixed an
> incidental type bug while writing the regression test: the rewrite's first attempt initialized
> the running totals from `_ZERO` (a `Decimal`), which silently upgraded the running sum from `int`
> to `Decimal` — numerically identical but schema-INVALID, since the official schema's integer
> fields reject a `Decimal` instance even when its value is a whole number; caught immediately by
> an *existing* test (`test_schedule_fa_fsi_tr_derive_real_country_name_from_the_code`) failing on
> re-run, fixed by initializing from plain `0` instead, matching what `_to_rupees()`'s own `int`
> return type requires. One new regression test in `tests/test_itr2_itd_builder.py`
> (`test_schedule_tr1_dtaa_split_is_not_double_counted_across_mixed_relief_sections`), confirmed via
> `git stash` to fail against pre-fix code (`12000 == 8000`, i.e. double-counted). Full combined
> `test_itr1_*`/`test_itr2_*`/`test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation`
> regression suite: 835 passed, only the same 6 pre-existing failures (unrelated to this fix, not
> newly introduced).

### New finding — Schedule TDS3's `AadhaarOfBuyerTenant` is captured on input but has no path to the JSON

**Evidence:** `TDS3Entry.tenant_aadhaar` is correctly mapped from the draft, but `_schedule_tds3()`
builds its output from a *different* object (`TDS3FilingDetail`) that has no Aadhaar field at all —
the captured value is a dead end.

**Impact:** a taxpayer who supplies the buyer/tenant's Aadhaar (a legitimate optional Schedule TDS3
field) never has it appear in the filed JSON.

**Severity:** Medium/High (real data dropped, but an optional field alongside a correctly-emitted
required PAN — narrower than the CRITICAL findings above).

> **Fix status (2026-09-09): fixed and verified.** `_schedule_tds3()` (`app/engine/itd/itr2.py`)
> now conditionally includes `AadhaarOfBuyerTenant` from `entry.tenant_aadhaar` (the paired
> `TDS3Entry`, zipped with `TDS3FilingDetail` by index) whenever supplied, omitted entirely when
> not — matching the schema's own optional, pattern-constrained (`[0-9]{12}`) field exactly and the
> same "omit when empty" convention this function already uses for `PANofOtherPerson`/
> `AadhaarOfOtherPerson`. One new regression test in `tests/test_itr2_itd_builder.py`
> (`test_schedule_tds3_serializes_the_buyer_tenants_aadhaar`), confirmed via `git stash` to fail
> against pre-fix code (`KeyError: 'AadhaarOfBuyerTenant'`). Full combined `test_itr1_*`/
> `test_itr2_*`/`test_itr4_*`/`test_cyla`/`test_capital_gains_loss_foundation` regression suite: 836
> passed, only the same 6 pre-existing failures (unrelated to this fix, not newly introduced).

### New findings — two input-validation gaps let malformed values reach the builder undetected until ITD-side rejection

`ESOPDeferralInput.dpiit_registration_number` has no pattern constraint, though the official
schema's `DPIITRegNo` requires `DIPP[0-9]{3,5}` — any other format passes Pydantic and fails only at
ITD submission. `TDS2Entry.head_of_income` is a bare `Optional[str]` (unlike its correctly
`Literal`-typed sibling on `TDS3Entry`) — a value outside the schema's closed enum reaches the
builder validly per Pydantic but fails the official schema.

**Severity:** Medium (surfaces as a late, opaque submission-time rejection rather than silent data
corruption, but a real gap in this codebase's usual practice of enforcing CBDT enums at the Pydantic
layer).

> **Fix status (2026-09-09): fixed and verified.** `ESOPDeferralInput.dpiit_registration_number`
> now enforces `^DIPP[0-9]{3,5}$` (anchored, matching this codebase's own convention for other
> identifier patterns — the official schema's own `DIPP[0-9]{3,5}` isn't anchored, but a real DPIIT
> registration number always takes exactly that literal form). One pre-existing test
> (`test_ESOP_001_balance_arithmetic_fails`) used a placeholder value (`"DPIIT1"`) that never
> matched the real format at all — updated to a valid one (`"DIPP12345"`) so it can still reach the
> balance-arithmetic check it actually exercises. For `TDS2Entry.head_of_income`: re-verified the
> finding's own claim before fixing it — its cited "correctly Literal-typed sibling on `TDS3Entry`"
> is actually never read by `_schedule_tds3()` at all (which sources `HeadOfIncome` from the
> unrelated, separately-and-correctly-typed `TDS3FilingDetail.head_of_income` instead); TDS2's own
> real enum is `TDSOthThanSalaryDtls.HeadOfIncome` (`HP`/`CG`/`OS`/`EI`/`NA` — five values,
> including `NA`, distinct from TDS3's own four-value enum with no `NA`). `TDS2Entry.head_of_income`
> is now `Optional[Literal["HP", "CG", "OS", "EI", "NA"]]`, matching the schema it's actually
> serialized against, not the sibling type the finding named. Two new regression tests in
> `tests/test_itr2_itd_builder.py`: `test_esop_deferral_rejects_dpiit_registration_number_with_wrong_format`
> and `test_tds2_entry_rejects_head_of_income_outside_the_official_enum` — since both fixes are pure
> Pydantic-construction-time rejections (no downstream JSON to diff), verified instead by
> reproducing the exact pre-fix model definitions in isolation and confirming they accepted the
> same garbage values these tests now reject. Full combined `test_itr1_*`/`test_itr2_*`/`test_itr4_*`
> regression suite: 699 passed, only the same 5 pre-existing `test_itr2_input_validation.py`
> HUF-verification failures (unrelated, unchanged).

### Areas re-checked, confirmed clean (or confirmed still accurately documented)

§9.3 (AMTC utilization-direction issue, "left unfixed pending tax-law verification") and §9.3a
(field-name fix) both confirmed still accurately described, no change needed. §12a.1
(`ImmovableDetails` always `[]`) confirmed still open, unfixed. §10.2 (Schedule FA, 3 of 10
categories, fails closed for the rest) confirmed still open, unfixed but safe. §13.1 (ESOP
event-level gap) confirmed still matches the doc's characterization. §12.2 (Schedule 5A's `amount *
2` Portuguese-Code apportionment) reconfirmed legally correct, not a bug. `ScheduleTDS1`/`ScheduleIT`/
`ScheduleTCS` field coverage, TDS2/TDS3 ownership attribution, and `ScheduleAL.MovableAsset`'s
required fields all cross-checked and found correctly sourced from real data.

---

# 21. Final assessment

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

> **Update (2026-09-08): a full, independent re-audit driven strictly by the official form's own
> page order — reading every Part/Schedule of the actual ITR-2 form PDF, then cross-referencing
> every field against the official JSON schema, then the frontend and backend — found that the
> "every P0 finding is closed" conclusion above does not hold. This form-order-first method (as
> opposed to the prior finding-driven audit cycle, which re-verified and extended existing
> findings but did not independently re-derive every schedule's field list from the form and
> schema from scratch) surfaced ten new CRITICAL-severity findings, several in schedules or fields
> the prior cycle had not examined at all.** Full detail is in each finding's own section; summary
> for anyone using this document as a punch list:
>
> **New CRITICAL findings (all schema-invalid-JSON or required-population-blocking; none affect
> the bottom-line tax amount unless noted):**
> 1. §6.4 — `PropertyOwnerOther` (Schedule HP) captured on the frontend, never serialized; silent
>    information loss for any non-Self/Minor/Spouse property owner.
> 2. §3.10 — the top-level `Schedule115AD` scrip-detail table is never built at all; FII/FPI
>    112A-eligible scrips land in the resident taxpayer's `Schedule112A` table instead, despite the
>    frontend/draft already correctly modeling the split end-to-end.
> 3. §3.4a — Schedule OS's own headline total, `GrossIncChrgblTaxAtAppRate` (item "1", the sum
>    "1a+1b+1c+1d+1e"), is hardcoded to `0` while its five components and the schedule's own item
>    "6" total are correctly populated a few lines later — visibly self-contradictory, and wrong
>    for the majority of real returns (any dividend/interest/rental/gift/other income).
> 4. §8.0 — Schedule VIA (`DeductUndChapVIA`/`UsrDeductUndChapVIA`) never populates any of its
>    ~20 named per-section fields (only a `TotalChapVIADeductions` scalar), is missing three
>    schema-required fields, and emits one extra key the schema doesn't define at all —
>    schema-invalid whenever *any* Chapter VI-A deduction is claimed, likely the highest-reach
>    single finding in this document given how close to universal 80C/80D claims are.
> 5. §8.0a — none of the six dedicated Chapter VI-A detail schedules (80D, 80G, 80GGA, 80GGC,
>    80DD, 80U) are built at all, compounding §8.0.
> 6. §9.3a — `ScheduleAMTCDtls` (AMT credit carry-forward rows) uses five field names that don't
>    match any of the schema's six required field names at all, and `TotSetOffEys` (a monetary
>    total) is populated with a row count.
> 7. §18a.1 — `AssetOutIndiaFlag` (Part B-TTI, required) is hardcoded `"NO"` regardless of Schedule
>    FA content, directly contradicting a populated Schedule FA in the same JSON.
> 8. §18a.1 — Part B-TTI emits `"GrossTaxPayable"`, a key that does not exist anywhere in the
>    schema — unconditional, on every return.
> 9. §18b.1 — the Verification block's `AssesseeVerPAN` pattern structurally requires an
>    individual's PAN (4th character "P"); every HUF ITR-2 return supplies the HUF's own PAN
>    (4th character "H") with no separate Karta-PAN field to draw from instead — a 100% failure
>    rate for the entire HUF taxpayer population on this form.
> 10. §3.9 — Schedule CG's own Table E (current-year capital-loss set-off) and Table F (quarterly
>     accrual) are both unconditionally hardcoded to zero-value stubs (Table E rated High rather
>     than CRITICAL only because the bottom-line tax figures are independently sourced and
>     unaffected).
>
> **Also newly found, High severity** (§4/§10.1's country-code gaps affecting Part A-GEN/HP/FSI/
> TR/FA; §7.5's Schedule EI `IncNotChrgblToTax` mislabeling; §12a.1's Schedule AL immovable-property
> drop; §18a.1's Part B-TI STCG-bucket swap and un-wired AMT-credit fields) plus several Medium/P2
> items — see each section for full evidence.
>
> **Revised classification: several of today's ten CRITICAL findings (§8.0/§8.0a especially) are
> higher-reach than any single finding the original P0 list identified — Chapter VI-A deductions
> are claimed by a large majority of real taxpayers, and that entire disclosure surface is
> currently non-functional at the schema level.** The corrected picture is not "P0 surface closed,
> remaining work is P1 polish" — it is that a systematic, schema-first, form-order re-audit
> continues to surface CRITICAL-severity gaps in schedules the prior cycle considered done, which
> strongly suggests the *right next step* is another full pass of this same methodology (every
> remaining schedule, re-verified field-by-field against the schema, not just against this
> document's own prior findings) before concluding any part of ITR-2 is production-ready — matching
> this document's own repeatedly-demonstrated lesson (Schedule HP, Schedule CG, Schedule FA all
> individually needed a second, code-level re-audit after their first "fixed" pass to find what the
> first pass missed).
>
> **Update (2026-09-09): findings #4 (Schedule VIA, §8.0) and #2 (Schedule 115AD, §3.10) from the
> list above are fixed and verified** — see each section's own "Fix status (2026-09-09)" note.
> Eight of the ten new CRITICAL findings remain open, plus §8.0a (six Chapter VI-A detail
> schedules, a separate and larger item). The lesson this update's own text draws — that a second,
> independent re-audit keeps surfacing what the first pass missed — applies to these two fixes too:
> they were not re-audited against the schema a third time after fixing; treat them as fixed-and-
> tested, not as re-confirmed-clean the way a full follow-up pass would establish.
>
> **Update (2026-09-09, second pass): findings #7 (`AssetOutIndiaFlag`) and #8 (`"GrossTaxPayable"`)
> from the list above are also fixed and verified.** Finding #8 as originally stated was itself
> wrong, though — `GrossTaxPayable` is a real, required schema field, not a nonexistent key; the
> real bug (hardcoded `0` instead of `max(item 1d, GrossTaxLiability)`) is fixed, and the finding's
> own retraction is documented in place at §18a.1 rather than silently corrected. This is exactly
> the lesson the paragraph above already draws, demonstrated directly: this fix's own first attempt
> (deleting the key) would itself have been wrong, and was caught only because the schema was
> re-checked before committing rather than trusted from the earlier audit pass. Four of ten new
> CRITICAL findings now closed; six remain, plus §8.0a.
>
> **Update (2026-09-09, third pass): finding #3 (`GrossIncChrgblTaxAtAppRate`, §3.4a) is also fixed
> and verified — five of ten new CRITICAL findings now closed.** While writing the regression test
> for this fix, found and documented (not fixed — out of scope for this pass) a new, separate,
> CRITICAL-candidate bug: `os_other_income_entries` ("any other income," Schedule OS item 1e) is
> disclosed in the JSON but never actually summed into taxable `other_sources_income` by the
> calculator at all — a real undertaxation gap. See §3.4a's own fix note for full evidence. Five
> new CRITICAL findings remain open, plus §8.0a and this newly-found "any other income" gap.
>
> **Update (2026-09-09, fourth pass): finding #6 (`ScheduleAMTCDtls`, §9.3a) is also fixed and
> verified — six of ten new CRITICAL findings now closed.** Beyond the field-naming/`TotSetOffEys`
> fix originally scoped, found and fixed a second, more severe, previously-undocumented bug in the
> same function while implementing it: multi-year AMT credit rows each independently claimed the
> *full* current-year AMT-tax offset capacity instead of tracking how much earlier (older) rows had
> already consumed it — over-crediting utilization for any return with more than one year of
> brought-forward AMT credit. Fixed via FIFO processing (oldest year first) against a single
> capacity accumulator. See §9.3a's fix note for full evidence. Four new CRITICAL findings remain
> open, plus §8.0a and the `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, fifth pass): finding #1 (`PropertyOwnerOther`, §6.4) is also fixed and
> verified — seven of ten new CRITICAL findings now closed.** Fixed exactly as originally
> remediated, including the suggested `validate_property_owner_other` model validator (mirroring
> the existing `co_owned`/`co_owner_details` "flag with no detail" precedent). See §6.4's fix note
> for full evidence. Three new CRITICAL findings remain open, plus §8.0a and the
> `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, sixth pass): finding #9 (`AssesseeVerPAN`, §18b.1) is also fixed and
> verified — eight of ten new CRITICAL findings now closed.** Fixed exactly as originally
> remediated: a new `karta_pan` field on `ITR2FilingProfile`, required by a model validator
> whenever `assessee_status == HUF`, used by `_verification_block()` in place of the HUF's own
> PAN. See §18b.1's fix note for full evidence. Two new CRITICAL findings remain open — #10
> (Schedule CG's Table E/F, §3.9) and the Part B-TI STCG-bucket swap — plus §8.0a and the
> `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, seventh pass): the Part B-TI STCG-bucket swap (§18a.1, the finding at the
> top of this section listed alongside #7/#8) is also fixed and verified — nine of ten new
> CRITICAL findings now closed.** Fixed exactly as remediated: `_partb_ti()` now takes
> `input_data` and branches on `is_fii_fpi` the same way `_schedule_cg()`/`_schedule_115ad()`
> already do. See §18a.1's fix note for full evidence. One new CRITICAL finding remains open — #10
> (Schedule CG's Table E/F, §3.9) — plus §8.0a and the `os_other_income_entries` undertaxation gap.
>
> **Update (2026-09-09, eighth pass): finding #10 (Schedule CG's Table E/F, §3.9) is also fixed and
> verified — all ten of ten new CRITICAL findings from the 2026-09-08 form-order re-audit are now
> closed.** Table E's fix required a refactor of the shared `cyla.py` engine (also used by ITR-3)
> to expose the within-Schedule-CG intra-head loss set-off matrix it was already computing
> internally but discarding to aggregates — confirmed additive/non-breaking via `test_cyla.py`'s
> full 17-test suite staying green. Table F now buckets real per-transaction gains by transfer-date
> quarter, with a documented small approximation for two schedule-level refinements (50CA deeming,
> 112A grandfathering) that don't apply per-transaction. See §3.9's fix notes for full evidence.
> **What remains open across this entire document: §8.0a (six Chapter VI-A detail schedules) and
> the `os_other_income_entries` undertaxation gap — both already tracked, neither part of the
> 2026-09-08 re-audit's ten-item list.**
>
> **Update (2026-09-09, ninth pass): §8.0a is also fixed and verified.** All six Chapter VI-A
> detail schedules (80D, 80G, 80GGA, 80GGC, 80DD, 80U) are now built, wiring `ITR2Input`/
> `app/engine/calculators/itr2.py` into the same shared per-section eligibility engine ITR-1
> already uses for these schedules in production, plus six new `_schedule_80*()` builder
> functions in `app/engine/itd/itr2.py` adapted from ITR-1's own proven implementation. Also fixed
> a real incidental bug found along the way: `is_80dd_severe`/`is_80u_severe` read a
> `Chapter6ADeductions` field that is never actually populated, silently defaulting every
> taxpayer to non-severe. See §8.0a's own fix note for full evidence. **The only item remaining
> open across this entire document is now the `os_other_income_entries` undertaxation gap
> (§3.4a).**
>
> **Update (2026-09-09, tenth pass): the `os_other_income_entries` undertaxation gap is also fixed
> and verified — every finding tracked anywhere in this document is now closed, from the original
> audit's P0/P1 list through the 2026-09-08 form-order re-audit's ten CRITICAL findings and §8.0a.**
> `os_other_income_entries` now reaches taxable income in `app/engine/calculators/itr2.py`. The
> real fix needed more than the one-line addition the original note suggested: tracing the v2 draft
> pipeline first found that the same rows were already reaching GTI a second way, through a generic
> aggregate the mapper shares with ITR-1 — fixed by widening that mapper's existing MACHINERY_RENT/
> PASS_THROUGH exclusion to also exclude `os_other_income_entries`'s own rows, avoiding a
> double-taxation regression that a narrower fix (matching how the original finding's own test was
> written) would have introduced for real taxpayers. See §3.4a's own fix note for full evidence.
> **This closes the last open item in this document.**
>
> **Update (2026-09-09, Phase 8 re-audit): that "last open item" framing did not survive the
> standing plan's own local-correctness exit gate.** A full independent re-audit — required before
> this section's classification could honestly be upgraded to production-ready, per the plan's own
> "if not clean, loop back into another fix cycle" instruction — found **26 new findings, roughly
> half CRITICAL**, several of which directly contradict specific "confirmed correct" claims made
> earlier in this same document, on this same day. Full write-up: the new §20. The two most
> consequential: Schedule CYLA's own six capital-gains sub-baskets are unconditionally zero
> (contradicting Schedule BFLA in the same JSON, for every return with any STCG/LTCG income — this
> form's primary case) and Section 112A gain is corrupted by double-counted deductions on the
> primary scrip-entry UI (turning real gains into fabricated losses). Neither was caught by any
> prior pass, including the exhaustive 2026-09-08 form-order re-audit, because both require tracing
> data through the *calculator's own result object*, not just the schema/builder pairing every
> prior pass (including this document's original methodology) checked.
>
> **Revised classification: NOT production-ready.** The pattern across every re-audit this
> document has run (Phase 4, the 2026-09-08 pass, and now this one) is the same: a systematic,
> independent, schema-first pass keeps surfacing CRITICAL-severity defects in areas a prior pass
> considered closed. That pattern itself is the strongest evidence that another full fix-and-verify
> cycle against §20's 26 findings, followed by yet another independent re-audit, is required before
> this document's classification can honestly change — not a smaller "polish" pass. Continuing
> that cycle (fix §20's findings one at a time with the same test-first/`git stash`-verified/full-
> regression discipline every fix in this document has used, then re-audit again) is this
> document's own recommended next step.
