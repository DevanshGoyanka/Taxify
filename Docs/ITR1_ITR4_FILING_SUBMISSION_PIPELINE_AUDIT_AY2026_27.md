# ITR-1/ITR-4 Filing & Submission Pipeline Audit (AY 2026-27)

**Date:** 2026-09-03
**Scope:** the code that runs *after* a correct CBDT JSON has been generated —
`app/eri/` (credential resolution, Digest computation, Type-3 JSON export/acknowledgement),
`app/filing_automation/` (the Type-3 Playwright submission worker + uploader), and
`app/routers/filing.py` (the unified filing API). This is deliberately the **complement** of
the earlier ITR-1/ITR-4 audits (`ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`,
`ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`), which covered *compute → JSON
generation* in exhaustive depth but explicitly stopped short of the submission mechanism
itself.

**Methodology, consistent with the earlier audits:** read the primary ITD/ERI reference
documents (`Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/*.pdf` — the
Digest Generation SOP and the ERI API Specification) before trusting any in-repo description
of the algorithm, then read the actual implementation files in full and cross-check against
both the primary source and each other, watching for the same bug classes that produced real
findings in the compute audits: hardcoded placeholders substituting for real data, silently
unreachable-vs-reachable fallback defaults, and a frontend restriction not mirrored
server-side.

## 1. Digest computation — verified correct against the primary source

`app/eri/digest.py`'s `compute_digest()` was cross-checked line-by-line against
`Digest_generation_ERI 2 (2).pdf` §5.3 (the official ERI Type-3 onboarding SOP). The primary
source specifies: minify the JSON (sorted keys, no interstitial whitespace), locate the
`Digest` field and replace it with the placeholder `"-"`, then compute **HMAC-SHA256** —
*keyed with the ERI secret key*, not a bare hash — iterated a credential-specified number of
times, then Base64-encoded. `compute_digest()` implements this exactly, including the
"read → minify+placeholder → iterated keyed hash → Base64" step ordering, and
`app/engine/itd/common.py::_compute_digest` is a thin, single delegate to it — there is no
second Digest computation path anywhere in the codebase (confirmed by grep: `app/eri/digest.py`
is the sole definition of a function matching `compute_digest`/`_compute_digest`).

**One documentation staleness fixed, not a code bug**: `CLAUDE.md`'s architecture section
described the Digest as *"SHA-256 over the sorted JSON"* — true only in the sense that SHA-256
is HMAC's underlying hash, but omitting the HMAC keying and iteration entirely is materially
misleading (a bare SHA-256 over the JSON, with no secret key, would never validate against the
ITD portal). Corrected to describe the actual algorithm.

## 2. Credential resolution (`app/eri/config.py`) — well-designed, one gap closed

The credential resolver was already, on inspection, unusually careful: its own docstrings and
comments cite three *specific*, already-fixed prior defects (an unsuffixed `ERI_BASE_URL`
module constant that silently always resolved to the UAT default regardless of `ERI_ENV`; the
same defect for `ERI_USER_ID`; a symmetric-key fallback that used to default to a hardcoded
placeholder that would silently produce an undecryptable password). `get_eri_base_url()`
explicitly states its design principle: *"there is deliberately no default — a wrong gateway
must fail, not be guessed."*

**Gap found**: `get_eri_credentials()` itself did not follow that same principle for the two
inputs that select *which* of the four coexisting credential sets to use in the first place —
`ERI_MODE` defaulted to `"type3"` and `ERI_ENV` defaulted to `"production"` when either was
unset or blank. Since all four `(mode, environment)` credential bundles live in the same
`.env` file simultaneously (by this project's own explicit design, so an operator can switch
modes by flipping two variables rather than editing secrets), a blanked `ERI_ENV` would not
fail to resolve — it would silently resolve the **production** bundle instead of the intended
one. This is not a hypothetical: `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`'s own "Recovery
incident" section documents a real prior incident where a careless full-file `.env` rewrite
blanked several secrets (`PORTAL_ENCRYPTION_KEY`, `ERI_CLIENT_SECRET_TYPE2_UAT`,
`ERI_SYMMETRIC_KEY`) — had `ERI_ENV` been blanked the same way while the production default was
in effect, the failure would not have been loud (a startup crash) but silent (an app that boots
fine and quietly starts stamping/signing everything with production credentials).

**Fix**: `ERI_MODE`/`ERI_ENV` are no longer defaulted — both must be explicitly set, or
`get_eri_credentials()` raises `ValueError` immediately, matching `get_eri_base_url()`'s
existing "fail loudly, never guess" principle. Verified against the real `.env` (which always
sets both explicitly) that this changes nothing about normal operation — `assert
_credentials_at_startup()` and the real `get_eri_credentials()` call both still resolve
`mode=type3, env=uat` correctly after the fix.

**Tests added** (`tests/test_eri_config.py`, new file): missing/blank `ERI_MODE` raises;
missing/blank `ERI_ENV` raises (rather than silently defaulting to production); explicit values
still resolve normally (regression fence). All 5 pass; the app's real startup path re-verified
manually against the actual `.env` after the change.

**Not touched, dead code noted for completeness**: `app/eri/type2/client.py::get_eri_mode()`
reads the same `ERI_MODE` env var but interprets it under a completely different, undocumented
vocabulary (its docstring claims `"real"`/`"mock"` semantics that the function doesn't actually
implement — it just lowercases whatever `ERI_MODE` holds). Confirmed via grep that this function
is never called anywhere in the codebase — genuinely dead, and Type-2 work is explicitly
deferred to next season, so left alone rather than fixed or removed.

## 3. `app/engine/filing_orchestrator.py` — confirmed no divergent second compute path

The Type-3 JSON export (`app/eri/type3/json_exporter.py`) calls
`app.engine.filing_orchestrator.produce_itd_json`, a name that doesn't appear anywhere in the
extensive compute-pipeline audits (which worked against `filing_gateway_v2.generate_cbdt_json`
directly). Read in full to confirm this wasn't a second, possibly-diverged reimplementation of
the compute pipeline — it is not: `produce_itd_json` is a thin, mode-agnostic wrapper that
validates the form is one of ITR-1/2/4 (rejecting ITR-3 explicitly, matching the established
"not yet on the canonical pipeline" status), then delegates directly to
`filing_gateway_v2.generate_cbdt_json` — the exact same function, exact same call, that every
finding in the earlier compute audits was made against. No new correctness surface here; this
confirms the filing path reuses the already-audited compute path rather than re-deriving it.

**Documentation staleness fixed** (code was already correct; only the plan doc's Phase 2 entry
was stale): `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`'s Phase 2 section, written 2026-08-20,
claims the orchestrator "routes ITR-1 → v2 and ITR-4 → legacy" (i.e., a *different* gateway per
form). The current code routes ITR-1, ITR-2, and ITR-4 through the same single
`generate_cbdt_json` branch — ITR-4 was migrated onto the v2 canonical pipeline in a later,
undocumented pass, consistent with `CLAUDE.md`'s current architecture description and with this
whole session's ITR-4 compute audit (which worked exclusively against `filing_gateway_v2.py`'s
ITR-4 functions). Corrected with an inline note rather than silently edited, per this
repository's established documentation practice.

## 4. Type-3 JSON export (`app/eri/type3/json_exporter.py`) — no defects found

Read in full. Well-engineered: atomic write (temp `.partial` file + `Path.replace()`, so a
crash mid-write can never leave a half-written JSON at the real filename), a digest-presence
guard (`_require_filing_digest`) that rejects a placeholder or malformed Digest before any
artifact leaves the export function, and filesystem-safe filename sanitization
(`_safe_component`) that strips anything outside `[A-Za-z0-9_.-]` from the PAN before using it
in a path — closing the obvious path-injection angle for a client PAN a taxpayer could in
principle influence indirectly. No defect found.

## 5. Type-3 acknowledgement downloader (`app/eri/type3/ack_downloader.py`) — real bug found
and fixed

**The bug**: `download_acknowledgement()` computes `ay_compact = ay_text.replace("-", "")` —
e.g. `"2026-27"` → `"202627"` — with an inline comment explicitly stating the purpose:
*"Normalize AY formats so '2026-27' and '202627' both match (the portal may render either)."*
But `ay_compact` was never actually used anywhere else in the function — only the hyphenated
`ay_text` form was ever searched for on the page. If the live ITD portal happens to render the
assessment year in the compact form for a given "View Filed Returns" row (which the function's
own comment says is a real possibility, not a hypothetical), a **genuinely filed return** would
be misreported as `not_filed=True` — surfacing a misleading "file the ITR first" error to an
operator for a return that was, in fact, already filed.

**Fix**: the row-lookup now retries with `ay_compact` before concluding `not_filed=True`,
implementing exactly what the pre-existing comment already promised.

**Tests added** (`tests/test_filing_audit_and_ack.py`): a minimal Playwright-double harness
(`_FakeAckPage`/`_FakeAckLocator`) proves three cases — the hyphenated form matches directly;
*only* the compact form is present (the bug scenario — must not report `not_filed`); neither
format is present (genuinely not filed, must still report `not_filed=True`). Confirmed via
`git stash` that the compact-form-fallback test fails against the pre-fix code with exactly the
predicted symptom (`not_filed=True` when the return actually is filed) and passes after the fix.

## 6. Type-3 submission worker & uploader (`app/filing_automation/worker.py`,
`app/filing_automation/uploader.py`) — read in full (1631 + 357 lines), one non-issue
investigated and closed

This is defensive, iteratively-hardened Playwright automation: session-loss detection at every
wizard step (`_assert_session`), route-drift detection (`_assert_on_file_itr_route`, so a click
that navigates the wizard off the File-ITR page fails immediately at the step that caused it
rather than several steps later as an unrelated-looking symptom), a portal-error text scanner
that reads the page's own rejection wording rather than relying on ARIA roles the portal doesn't
actually set, and extensive diagnostic control-enumeration (`_log_page_controls`) so a stalled
run doesn't require live reproduction to diagnose. Credentials are never logged: `worker.py`
decrypts the client's portal password only in memory immediately before use, and OTP/EVC values
flow through an in-memory `asyncio.Future` handoff (`wait_for_job_otp`/`provide_job_otp`) that
is explicitly documented and confirmed to never persist or log the value.

**One thing investigated and confirmed safe, not a bug**: `goto_file_itr_page()` hardcodes "No"
to the portal's Section 44AB tax-audit question for every ITR-1 *and* ITR-4 submission. For
ITR-1 this is trivially always correct (44AB tax audit cannot apply to a salary/one-HP/other-
sources-only filer). For ITR-4, Section 44AB audit *can* in principle apply to a presumptive-
income filer in two ways: (a) turnover/receipts exceeding the statutory threshold with cash
receipts over 5%, or (b) declaring presumptive income below the statutory floor. Checked both
against the existing validators and calculator: (a) is hard-blocked pre-JSON-generation by
`ITR4-R237`/`ITR4-R238` ("Tax audit u/s 44AB mandatory. File ITR-3"); (b) is structurally
impossible because the calculator's own `ITR4-C005`/`ITR4-C014`/`ITR4-R144` checks hard-reject
any declared 44AD/44ADA/44AE income below the statutory presumptive minimum. Together these mean
no JSON this platform could ever generate for ITR-4 can represent an audit-required filer — the
hardcoded "No" is therefore always correct by construction, the same "verify reachability before
flagging as a defect" discipline already established in the compute audits' methodology.

The bulk of the file (locator strategies, mat-select/mat-option handling, multi-fallback click
helpers) is UI-automation glue code inherently coupled to the live portal's current markup —
a real, acknowledged fragility class (portal UI changes could break any of these selectors), but
one the code's own comments show real iteration against, citing specific prior failure modes and
their fixes throughout (anti-automation navigation protection, rate-limit recovery, the
Filing-Type-dropdown due-date gating). **Correction**: this was originally attributed to
iteration "against a real UAT portal" — per §11a, no live Type-3 UAT portal exists, so that
attribution was wrong. The iteration evidenced in these comments must instead be against either
the **production** portal (Type-3 production credentials for ITR-1/ITR-4 are already
ITD-enabled per `Docs/ERI_UAT_EXPANSION_PLAN.md`'s status table) or carried over from the
referenced "NRITAX" prior implementation the code explicitly credits several helpers to — which
one wasn't determined in this pass. Either way, not a static-analysis-catchable defect.

## 7. `app/routers/filing.py` — real defense-in-depth gap found and fixed

**The gap**: `_normalize_form()` accepts `{"ITR-1", "ITR-2", "ITR-4"}` and is used uniformly
across every route in this file, including `POST .../submit` — the endpoint that queues a real,
automated Playwright job that logs into the live ITD portal as the taxpayer and submits the
return. The frontend deliberately hides the "Direct Submit" button for ITR-2
(`Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`'s Phase 3 Addendum-3: *"hidden for ITR-2/ITR-3"*) —
correctly, since ITR-2's compute/validation pipeline has not been through the same
production-readiness audit as ITR-1/ITR-4 (`Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`
tracks its build-out separately and it is explicitly not this season's filing-ready form). But
that restriction was enforced **only in the frontend** — a direct API call to
`POST /api/v1/filing/{client_id}/{ay}/ITR-2/submit` would have sailed straight through the
backend's `_normalize_form()` check and queued a real portal submission for an under-audited
form. This is exactly the "the UI hides it, but the API doesn't enforce it" class of gap: a
future frontend change, a stale client build, or an operator using the API directly would have
no server-side backstop.

**Fix**: `submit_via_portal()` now explicitly restricts the *submission* endpoint (not
`/generate` or `/download`, where preparing/downloading a JSON for a still-under-build-out form
is a reasonable, lower-stakes action) to `{"ITR-1", "ITR-4"}`, returning `501 Not Implemented`
with a clear message for anything else — mirroring the frontend's own restriction server-side
rather than relying on it alone.

**Tests added** (`tests/test_filing_router_contract.py`): a direct call to `submit_via_portal`
with `itr_type="ITR-2"` is confirmed to raise `HTTPException(501)` with the expected message
*before* touching `current_user`/`db` (proving the guard fires early, not after some other
failure); a companion test confirms ITR-1/ITR-4 are not caught by the new guard (they fail later,
on the deliberately-invalid fake `client_id`, proving the guard itself passed them through). Both
tests pin `(ERI_MODE, ERI_ENV)` to `type3`/`uat` via `monkeypatch` — a full-suite run surfaced
that `tests/test_eri_routers.py` sets `os.environ["ERI_MODE"] = "type2"` at **module import
time** rather than through a fixture, so it never reverts within a test session; any later test
depending on `ERI_MODE=type3` (as `submit_via_portal`'s own pre-existing Type-2 mode check does)
gets a collection-order-dependent result unless it pins the value itself. Not a product bug —
`test_eri_routers.py`'s pattern was pre-existing and out of scope to change here — but a real
test-isolation gap in the new tests, fixed by pinning the mode explicitly rather than assuming it.

**Everything else in this router** — ownership checks (`resolve_owned_client`,
`job.user_id != current_user.id` on job polling and OTP delivery), audit logging via
`log_filing_action` on every state transition, and the acknowledgement-serving endpoints — was
read in full and found correctly scoped, with no other gap found.

## 8. `_personal_info_base`'s hardcoded PII fallback defaults — investigated, confirmed
unreachable, not fixed

`app/engine/itd/common.py::_personal_info_base` falls back to values like
`"assessee@example.com"`, a fixed `MobileNo=9999999999`, and `PinCode=110001` when its
`email`/`mobile_no`/`pin_code` parameters are `None`/empty — the same "hardcoded placeholder
substituting for real data" shape as this session's most severe compute-side finding
(`filing_date` wired to `date_of_birth`, ITR-1 doc §24). Traced the call path back to the
schema: `FilingAddress.mobile_no` and `.email` (the fields that ultimately supply these
parameters) are **required**, pattern-validated Pydantic fields on `ITR1FilingProfile
.primary_address` — Pydantic construction itself rejects a missing or malformed value before
a real filing profile can ever exist. These fallbacks are therefore unreachable dead code on
the real production path (defense-in-depth for a call shape that cannot occur, or a residue for
a legacy/test call site), not a live defect. Recorded here so a future reader doesn't re-chase
it, matching this repository's established "record scope honestly" practice.

## 9. Credential/PII logging hygiene (`app/automation/auth.py`) — spot-checked, no defect found

`login_itd()`'s progress logging never includes the password value (only generic "Entering
password..." messages and a masked PAN). `_dump_inputs()` — the diagnostic control-enumeration
helper invoked on login failure — explicitly excludes input *values* from what it logs
(`text: isInput ? '' : ...`), capturing only tag/type/id/placeholder metadata for input elements
and visible text for buttons/links. No password- or OTP-leaking log path found.

## 10. Separately reported, not part of this document's remediation: real ERI credentials
committed to git

While reading `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` as a primary source for this audit, real,
currently-active ERI Type-2 UAT credentials (SW_ID, digest secret key, client ID, user ID,
password) were found committed in plaintext, exactly matching the live `.env` values — not
stale/rotated examples. The same values are further duplicated across 17 more tracked files,
including an `API_Testing/` Java/Maven test harness. This is a live violation of `SECURITY.md`'s
explicit "never commit ERI credentials" policy. **This finding was reported to the user
separately and immediately upon discovery** (not batched into this document), since it required
an explicit remediation-approach decision (redact-and-rotate vs. also rewriting git history)
before any file could safely be touched. It is recorded here only as a pointer — the decision
was still pending when this document's other findings were fixed, and no credential-leak
remediation is included in this pass's commits.

## 11. Scope not covered in this pass

Given the size of this surface (`app/automation/` alone is ~13,000 lines, most of it the
*download*-side portal automation for AIS/TIS/26AS/Form-16/prefill — a different subsystem from
filing, per `app/routers/automation.py` vs `app/routers/filing.py`'s explicit separation in
`CLAUDE.md`), this pass deliberately prioritized the *filing/submission*-specific surface over a
full re-audit of the shared download-automation infrastructure:

- `app/automation/navigation.py` (739 lines) and `app/automation/browser.py`'s `BrowserManager`
  singleton (395 lines) were read only far enough to confirm the functions the filing pipeline
  calls (`dismiss_portal_modals`, `navigate_income_tax_returns`, `session_expired`,
  `get_context`) exist and are used correctly — not read end-to-end for their own internal
  correctness. `SECURITY.md` already documents the singleton-Playwright-instance /
  `--workers 1` constraint as a known, accepted deployment risk, not something to re-litigate
  here.
- `app/eri/envelope.py` (228 lines) and all of `app/eri/type2/*` (~750 lines across 6 files) are
  Type-2-only — not the active deployment mode (`ERI_MODE=type3`) and explicitly deferred to
  "next season" per the integration plan. Not read this pass; flagged as the natural next
  increment if/when Type-2 work resumes.
- `app/automation/downloader*.py`, `ais_converter.py`, `as26_converter.py`,
  `pdf_unlocker.py` (the AIS/TIS/26AS import pipeline) — a separate subsystem from filing
  entirely, out of scope for a *filing/submission* pipeline audit specifically.

## 11a. Filing-type coverage (original/belated/revised/notice-response) — mapping verified,
extra-field handling unverified and *unverifiable* before production, by design of Type-3 UAT

**What's confirmed correct**: `app/filing_automation/uploader.py`'s `_RETURN_FILE_SEC_TO_SECTION`
dropdown-selection table was checked against the official ITR-1 JSON schema's own
`FilingStatus.ReturnFileSec` enum description (`"11 : 139(1)-On or before due date, 12 :
139(4)-After due date, 13 : 142(1), 14 : 148, 16 : 153C, 17 : 139(5)-Revised, 18 : 139(9), 20 :
119(2)(b)-After condonation of delay"`) — all 8 codes match exactly, and the filing section is
read from the generated JSON itself (`_filing_section_from_json`) rather than a separately-passed
argument that could drift out of step with the artifact. The compute side also correctly
populates the revised-return/notice-response metadata fields
(`OrigRetFiledDate`/`ReceiptNo`/`NoticeNo`/`NoticeDateUnderSec`) in the JSON when the filing
profile carries them, confirmed directly in `app/engine/itd/itr1.py`/`itr4.py`.

**What's not confirmed, and — this is the important correction — cannot be confirmed by a
pre-production test for Type-3**: grepping the entire uploader for any handling of these same
fields as *portal UI* elements (as opposed to JSON content) returns zero matches. If the ITD
portal's real upload wizard shows a separate on-screen field for the original acknowledgement
number or notice number when "Revised" or "Response to Notice" is selected in the Filing Type
dropdown (a common pattern — dropdown selection plus a confirmation field, independent of what's
embedded in the uploaded JSON), the automation has no code to fill it.

Initially this was framed as "verify with a UAT dry run before trusting it in production" — that
framing was **wrong for Type-3**, corrected directly by the user with real operational knowledge
of the ITD onboarding process: **Type-3 UAT has no live portal to test the automation against at
all.** The UAT step is a paperwork gate — generate a JSON on dummy PAN data with Type-3 UAT
credentials, email it to `erihelp@incometax.gov.in`, ITD performs an offline sanity check
(schema/structure/mandatory fields per the onboarding SOP), and only after that approval does ITD
issue Type-3 *production* credentials — the first credential set that is ever actually usable
against a live portal session. (Type-2's process is structurally different and does have a live
UAT API to exercise: submit dummy PAN data via the Type-2 UAT API, compile the required results
into an Excel sheet, email that sheet to ITD, and only then receive Type-2 production
credentials.) `Docs/ERI_UAT_EXPANSION_PLAN.md`'s Phase 12/13 wording — *"Manually upload one
generated JSON per form to the ITD Type-3 UAT portal as the control step"* — assumed exactly
this nonexistent capability, confirmed by the user (not a self-resolved ambiguity) and now fixed
at every occurrence across that document and `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` (which had
the same wrong assumption baked into its Phase 3 "Required user UAT before commit" checklist,
its A2/A6 validation notes, and its §9.1 Type-3 Testing section) — see
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §2.3 for the consolidated list of what was corrected
where.

**Consequence for what "production ready" can mean here**: since no rehearsal environment
exists, the *first* real Type-3 production filing of each less-common filing-type variant
(revised, notice-response) is inherently also the first live exercise of that specific code path
— there is no way to de-risk this in advance the way the compute/JSON side can be de-risked with
local schema validation. The one deliberate mitigation already built into the code, not added by
this audit: `worker.py`'s Playwright context runs in **visible, interactive mode**, specifically
(per its own comment) *"so the operator can watch the portal upload and intervene if the portal
throws an unexpected prompt."* That is the real safety net for this specific class of risk, given
a sandboxed dry run is structurally unavailable for Type-3. The practical recommendation, not a
code change: treat the first production filing of each filing-type variant (original, belated,
revised, notice-response) as requiring close, attentive operator supervision — not the passive
"click submit and check back later" posture that a well-rehearsed automation would otherwise
justify — until each variant has been observed to complete cleanly at least once.

## 12. Verification

- `ast.parse()` syntax check on every touched file.
- `pytest tests/test_eri_config.py tests/test_filing_audit_and_ack.py
  tests/test_filing_router_contract.py tests/test_eri_routers.py
  tests/test_eri_creation_info_invariant.py tests/test_eri_envelope.py tests/test_itd_direct.py
  tests/test_filing_gateway_v2.py tests/test_filing_gateway_v2_itr4.py -q` — all green, including
  10 new tests (5 in the new `test_eri_config.py`, 3 in `test_filing_audit_and_ack.py`, 2 in
  `test_filing_router_contract.py`).
- `git stash` isolation confirmed the ack-downloader compact-AY-format test genuinely fails
  against the pre-fix code (not a vacuous pass).
- Real `.env` re-verified after the `ERI_MODE`/`ERI_ENV` default-removal: `get_eri_credentials()`
  and `assert_credentials_at_startup()` both still resolve `mode=type3, env=uat` correctly.
- Full backend suite run after all fixes in this document (see the commit for the exact
  pass/fail counts) — same pre-existing-failure baseline as every other pass this session, no
  regressions introduced by this audit's changes.
