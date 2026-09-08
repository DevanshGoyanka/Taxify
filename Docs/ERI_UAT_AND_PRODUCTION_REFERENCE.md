# ERI Type-2 & Type-3 — UAT/Production Reference and Findings (AY 2026-27)

**Date:** 2026-09-03 (§1-11); **Updated:** 2026-09-04 (§12 — ITR-4 Type-2 UAT signing
architecture and `validate`/`submit` implementation; §13 — live prefill flow verification and
four bugs found/fixed in `app/eri/type2/prefill.py`; §14 — Phase B, the WireGuard
whitelisted-egress relay, built and verified)
**Purpose:** one authoritative document for everything ERI-operational — how Type-2 and Type-3
actually get from UAT to production (corrected here from an earlier wrong assumption, with the
real process below), credential architecture, Digest computation, login/session mechanics,
the Type-3 submission automation, acknowledgement retrieval, every finding from the
filing/submission pipeline audit, and (§12-14) the ITR-4 Type-2 UAT signing-architecture
investigation, `validate`/`submit` implementation, live prefill-flow verification, and the
WireGuard whitelisted-egress relay.
Complements, and where the two disagree corrects, `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`
(original architecture plan) and
`Docs/ERI_UAT_EXPANSION_PLAN.md` (multi-form UAT-pack rollout plan) rather than replacing
either — both remain the record of *how the system was built*; this document is the record of
*how it actually operates* and *what has been verified*.

---

## 1. Type-2 vs Type-3 — what they fundamentally are

Per the official `ERI API Specification_v1.1.pdf`:

| Aspect | Type-2 | Type-3 |
|---|---|---|
| Access method | Via API Gateway | Via Web API — but see §2: in practice, no live API access at all until enabled |
| Session created for | The ERI-2 organisation itself | The taxpayer (or an ERI-Type-1) |
| Credentials supplied | ClientID, Client Secret, ERI User ID, ERI Password | Taxpayer PAN/Aadhaar + password/OTP |
| Session validity | 24 hours or until logout | 45 minutes |
| Session identification | AUTH token (cookie) | AUTH token (cookie) |
| Login methods | Password only | Password, Mobile OTP, Bank OTP (taxpayer only), Aadhaar OTP |
| What it does | Official REST API integration — login, prefill, validate, verify, submit, acknowledgement, all as real HTTPS calls signed with the ERI's own DSC | No ITD API access whatsoever. A Type-3 ERI is a pure *software provider*: it generates a CBDT-schema-compliant ITR JSON locally; **the taxpayer uploads it themselves** via the portal's Offline Mode (or, in this codebase, a Playwright automation does the same upload on the taxpayer's behalf, logged in as the taxpayer) |

Every API call under Type-2 additionally carries a **request-level signature**: `data` is the
Base64-encoded request JSON, `signature` is that data signed with the *ERI's own* DSC private
key (PKCS#7) — a distinct concept from the *taxpayer's* DSC, which is only relevant when the
taxpayer's chosen e-verification method is "Digital Signature Certificate" (§7). Confirmed this
distinction is real and not conflated anywhere in the codebase: `app/eri/envelope.py` is the
Type-2 request-envelope signer (ERI's own DSC), entirely separate from anything taxpayer-DSC
related.

## 2. UAT → Production onboarding — corrected, real operational process

**This section replaces an earlier wrong assumption made during this audit** (that a live
Type-3 UAT portal exists to rehearse the submission automation against, the same way a
staging/sandbox environment normally would). It does not. The actual process, as operated in
practice and confirmed directly by the user with real onboarding experience, differs
structurally between the two modes:

### 2.1 Type-3: paperwork-gated, no live sandbox

1. Generate a CBDT-compliant ITR JSON locally, stamped with the **Type-3 UAT** credential
   bundle (`SW_ID`, digest secret, iteration count — see §3), using dummy/test PAN data (ITD
   supplies test data alongside the UAT credentials on request, per the onboarding SOP).
2. **Email the generated JSON directly to `erihelp@incometax.gov.in`.** There is no API call
   and no portal upload at this stage — Type-3 has zero API access by definition
   (`API_Specification` §1.1: *"Type 3 ERIs do not receive any API access"*), and the onboarding
   SOP is explicit that the taxpayer-facing upload happens only in *Offline Mode after
   enablement*, not during certification.
3. ITD's ERI Technical Operations Team performs an **offline sanity check** of the JSON
   (schema, structure, mandatory fields) — 1–2 working days' turnaround per the onboarding SOP.
4. On approval, ITD enables the `SW_ID` for that specific ITR form and assessment year, and
   notifies the ERI by email.
5. **Only at this point does ITD issue Type-3 *production* credentials** — the first credential
   bundle that is ever actually usable against a live portal session.

**Consequence: there is no environment in which the Type-3 Playwright submission automation
(`app/filing_automation/`) can be rehearsed before production.** The UAT credential bundle
exists solely to stamp a JSON for the email-based sanity check — it was never meant to
authenticate a live upload, and attempting to run the automation against a real portal session
with Type-3 UAT credentials will fail with a "software provider not enabled" class of error
(exactly the message `app/filing_automation/uploader.py`'s `_eri_environment_hint()` already
anticipates and explains — see §6). The first live exercise of the submission automation is
inherently the first real production filing.

### 2.2 Type-2: live API sandbox, then a compiled results package

1. Submit dummy/test PAN data through the **Type-2 UAT API** — real, live HTTPS calls against
   ITD's UAT gateway (`uatocpservices.incometax.gov.in/iec-uat/uat/eriapi`), using the Type-2
   UAT credential bundle (ClientID/Secret, ERI User ID/Password, DSC). This *is* a genuine
   rehearsal environment, unlike Type-3's UAT step.
2. Compile the required output from those API calls into ITD's prescribed Excel sheet format
   (the "UAT Test Scenario Sheet" referenced in `CLAUDE.md`).
3. Email the completed sheet to ITD for review.
4. On approval, ITD issues Type-2 **production** credentials.

### 2.3 Why this asymmetry matters for "production ready"

The compute/JSON-generation side of this platform *can* be meaningfully de-risked before
production — local schema validation, the CBDT rule validators, and the extensive compute
audits this session all work without needing any live ITD connection. The Type-3
*submission-automation* side structurally cannot be de-risked the same way: there is no
rehearsal portal. This reframes what "verify before trusting it" can mean for Type-3
specifically — see §9's filing-type-coverage finding and its recommended mitigation (supervised
first use per filing-type variant, leaning on the automation's own visible-browser design — §6).

**Corrected everywhere it appeared** (confirmed by the user with real onboarding experience, not
a self-resolved ambiguity): every reference across the repo's docs to manually uploading a JSON
to a live "Type-3 UAT portal" as a testing/control step described a capability that does not
exist. Fixed at every occurrence: `Docs/ERI_UAT_EXPANSION_PLAN.md`'s Phase 12/13 wording and its
Verification section's "Manual control" bullet, and `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`'s
Phase 3 "Required user UAT before commit" checklist (items 4–8, which is almost certainly why
that phase sat at "AWAITING UAT" without ever resolving — the checklist asked for a step that
was never possible to complete), its A2 Digest validation note, its A6 portal-uploader
validation note, its Phase-3-table "Deliverable" cell, and its §9.1 Type-3 Testing E2E/manual-
control bullets. Each now says either "email to `erihelp@incometax.gov.in`" (the real Type-3 UAT
deliverable) or "production only" (for anything that genuinely needs a live portal session).

## 3. Credential architecture

Four independent credential bundles coexist simultaneously in `.env`, disambiguated by
suffix-qualified variable names keyed by `(mode, environment)`: `ERI_SW_ID_TYPE3_UAT`,
`ERI_SW_ID_TYPE3_PRODUCTION`, `ERI_SW_ID_TYPE2_UAT`, `ERI_SW_ID_TYPE2_PRODUCTION`, and
similarly-suffixed variables for the digest secret/iteration count (all four bundles) and
ClientID/Secret/User ID/Password/base URL/DSC signing mode (Type-2 bundles only — Type-3 needs
none of these, consistent with §1's "no API access" fact). `ERI_MODE` (`"type2"`/`"type3"`) and
`ERI_ENV` (`"uat"`/`"production"`) select which bundle is active for the current process;
`app/eri/config.py::get_eri_credentials()` is the single resolver every other module goes
through.

**Fixed this pass**: `get_eri_credentials()` used to default `ERI_MODE` to `"type3"` and
`ERI_ENV` to `"production"` when either was unset or blank. Since all four bundles coexist in
one file, a blanked `ERI_ENV` (the exact failure mode of a real prior incident — see
`Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md`'s "Recovery incident" — where a careless full-file
`.env` rewrite blanked several secrets) would have silently resolved *production* credentials
instead of failing loudly. Both are now required explicitly; an unset or blank value raises
`ValueError` immediately, matching the "a wrong gateway must fail, not be guessed" principle the
same file already applied to `ERI_BASE_URL` resolution. Verified the real `.env` (which always
sets both explicitly) still resolves correctly after the change; 5 new tests in
`tests/test_eri_config.py`.

## 4. Digest computation — verified correct against the primary source

> **Correction (2026-09-04, §15): this section's title overclaimed.** The cross-check below was
> a *structural/static* read-through against the SOP text — it was never exercised against a
> live `validateItr` call, and it missed a real off-by-one in the iteration count (`iterations`
> HMAC operations were run instead of the correct `iterations + 1`) that made every digest this
> engine ever computed wrong, for every form and both ERI modes, until fixed. "Matches the SOP
> exactly, including step ordering" below is TRUE for the algorithm shape (minify → placeholder
> → keyed HMAC-SHA256 → iterate → Base64) but was wrong about the iteration *count* specifically
> — see §15 for the full discovery, live-call evidence, and fix. Static cross-referencing against
> a spec document is not the same as live verification; this session's own pattern (found
> repeatedly in `prefill.py`, `add_client.py`, and now here) is that ITD's real server can diverge
> from what a spec PDF documents, and only a live call proves which one is right.

Cross-checked `app/eri/digest.py::compute_digest()` line-by-line against
`Digest_generation_ERI 2 (2).pdf` §5.3, the official ERI Type-3 onboarding SOP's digest guide.
The algorithm: minify the JSON (sorted keys, no interstitial whitespace), locate the `Digest`
field and replace it with the placeholder `"-"`, then compute **HMAC-SHA256** — keyed with the
active credential bundle's secret, not a bare hash — iterated a credential-specified number of
times, then Base64-encoded. The implementation matches exactly, including the step ordering.
`app/engine/itd/common.py::_compute_digest` is a thin, single delegate to it — confirmed by grep
that there is no second Digest computation path anywhere in the codebase.

**Documentation staleness fixed** (code was already correct): `CLAUDE.md` described the Digest
as *"SHA-256 over the sorted JSON"*, omitting the HMAC keying and iteration entirely — a bare
SHA-256 with no secret key would never validate against the ITD portal. Corrected.

## 5. Login mechanics

**Type-2**: password-only, per the official API spec — `ClientID`/`ClientSecret` identify the
ERI-2 itself, `ERIUserID`/`ERIPassword` authenticate the specific operator session. This
codebase's Type-2 login lives in `app/eri/type2/login.py` (not deeply re-read this pass — Type-2
is not the active deployment mode; see §8's scope note).

**Type-3**: the taxpayer's own portal credentials (PAN as user ID, plus password/OTP), since a
Type-3 session is created *for the taxpayer*, not the ERI. `app/automation/auth.py::login_itd`
implements the password-based flow via Playwright — PAN entry, "Secure Access Message" (SAM)
checkbox step, password field, multi-strategy submit-and-recover (handles a max-attempts
rate-limit popup by clicking "Login Here" and waiting for session stabilization). **Verified**:
the password value itself is never logged anywhere in this flow — progress messages say generic
things like *"Entering password..."*, and the diagnostic control-dump helper (`_dump_inputs`,
invoked only on a terminal login failure) explicitly excludes input *values* from what it
captures, logging only tag/type/id/placeholder metadata for inputs and visible text for
buttons/links.

## 6. Type-3 submission automation

`app/filing_automation/worker.py` (queue/lifecycle) and `app/filing_automation/uploader.py`
(the actual Playwright wizard-driving logic, 1631 lines) were read in full. This is
defensive, iteratively-hardened automation, not a first draft:

- **Session-loss detection at every wizard step** (`_assert_session`) — a lost session
  previously surfaced several steps later as an unrelated-looking symptom ("file input not
  found"); now it fails at the exact step that lost the session.
- **Route-drift detection** (`_assert_on_file_itr_route`) — any click that navigates the wizard
  off the File-ITR page fails immediately, with the actual URL logged, rather than continuing
  and failing later with no context.
- **Portal-error text scanning** (`_visible_portal_error`) reads the page's own rejection
  wording directly, because the portal renders its rejection as a plain text block with no ARIA
  role or CSS class the automation could otherwise detect.
- **Diagnostic control enumeration** (`_log_page_controls`) — when a step stalls, this logs
  every visible button/link/input the portal actually rendered, so a stalled run doesn't require
  live reproduction to diagnose.
- **Visible, interactive browser** — deliberately not headless. `worker.py`'s own comment:
  *"the operator can watch the portal upload and intervene if the portal throws an unexpected
  prompt."* Given §2's finding that Type-3 has no rehearsal environment, this is the actual,
  load-bearing safety net for anything the automation doesn't yet handle — not a nice-to-have.
- **OTP/EVC handling** flows through an in-memory `asyncio.Future` handoff
  (`wait_for_job_otp`/`provide_job_otp`) — confirmed never persisted or logged.
- **A pre-built explanation for the single most likely early failure**:
  `_eri_environment_hint()` recognizes a "software provider not enabled" portal rejection and
  explains it in terms of the active `(ERI_MODE, ERI_ENV)` bundle and the SW_ID enablement
  process from §2.1, rather than surfacing a bare portal error string.

**Real bug found and fixed** (not in this file, but discovered while reading the sibling
acknowledgement downloader — see §7).

**Filing-type/section coverage**: `_RETURN_FILE_SEC_TO_SECTION` maps all 8 `ReturnFileSec` codes
the official schema defines (139(1)/139(4)/139(5)/139(9)/142(1)/148/153C/119(2)(b)) to the
portal's Filing Type dropdown labels, verified against the schema's own enum description — the
*dropdown selection* is complete. What is **not** verified, and per §2.1 cannot be verified
before production: whether the portal's real wizard requires *additional* on-screen fields
(original acknowledgement number, notice number) for revised/notice-response filings beyond
dropdown selection — a full grep of the uploader found no handling for
`OrigRetFiledDate`/`ReceiptNo`/`NoticeNo`/`NoticeDateUnderSec` as portal UI elements, only as
JSON content (which the compute side does populate correctly). See §9 for the practical
implication.

**Investigated and confirmed not a bug**: `goto_file_itr_page()` hardcodes "No" to the portal's
Section 44AB tax-audit question for every submission. For ITR-1 this is trivially always
correct. For ITR-4, checked both ways 44AB could apply — turnover/cash-ratio thresholds
(`ITR4-R237`/`R238`, hard-blocked pre-generation) and declaring presumptive income below the
statutory floor (`ITR4-C005`/`C014`/`R144`, hard-blocked by the calculator itself) — and
confirmed no JSON this platform can generate for ITR-4 can represent an audit-required filer.
The hardcoded answer is correct by construction, not a gap.

## 7. Acknowledgement retrieval

Two independent paths exist, deliberately: `PortalUploader.download_acknowledgement()` (inside
`uploader.py`, runs immediately after a successful e-verified submission in the same browser
session) and the **standalone** `app/eri/type3/ack_downloader.py::download_acknowledgement()`
(a separate Playwright flow that logs in fresh, navigates to "View Filed Returns," and finds a
row by assessment year — built specifically so acknowledgement retrieval works even for a return
that was uploaded manually outside this platform, with no dependency on the uploader's own
session or a pre-known ARN).

**Real bug found and fixed** in the standalone path: the function computed
`ay_compact = ay_text.replace("-", "")` (e.g. `"202627"` from `"2026-27"`) with an inline comment
explicitly stating the purpose — *"Normalize AY formats so '2026-27' and '202627' both match
(the portal may render either)"* — but `ay_compact` was never actually used anywhere else in the
function. If the live portal happened to render the compact form for a given filed-return row
(which the pre-existing comment itself says is a real possibility), a **genuinely filed return**
would be misreported as `not_filed=True`, surfacing a misleading "file the ITR first" message
for a return that was already filed. Fixed: the row lookup now retries with the compact form
before concluding not-filed, implementing exactly what the pre-existing comment already
promised. 3 new tests (`tests/test_filing_audit_and_ack.py`) using a minimal Playwright-double
harness; confirmed via `git stash` that the fallback test genuinely fails against the pre-fix
code (not a vacuous pass) and passes after the fix.

## 8. `app/routers/filing.py` — the unified API surface

Read in full. Ownership checks (`resolve_owned_client`, `job.user_id != current_user.id` on job
polling and OTP delivery) and audit logging (`log_filing_action` on every state transition) are
correctly and consistently applied across every route.

**Real defense-in-depth gap found and fixed**: `_normalize_form()` accepts
`{"ITR-1", "ITR-2", "ITR-4"}` and is used uniformly across every route, including
`POST .../submit` — the endpoint that queues a real, automated Playwright portal submission. The
frontend deliberately hides "Direct Submit" for ITR-2 (its compute/validation pipeline hasn't
been through the same production-readiness audit as ITR-1/ITR-4 — tracked separately in
`Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`), but that restriction was enforced **only in the
frontend** — a direct API call to `.../ITR-2/submit` would have sailed through the backend check
and queued a real portal submission for an under-audited form. Fixed: `submit_via_portal()` now
explicitly restricts *submission* (not `/generate`/`/download`, where preparing a JSON for a
still-under-build-out form is a reasonable, lower-stakes action) to `{"ITR-1", "ITR-4"}`,
returning `501` for anything else. 2 new tests in `tests/test_filing_router_contract.py`
(confirmed the guard fires for ITR-2 before touching `current_user`/`db`, and that ITR-1/ITR-4
are not caught by it).

## 9. Consolidated: what "production ready" can and cannot mean here

**Can be, and has been, verified before production** (all confirmed this pass): Digest algorithm
correctness against the primary SOP; credential resolution correctness and safety (no silent
mode/environment guessing, for either mode's DSC signing — §10.3); no divergent second
JSON-generation path; filing-type dropdown mapping completeness against the schema;
acknowledgement-retrieval AY-matching correctness; Type-3 taxpayer login's password/OTP logging
hygiene (§5); the ITR-2 submission guard. **Type-2's own PII/OTP logging hygiene was not yet
verified when this line was first written — it wasn't, and was fixed (§10.1, §10.2)**; corrected
here rather than silently, since the original claim implicitly covered ground (Type-2) that
hadn't actually been audited yet at the time.

**Cannot be verified before production, by the structural nature of Type-3 onboarding** (§2.1):
whether the portal's live upload wizard needs additional fields for revised-return or
notice-response filings beyond what this codebase currently fills in. **This is not "untested"
in the sense of "someone should go test it" — there is no environment in which it could be
tested before a real production filing.** The practical mitigation is procedural, not a code
change: the automation's visible/interactive browser mode (§6) exists specifically so an
operator can watch and intervene on an unexpected prompt. The first production filing of each
less-common filing-type variant (revised, notice-response, condonation-of-delay) should be
treated as requiring close operator supervision — not the passive posture a well-rehearsed
automation would otherwise justify — until each variant has been observed to complete cleanly at
least once.

**Not part of this pass, tracked separately and still pending**: the real ERI Type-2 UAT
credential leak (SW_ID, digest secret, client ID, user ID, password committed in plaintext
across 18 tracked files, including `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` and an entire
`API_Testing/` subtree) — reported to the user immediately upon discovery, remediation approach
still awaiting their decision. Unrelated to the findings in this document but relevant to overall
ERI operational risk, so noted here for completeness.

## 10. Type-2 (`app/eri/envelope.py` + `app/eri/type2/*`) — read in full; three real issues
found and fixed, all in the shared envelope module

Read `app/eri/envelope.py` (request signing/headers, shared by every Type-2 module) and all six
`app/eri/type2/*.py` files (`login.py`, `add_client.py`, `everify.py`, `acknowledgement.py`,
`prefill.py`, `client.py`) in full. Type-2 is not the active deployment mode this season, so
none of these three issues are live-impacting today — but all three would have broken or
endangered the very first real Type-2 usage, and all three are fixed now rather than left for
whoever picks Type-2 up next to rediscover.

### 10.1 Real PII/secret leak found and fixed: every Type-2 API call logged the full plaintext
payload to console

`envelope.py::build_request_envelope()` — called by every single Type-2 module before every API
call — contained four `print()` debug statements, including `print(f"DEBUG [ENVELOPE] Plain
payload: {serialized}")`, which logs the **complete, unencrypted request payload** to
stdout/console on every call. This payload routinely carries real taxpayer PII (PAN, name,
address — `add_client.py`'s `addRegisterClient`) and, more severely, **live authentication
secrets**: `everify.py::verify_evc()` puts the taxpayer's actual Aadhaar OTP or bank EVC value
directly into the payload as `otpValue`/`evcValue` before it reaches this function, and
`prefill.py` does the same with `mobileOtp`/`emailOtp`. Every one of these would have been
printed in full. This directly contradicts the discipline `login.py`'s own comment already
states for this exact call: *"Send the request without logging URLs, envelopes, headers,
tokens, or response bodies."* — an intent that `envelope.py` itself did not honor. Given server
logs are routinely captured, retained, and sometimes shipped to external logging
infrastructure, this was a live PII/credential-leak risk the moment any Type-2 code path ran.
**Fixed**: all four `print()` calls removed.

### 10.2 Real bug found and fixed: `eri_headers()` used the exact "unsuffixed variable this
project never sets" defect already fixed everywhere else in this package

`envelope.py::eri_headers()` read `os.getenv("ERI_CLIENT_ID")`/`os.getenv("ERI_CLIENT_SECRET")`
directly — the unsuffixed names. But this project's entire credential architecture (§3) only
ever sets the suffix-qualified `ERI_CLIENT_ID_TYPE2_UAT`/`_PRODUCTION` (and the `_SECRET`
equivalents) in `.env`; the unsuffixed names are never set. Every one of the six Type-2 modules
already carries a comment explaining this *exact* defect class was found and fixed for
`ERI_BASE_URL`/`ERI_USER_ID` (*"It used to be a module constant captured at import time from an
unsuffixed ERI_BASE_URL that this project never sets, so every request silently went to the
hardcoded UAT default"*) — but that fix was never carried over to `eri_headers()`, the one
function every Type-2 API call also depends on. The existing test suite even encoded this bug as
expected behavior (`test_eri_headers`/`test_eri_headers_missing` set/cleared the unsuffixed
vars directly). **Practical effect**: every Type-2 API call that reached `eri_headers()` would
have unconditionally raised `ValueError("ERI_CLIENT_ID and ERI_CLIENT_SECRET must be
configured...")`, before ever making an HTTP request — the Type-2 API pipeline was entirely
non-functional. **Fixed**: `eri_headers()` now resolves `client_id`/`client_secret` via
`get_eri_credentials()`, matching every sibling function. Both existing tests updated to use the
suffix-qualified variables (confirmed via `git stash` that both fail against the pre-fix code
with exactly the predicted symptom).

### 10.3 Real safety gap found and fixed: the `ngrok` DSC-signing mode had a hardcoded fallback
URL and was not forbidden in production

`sign_data()`'s `"ngrok"` mode transmits the full plain payload — the same PII/OTP-bearing data
as §10.1 — to an external URL for remote DSC signing. It defaulted `SIGNER_URL` to a hardcoded
value, `https://unpondered-implacably-tamatha.ngrok-free.dev/api/sign` — apparently one
developer's personal ngrok tunnel, used with no explicit configuration required. This is the
exact "a wrong destination must fail, not be guessed" hazard `app/eri/config.py::get_eri_base_url()`
already explicitly guards against for the ITD gateway URL, just not carried over to this signer
URL. Worse, `app/eri/config.py::assert_credentials_at_startup()` already forbids `"mock"`
DSC-signing mode in Type-2 production (an invalid-signature failure mode that fails safely — ITD
simply rejects it) but did **not** forbid `"ngrok"` mode, which is more dangerous: a
misconfiguration that left `ERI_DSC_SIGNING_MODE=ngrok` active in a production deployment would
silently exfiltrate real taxpayer PII/OTP payloads to an external, unaudited endpoint on every
signing call. **Fixed**: the hardcoded fallback URL is removed (`SIGNER_URL` must now be
explicitly set, raising `ValueError` otherwise); `assert_credentials_at_startup()` now forbids
`ngrok` mode in Type-2 production alongside `mock`.

### 10.4 Noted, not fixed: hardcoded personal name as the default DSC certificate subject filter

`sign_data()`'s `"token"` mode (Windows Certificate Store signing) defaults
`ERI_DSC_CERT_SUBJECT` to a specific individual's name (matching the DSC holder referenced in
the UAT Test Scenario Sheet filename in `Reference Docs by CBDT & ITD/`). Lower severity than
§10.1–10.3: an unset/wrong value **fails loudly** (`RuntimeError` if no matching certificate is
found in the store), rather than silently misbehaving, so it was left as a recorded finding
rather than changed — a default that only works for one specific operator's machine is still
worth knowing about before anyone else tries to run Type-2 token signing.

### 10.5 Verified correct, not a bug

`type2/client.py::get_eri_mode()` reads `ERI_MODE` but under an entirely different,
undocumented vocabulary (`"real"`/`"mock"` per its own docstring, though it just lowercases
whatever `ERI_MODE` actually holds — never `"real"` or `"mock"` in this project's actual usage).
Confirmed via grep it is never called anywhere in the codebase — genuinely dead code, left
alone. `parse_response_envelope()`'s error-detection (checking both a `messages[]` array and a
separate `errors[]` array, per a comment noting the latter "seen in some Type-2 API responses")
and `eri_post()` in `client.py` (the generic Type-2 HTTP dispatcher) were both read and found
structurally sound — no defect found in either.

## 12. ITR-4 Type-2 UAT enablement — signing architecture investigation and
implementation (2026-09-04)

**Goal:** Taxify already holds Type-2 **production** credentials for ITR-1 (earned by passing
Type-2 UAT for ITR-1 previously). To get ITR-4 production-enabled the same way, the full
Type-2 API flow (login → client onboarding → prefill → **validate** → **submit** → e-verify →
acknowledgement) must be exercised against Type-2 UAT credentials for a dummy-PAN ITR-4 return,
the results captured into ITD's Test Scenario Sheet, and ITD emailed requesting ITR-4
enablement. `validate`/`submit` did not exist in this codebase before this session (§10 already
covered `login`/`add_client`/`everify`/`acknowledgement`/`prefill`) — this section covers
building them, and a real signing-architecture problem that had to be solved first.

### 12.1 The starting problem: how to sign UAT calls without a 24/7 machine

Type-2 calls must (a) egress from an IP ITD has whitelisted, and (b) carry every payload signed
with the ERI's own DSC private key. The user's DSC is a **physical USB hardware token**
(HyperPKI HYP2003, cert holder Sunit Ramashankar Goyanka, issuer Verasys Sub CA 2022) that only
their local Windows machine can access — it cannot run on a always-on cloud box unless the key
itself is exported to a portable form.

**Read-only investigation (per explicit instruction: inspect only, never export or mutate the
key) ruled that out.** `certutil -store -user My <thumbprint>` reported `Private key is NOT
exportable`; the vendor's own HyperPKI Token Manager GUI's Export function offers only `.cer`
(public certificate) with no PFX/P12 option. Confirmed via two independent authoritative
sources: the private key genuinely cannot leave this specific token, by any means.

**Decision:** the real long-term fix is a new file-based or cloud-HSM DSC, re-registered with
ITD's public-key whitelisting process — a separate, longer effort, explicitly deferred. The
immediate, narrower goal became: pass ITR-4 UAT now, signing on the user's own local machine
during attended sessions (no 24/7 infrastructure, no unattended-operation hardening) — the
existing ngrok-based bridge (§10.3) had already proven this pattern works for ITR-1 UAT; this
work replaces its unsafe bits and fills the `validate`/`submit` gap.

### 12.2 Step 0 discovery: Python CryptoAPI signing works, once two structural
bugs are fixed

`envelope.py::sign_data()`'s `"token"` mode (`win32crypt`) was already-written but never
actually exercised — `pywin32` was commented out of `requirements.txt`. Installing it and
smoke-testing directly against the plugged-in token **worked immediately**, and ASN.1 inspection
confirmed it produced a genuine `pkcs7-signedData` (CMS `SignedData`) structure — not dead code.
But comparing it byte-for-byte against a real, already-ITD-whitelisted captured signature (from
a prior successful ITR-1 UAT login, `data` length 172, `sign` length 8984) surfaced two real
defects in the existing implementation:

1. **Attached vs. detached — the code's own comment was backwards.** The original code called
   `CryptSignMessage(sign_para, (data_bytes,), False)` with the comment *"Set to False to
   generate an ATTACHED signature (which the Java app uses)"*. ASN.1 inspection of both the real
   captured sample and a fresh call to the actual working Java `local-dsc-signer` reference
   (`API_Testing/local-dsc-signer/` — read for reference only, per explicit instruction not to
   modify or depend on it; its `CmsTokenSigningService.java` calls BouncyCastle's
   `cmsGenerator.generate(cmsData, false)`, where `false` means **don't encapsulate** = detached)
   showed the real, working signature is **detached** — the JSON payload is *not* embedded in
   the CMS blob (it's sent separately via the envelope's own `data` field). The comment had the
   boolean backwards. **Fixed**: `fDetachedSignature=True`.

2. **Leaf cert only vs. full chain.** The real captured sample embeds **4 certificates** (leaf →
   issuing sub-CA "Verasys Sub CA 2022" → intermediate CA → root "CCA India 2022"), confirmed by
   counting distinct `Certificate` SEQUENCEs in the ASN.1 dump. The original code passed only the
   signing cert with no `MsgCert` chain at all. The intermediate/root certs aren't in the token's
   own `CurrentUser\My` store — only Windows's system-wide `CA`/`Root`/`AuthRoot` stores carry
   them, since Windows downloads/caches those separately as part of normal chain-building.
   **Fixed**: a new `_build_cert_chain()` helper walks Issuer-DN → Subject-DN matches up through
   those stores (both `CurrentUser` and `LocalMachine` locations) until reaching a self-signed
   root, and the full chain is passed via `MsgCert`.

With both fixes, the base64 signature length came to 8788 chars — close to the real 8984, but
not exact. The remaining ~150-byte gap was a **CMS authenticated-attributes block**
(`contentType`, `signingTime`, `messageDigest`, and an `id-aa-CMSAlgorithmProtection` attribute)
that BouncyCastle's `JcaSignerInfoGeneratorBuilder` adds by default and Windows
`CryptSignMessage` does not, unless explicitly told to via its `AuthAttr` parameter.

**Attempting to add these via `CryptSignMessage(..., AuthAttr=[...])` segfaulted** — a hard
native crash, not a Python exception, while touching the live hardware token. `pywin32` exposes
no lower-level `CryptSignHash` primitive to work around it (confirmed by reading pywin32's own
C++ source, `PyCRYPTKEY.cpp`); the only clean workaround would be a from-scratch `ctypes`
binding to classic CryptoAPI (`CryptAcquireCertificatePrivateKey` → `CryptCreateHash` →
`CryptSetHashParam` → `CryptSignHash`) plus hand-built CMS assembly. Before building that,
the no-attributes, detached, full-chain signature was tested directly against a **real ITD
Type-2 UAT login call** — and it worked:

```
HTTP 200
{"messages":[{"code":"EF00000","type":"INFO","desc":"OK","fieldName":null}],
 "entity":"ERIP013181","transactionId":"FOS000005955097","autkn":"83a8099897de4d06b0090633bbddd80b"}
```

This confirms ITD's verifier does **not** require the authenticated-attributes block — the
ctypes/ from-scratch-CMS path was dropped as unnecessary. `envelope.py::sign_data()`'s `"token"`
mode now: detached signature, full chain, no signed attributes — verified working, not merely
theorized.

### 12.3 IP whitelisting reality check — why `assert_credentials_at_startup()`
and `AWS_FREE_TIER_DEPLOYMENT.md` were wrong

The login call above succeeded directly from the user's **local machine's own IP** — no AWS
relay involved. This does *not* mean IP whitelisting stopped mattering (see §10's own docstring
fix and the correction below) — the user confirmed their **current local IP happens to already
be whitelisted for UAT specifically, but not for production**; the AWS jump-box IP (used for
the original ITR-1 UAT/production work) is whitelisted for **both**. Two real doc/code
inaccuracies were found and fixed as a result, both of which predate this session and both of
which actively claimed IP whitelisting was no longer necessary:

> **Account distinction, confirmed directly by the user (2026-09-04) — do not conflate these.**
> "The AWS jump-box" throughout this section (and §12.4/§12.8's Phase B) refers to a **specific
> AWS account whose IP is whitelisted with ITD**, used for the original ITR-1 Type-2 UAT/
> production work. `Docs/AWS_FREE_TIER_DEPLOYMENT.md` describes provisioning an **entirely
> different, unrelated AWS account** purely to host Taxify's own backend/frontend for testing —
> that account has no IP whitelisted with ITD and no relationship to ERI API calls at all. The
> two are separate AWS accounts, separate credentials, separate purposes; Phase B's jump-box
> work below is scoped exclusively to the whitelisted account, never to the free-tier hosting
> one.

- `app/eri/config.py::assert_credentials_at_startup()`'s docstring claimed *"That whitelisting
  requirement no longer applies — ERI endpoints accept the deployment IP directly"*. Wrong —
  confirmed by both the user directly and the official ITD `List of UAT/Production URLs for
  Type 2` PDFs (precondition #1 on both). What actually happened: an earlier session removed a
  dead SSH-jump-host startup guard (`ERI_AWS_SSH_HOST_TYPE2_PRODUCTION` — never wired to any
  real relay, no `paramiko` import exists anywhere in this codebase) and the docstring
  conflated "the code guard is gone" with "the requirement it checked is gone." Fixed: the
  docstring now states plainly that whitelisting is still required, the guard's removal was
  about dead scaffolding, not the requirement.
- `Docs/AWS_FREE_TIER_DEPLOYMENT.md` §2 had a **"RESOLVED — ITD IP whitelisting"** callout
  making the same wrong claim, plus downstream advice (§2.1) recommending removing the (already
  since-removed) startup guard as "safe," and two more references (§8, §11) repeating the
  claim. All four corrected in place with dated `> **Correction**` blocks per this repo's
  established convention — not silently rewritten, so anyone who already acted on the original
  claim can see exactly what changed and why.

**Resulting two-phase plan, agreed with the user:**

- **Phase A (now, in progress):** build and test `validate.py`/`submit.py` and the rest of the
  flow directly from the local machine — the current local IP is whitelisted for UAT, and the
  backend running locally means signing is simply in-process (no network hop to a separate
  signer needed at all, eliminating an entire planned `remote_signer` `sign_data()` mode and the
  Java `local-dsc-signer` service from scope — see §12.5).
- **Phase B (before the real, ITD-reviewed ITR-4 UAT run):** route outbound traffic to ITD
  through the AWS jump-box (WireGuard tunnel + NAT/MASQUERADE for the specific ITD destination
  IP), since that IP is whitelisted for production too and the final UAT run that gets reported
  to ITD should go through production-representative infrastructure. **Not yet built** — the
  jump-box/WireGuard/NAT setup is the one piece of this plan still outstanding, requiring the
  user's own AWS access.

### 12.4 Architecture simplifications versus the original plan

Two components originally planned were dropped once the above was confirmed, both by explicit
user decision after empirical verification, not by default:

- **The Java `local-dsc-signer` service** (`API_Testing/local-dsc-signer/`, a working
  Spring Boot + BouncyCastle reference the user had used to pass ITR-1 UAT previously). Explicit
  instruction: *"do not touch it at all, just refer its implementation and implement it
  independently in python in taxify"* — it was read in full for reference (confirming the
  detached-signature/full-chain/signed-attributes structure documented in §12.2) but never
  modified, and is not depended on by the running system. `app/eri/envelope.py`'s Python
  `"token"` mode is now the sole, independent implementation.
- **The `remote_signer` `sign_data()` mode** (planned: POST to a `SIGNER_URL` on a WireGuard
  private address, mirroring the `"ngrok"` mode's `{success, data, sign}` contract). Made moot
  once the backend itself runs on the same local machine as the DSC token — signing happens
  in-process via the `"token"` mode, no network hop or separate signer process required. Only
  Phase B's outbound *network route* to ITD needs a relay; signing itself does not.

### 12.5 New code: `validate.py` / `submit.py` and the routes

Built from `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/
API_SubmitFlow_v1.1.pdf` (read in full). Both endpoints share an identical request/response
shape (`app/eri/type2/validate.py::build_itr_payload()` builds it once; `submit.py` imports and
reuses it), differing only in `serviceName` (`"EriValidateItr"`/`"EriItrSubmit"`) and URL suffix
(`/validate`/`/submit`, appended to `get_eri_base_url()` the same way every other Type-2 module
does — the spec PDF's own "API URL" field shows a stale, non-matching path fragment,
correctly ignored). Both include the mandatory `timeStamp` field (§2/§10), matching the pattern
every other Type-2 module already uses.

Two new routes, following the existing `_require_type2_mode()` guard pattern exactly:
`POST /api/v1/eri/validate-itr` and `POST /api/v1/eri/submit-itr`
(`app/routers/integration.py`), with request schemas `ERIValidateItrRequest`/
`ERISubmitItrRequest` (`app/schemas/eri.py`).

`app/eri/envelope.py::parse_response_envelope()` was extended to recognize the `errCd`/
`errFld`/`errCtg`/`asPerItr`/`asComputed`/`variance`/`schId` error shape these two endpoints use
in their `errors[]` array — distinct from the `{code, desc, fieldName}` shape
login/addClient/everify use. Without this, every validate/submit-side validation error would
have collapsed into a generic `ERIApiError(code="UNKNOWN", desc="Unknown Error")`, discarding
exactly the per-field arithmetic-mismatch detail (`asPerItr` vs. `asComputed` vs. `variance`)
these endpoints exist to surface. `ERIApiError` (`app/eri/exceptions.py`) gained matching
optional fields (`category`, `as_per_itr`, `as_computed`, `variance`, `sch_id`) to carry this
through to callers.

Also confirmed from the spec: even the documented **"Validated Successfully"** sample response
carries `successFlag: false` (with empty `messages`/`errors` and a real `transactionNo`) — a
spec documentation anomaly, not something to treat as failure. `parse_response_envelope()`
deliberately does not key off `successFlag` for this reason; only non-empty `errors[]`/
`ERROR`-typed `messages[]` entries raise.

### 12.6 A real pre-existing bug found via testing, unrelated to this session's
own changes

Writing a test that actually exercises the `except ERIApiError as exc:` branch of the new
`/validate-itr` route immediately failed with `NameError: name 'ERIApiError' is not defined`.
`app/routers/integration.py` uses `ERIApiError` in **eight** `except` clauses (every Type-2
route: login, logout, add-client, validate-client-otp, register-client, validate-reg-otp, and
now validate-itr/submit-itr) but never imported it at module scope. Every existing Type-2 route
would have crashed with an unhandled `NameError` → 500 instead of a clean 400 the moment any of
them actually raised an `ERIApiError` in production — none of the pre-existing router tests
happened to exercise that branch, so it went uncaught until this session's new test did.
**Fixed:** `from app.eri.exceptions import ERIApiError` added to `app/routers/integration.py`'s
imports.

### 12.7 Test coverage

- `tests/test_eri_envelope.py` — `parse_response_envelope()`'s new errCd/errFld branch, the
  legacy shape's continued correctness (regression fence), and the `successFlag: false`
  "validated successfully" anomaly.
- `tests/test_eri_type2_validate_submit.py` (new) — `build_itr_payload()`'s field mapping
  (including the mandatory `timeStamp` and `createdBy` default/override), and
  `validate_itr()`/`submit_itr()` hitting the correct URL suffix and `serviceName`, with a
  mocked `requests.post` (no live network call in unit tests).
- `tests/test_eri_routers.py` — the two new routes' happy path, missing-auth-token 401, and the
  `ERIApiError` field-detail surfacing (the test that caught §12.6's bug).
- All fix-dependent tests confirmed via `git stash` to genuinely fail against the pre-fix code
  before trusting them (this repo's established verification convention) — e.g.
  `test_parse_response_envelope_validate_submit_error_shape` fails with
  `code == 'UNKNOWN'` (not `'AssesseeName_001'`) when `envelope.py`'s fix is stashed out.
- Signing itself (`"token"` mode, the chain-walk, live hardware) is **not** unit-tested — it
  depends on physical token access and was verified manually this session (§12.2/§12.5) rather
  than in the automated suite, consistent with how DSC signing has never been part of the
  regular test run.

### 12.8 What's left before ITR-4 can go to production

1. ~~Phase B: WireGuard + AWS jump-box NAT-routing~~ — **done, see §14.**
2. A full ITR-4 dummy-PAN UAT run end-to-end (login → client onboarding → prefill if applicable
   → validate → submit → e-verify → acknowledgement) through Phase B's production-representative
   path, captured into ITD's Test Scenario Sheet format (mirroring the ITR-1 precedent exactly).
   **Update (2026-09-04, §13): login, add-client-already-added confirmation, and the full
   prefill flow are now verified working end-to-end against live Type-2 UAT.** **Further update
   (same day, §14.4): re-verified through Phase B's tunnel specifically** (not just Phase A's
   direct local IP) — validate/submit/e-verify/acknowledgement remain to be exercised live, and
   should now go through the tunnel from the start rather than needing a second pass.
3. Email ITD requesting ITR-4 production enablement once the sheet is clean.

## 13. Prefill flow — live UAT verification and four real bugs found and
fixed (2026-09-04)

Continuing directly from §12: with `validate.py`/`submit.py` built and the signing/whitelisting
questions resolved, the next step toward "a full ITR-4 dummy-PAN UAT run" was exercising the
rest of the flow live. Per the user's guidance, the correct sequence is: **login → confirm the
dummy-PAN client is already added → request prefill → use the real prefill data (not fabricated
values) to build the ITR JSON.** This section covers that work, run against the same dummy PAN
used for the original ITR-1 UAT precedent, `GOYPT2026A`.

### 13.1 Login re-verified; client confirmed already added

A fresh live login (using the same token-mode signing verified in §12) succeeded again,
confirming §12.2's fix is stable across sessions. `request_prefill_otp("GOYPT2026A", ...)` was
then called directly (no `addClient` call first) and succeeded immediately — ITD's gateway would
reject a prefill OTP request for a PAN not already an authorized client, so success itself
*is* the "already added" confirmation the user asked for. `GOYPT2026A` was added as a client
during the original ITR-1 UAT work and remains valid.

### 13.2 Four real bugs found in `app/eri/type2/prefill.py`, all confirmed
against live calls (not guessed from the spec alone)

`API_Prefill_v1.1.pdf`'s own request-body tables turned out to be an unreliable source of truth
in two places — matching this repo's established finding (CLAUDE.md, §"CBDT/ITD source
material") that a spec document's stated shape doesn't always match what the live gateway
actually accepts. Each fix below was verified against a real HTTP response, not inferred from
the PDF alone; where the fix needed the ACTUAL request shape rather than the documented one, the
user's own prior `uat-login-test/get_prefill_goypt2026a.sh` script (which has a saved
`get_prefill_response_goypt2026a.json` showing `"successFlag":true` with real encrypted prefill
data) was the authoritative reference, not the spec PDF.

1. **`requestPrefillOTP`'s `serviceName`.** The spec's Section 4.4.3 table claims the mandatory
   value is `"EriGetPrefill"`. The *live* gateway rejects that with
   `errCd=EF40000, fieldName=serviceName, desc="JSON data invalid"` — confirmed by first
   "fixing" the code to match the spec (making it worse) and getting this exact field-level
   error back, then reverting to the code's original `"EriPrefill"`, which had been correct all
   along. **No fix needed here in the end** — but worth recording, since the spec's own table
   would lead a future reader to "fix" this into a real regression.
2. **`getPrefill`'s transaction ID field.** The spec's Section 5.3.3 table documents a single
   `"transactionId"` field. The live gateway rejects this shape with a generic
   `errCd=EF40000, desc="JSON data invalid"` (no `fieldName`) regardless of which of
   `requestPrefillOTP`'s two returned IDs (`smsTransactionId`/`emailTransactionId`) is used for
   it. The real, working shape (confirmed via the referenced `.sh` script's saved successful
   response, then independently reproduced live) sends **both** as separate fields:
   `"smsTransactionId"` and `"emailTransactionId"`, matching the exact keys
   `requestPrefillOTP`'s own response uses. **Fixed**: `get_prefill_data()`'s signature changed
   from a single `transaction_id: str` to `sms_transaction_id: str` +
   `email_transaction_id: Optional[str]`.
3. **Response key casing: `"Prefill"` vs `"prefill"`.** The code read
   `validated_envelope.get("Prefill")` (capital P); the real response key is lowercase
   `"prefill"`. This one is severe: it would silently treat even a **fully successful** response
   as an error (`"Prefill attribute is missing from the success response"`), discarding real
   decrypted taxpayer data. **Fixed**: reads `"prefill"`.
4. **Schema-file path off by one directory level.** `validate_prefill_schema()`'s
   `schema_path` used two `".."` segments from `app/eri/type2/prefill.py`, resolving to
   `app/Docs/PreFillSchemaJSON_V6.5/...` — which never existed (the real file is at repo-root
   `Docs/PreFillSchemaJSON_V6.5/...`, three levels up: `type2 → eri → app → root`). This raised
   `FileNotFoundError` on every single call, including the very first genuinely successful
   `getPrefill` response this session obtained. **Fixed**: added the missing `".."` level.

### 13.3 A fifth issue: the published prefill schema is stricter than ITD's
own live server

After fixing #1–4, a live call for `GOYPT2026A`/AY 2025 returned **real, fully decrypted**
prefill data — 55 top-level sections (`personalInfo`, `verification`, `bankAccountDtls`,
`filingStatus`, `ais`, `scheduleCFL`, and so on). Of those 55, only `personalInfo` and
`verification` were populated; the other 53 (covering audit reports, ESOP schedules, foreign
remittance forms, carried-forward losses, etc. — all genuinely inapplicable to this simple dummy
taxpayer) were `null`. `validate_prefill_schema()` then raised
`jsonschema.exceptions.ValidationError` at `scheduleCFL`: `"None is not of type 'object'"` — the
published `PreFillSchemaJSON_V6.5.json` declares that field (and, by the same pattern, likely
most of the other 52) as a required `"type": "object"` with no `null` allowed, but ITD's own
live server legitimately sends `null` for any section that doesn't apply to the taxpayer. This
is not malformed data; it's the schema being out of sync with the server's real, ordinary
behavior — and since **most real taxpayers will have many inapplicable null sections** (this
was not a dummy-data quirk unique to `GOYPT2026A`), treating this as fatal would make
`get_prefill_data()` unusable for its actual purpose against any normal return. **Fixed**: a
schema validation failure is now logged as a warning (`_log.warning(...)`, naming the exact
field path and message) rather than raised — the successfully decrypted-and-parsed data is
still returned. A genuinely corrupted/undecryptable response still fails earlier and loudly (bug
#3's fix, and the existing `DECRYPT_ERROR`/`JSONDecodeError` handling, are unaffected).

### 13.4 Verification

All five fixes were confirmed against live HTTP calls before being written into the source
(not merely inferred), and `tests/test_eri_type2_prefill.py` (new) covers all of them with
mocked `requests.post`/`build_request_envelope`, each `git stash`-verified to fail against the
pre-fix code (four of five did; the `serviceName` test correctly does **not** regress, since #1
above concluded no code change was needed there — recorded as a regression fence instead). The
real encrypted-then-decrypted round trip in the schema-mismatch test uses the actual
`ERI_SYMMETRIC_KEY` AES-128-ECB/PKCS7 scheme `decrypt_prefill()` implements, not a stub, so a
future accidental change to that decryption logic would also be caught here.

### 13.5 Wired into the unified filing pipeline: `POST /api/v1/filing/{client}/{ay}/{form}/submit`

With `validate.py`/`submit.py` proven and the header-field mapping (PAN, `ReturnFileSec` →
`filingTypeCd`/`incomeTaxSecCd`) worked out for §13.2, the last piece to make Type-2 actually
reachable end-to-end through Taxify's own API (not a standalone script) was wiring it into
`app/routers/filing.py`'s existing `/submit` endpoint, which previously just returned
`501 "Type-2 submission is deferred until the next implementation phase"` for `ERI_MODE=type2`
unconditionally — the module's own docstring even still said *"for Type-3 now and Type-2
transport later"*.

`submit_via_portal()` now dispatches on `creds.mode`: Type-3 keeps its existing Playwright job
queue unchanged; Type-2 calls a new `_submit_via_type2_api()`, which is **synchronous** (no job
queue needed — `validateItr`/`submitItr` are ordinary HTTPS calls returning in seconds, unlike
a browser automation job):

1. Restricts to ITR-1/ITR-4 (matching the Type-3 endpoint's own restriction, and this season's
   scope generally).
2. Reuses `produce_itd_json()` — the SAME mode-agnostic JSON producer Type-3 already uses (its
   own docstring already anticipated this: *"Type-2 (next season): JSON → validate → signed API
   envelope via AWS"*) — so there is exactly one JSON-generation code path for both modes, not
   two that could drift.
3. Extracts `PAN` and `ReturnFileSec` directly from the generated JSON
   (`official["ITR"]["ITR1"/"ITR4"]["PersonalInfo"]["PAN"]` /
   `["FilingStatus"]["ReturnFileSec"]`) rather than re-deriving them from the draft a second
   time — one source of truth, confirmed to have the identical nested-key shape across both
   forms. Maps `ReturnFileSec` to `filingTypeCd` (`"R"` only for 17/revised, `"O"` otherwise)
   and `incomeTaxSecCd` (the code itself, as a string).
4. Converts Taxify's own `ay` route param (`"YYYY-YY"`, e.g. `"2026-27"`) to the bare `"YYYY"`
   Type-2 actually wants (`"2026"`) — confirmed by §13's live prefill calls, which is the only
   place in this codebase this exact conversion had already been empirically verified.
5. Logs in, calls `validate_itr()`, and only calls `submit_itr()` if validation raised no
   `ERIApiError` — an invalid return must never reach the actual submit call.
6. Persists the ARN into `FilingRecord` via the same `upsert_filing_record()`/
   `log_filing_action()` helpers Type-3 already uses.

**Deliberately out of scope for this endpoint**: e-verification. `verify_evc()`/`generate_evc()`
need the taxpayer's live OTP consent, which cannot happen inside one synchronous HTTP call —
use the separately-wired `/api/v1/eri/generate-evc` and `/verify-evc` routes (§12.5's sibling
routes) as a follow-up step, the same way acknowledgement retrieval is already a separate step
for both modes.

`tests/test_filing_type2_submit.py` (new) covers the dispatch, the field-mapping (including the
17→"R" case), the ITR-2 rejection, and — importantly — that a `validateItr` rejection stops the
flow before `submitItr` is ever called, so an invalid return can never actually be filed.

### 13.6 `everify.py`/`acknowledgement.py` desk-audited against their specs
— no discrepancies found

Given §13.2 found real spec-vs-reality gaps in `prefill.py`, the two remaining unverified Type-2
modules touching the rest of the flow (`everify.py` — `EriUpdateVerMode`/`EriGenerateEvcService`/
`EriVerifyEvcService`; `acknowledgement.py` — `EriGetAckowledgement`, including matching ITD's
own spelling typo exactly) were checked field-by-field against `API_Everify_Return_v1.1.pdf` and
`API_AcknowledgementFlow.pdf`'s request tables *and* sample-request JSON (not the table alone,
since the table alone is exactly what misled §13.2's `prefill.py` fixes at first). Every
`serviceName` and field name already in the code matches the spec exactly, including the
per-endpoint inconsistency of whether `eriUserId` appears a second time inside the signed data
payload (`generateEvc`/`verifyEvc` include it; `updateVerMode`/`getAckowledgement` don't) — this
already-correct code was left unchanged. **Not the same as a live-call verification** — §13.2's
`prefill.py` fixes were only trusted after being proven against a real HTTP response, and these
two modules have not yet been exercised against a live e-verify/acknowledgement call (that
requires an already-submitted return with a real ARN, which doesn't exist yet — see §13.5). Treat
this as "no known issue," not "proven correct."

Also added this session: `tests/test_eri_routers.py` gained coverage for the four e-verify/
acknowledgement routes (`update-ver-mode`, `generate-evc`, `verify-evc`, `get-acknowledgement`)
wired in §12.5 — they existed with zero test coverage until now, including the
`get-acknowledgement` route's distinct raw-PDF-`Response` return shape (every other Type-2 route
returns a JSON dict).

## 14. Phase B — WireGuard whitelisted-egress relay: built and verified
(2026-09-04)

The one piece §12.3 deferred: routing Type-2 outbound traffic through the AWS jump-box
(`ERI-UAT-Server`, instance `i-03efbd3dbd1cc35eb`, public IP `13.204.49.125`, the account
whitelisted with ITD for both UAT and production — **not** the separate, unrelated free-tier
account `Docs/AWS_FREE_TIER_DEPLOYMENT.md` provisions) so signing can stay in-process on the
local machine (§12) while egress still appears to come from the whitelisted IP.

### 15.1 Architecture actually built

```
Local Windows machine (backend + DSC signing, in-process, §12)
        │  WireGuard tunnel, client AllowedIPs scoped to 43.239.60.30/32 ONLY
        │  (all other traffic -- browsing, other apps -- bypasses the tunnel entirely)
        ▼
AWS jump-box (ERI-UAT-Server, 13.204.49.125) — WireGuard peer at 10.66.0.1,
  local machine at 10.66.0.2, UDP 51820
        │  iptables: MASQUERADE + FORWARD ACCEPT scoped to
        │  (10.66.0.2 → 43.239.60.30) and its return traffic ONLY;
        │  explicit catch-all DROP for any other wg0-sourced traffic
        │  (the box's baseline FORWARD policy is ACCEPT, so this catch-all
        │  is what actually keeps the box from becoming a general relay,
        │  not the MASQUERADE rule's own destination scoping alone)
        ▼
ITD Type-2 UAT gateway (43.239.60.30, uatocpservices.incometax.gov.in)
```

No nginx relay, no HTTP-level proxy — WireGuard operates below TLS entirely, so the jump-box
never terminates or sees the decrypted PII/OTP-bearing HTTPS session; it only forwards IP
packets between the two fixed endpoints. This was a deliberate choice over configuring the
box's pre-existing (but otherwise unrelated) default nginx install as a reverse proxy, which
would require either TLS termination (the jump-box would see plaintext) or `stream`-level SNI
passthrough (still a needless dependency on nginx behaving correctly for this narrow purpose).

### 15.2 What was found and fixed on the jump-box before WireGuard could
even install

- **Disk 97% full** (only 221 MB free) — blocked nothing yet, but would have blocked the
  WireGuard package download. Fixed: `apt-get clean` freed 423 MB of cached `.deb` files
  (safe — fully re-downloadable).
- **Broken package state**: `openjdk-17-jre-headless` was stuck mid-upgrade (installed
  `17.0.18+8-1~24.04.1`, needed `17.0.19+10-1~24.04.2` per stale package lists), which blocked
  `apt-get install wireguard` entirely with an unmet-dependencies error — unrelated to WireGuard
  itself, but any `apt install` on this box would have hit it. Confirmed via `apt-get
  --fix-broken install -s` (simulate first) that the fix was a clean upgrade of exactly that one
  package with zero removals, then applied it for real after `apt-get update` refreshed the
  stale package lists that caused the first fetch attempt to 404.
- **No AWS CLI, no IAM instance role** on this box — confirmed via the EC2 instance-metadata
  endpoint returning nothing for `iam/security-credentials/`. This meant the Security Group
  change (§14.3) could not be made from the box itself and needed the user's own AWS Console
  access — noted here since a future session might otherwise assume `aws ec2` commands would
  work from an SSH session on this box.
- `/etc/hosts` on the jump-box **already** had `43.239.60.30 uatocpservices.incometax.gov.in`
  (from the original ITR-1 UAT setup) — nothing to add there. The local Windows machine did
  *not* have this pin and public DNS happened to already resolve to the correct IP, but ITD's
  own onboarding email states the hosts-file pin as a requirement, not a fallback for when DNS
  is wrong — added it to the local machine's hosts file too rather than relying on DNS
  continuing to resolve correctly.
- The box's `/home/ubuntu/uat-login-test` directory (the source of §12's `.sh` reference
  scripts) was checked and found small (1.9 MB, 280 files) — **not** the disk-space source, in
  case a future session assumes otherwise; the real space was system-level (apt cache, as
  above) plus an unrelated 173 MB Maven `.m2` cache and a 32 MB `tax-erp-complete` directory,
  neither touched (unclear purpose, not blocking, left for the user to review separately).

### 15.3 Setup performed

1. WireGuard installed on both ends (`apt-get install wireguard` on the jump-box; `winget
   install WireGuard.WireGuard` locally).
2. Keypairs generated on both ends (`wg genkey`/`wg pubkey`) — note for future reference: piping
   a key from PowerShell into `wg.exe pubkey` directly corrupts it ("Trailing characters found
   after key") because PowerShell's native-process pipe re-encodes text; routing the same pipe
   through `cmd /c "type file | wg.exe pubkey"` avoids this by passing raw bytes.
3. Jump-box `/etc/wireguard/wg0.conf`: `Address = 10.66.0.1/24`, `ListenPort = 51820`, one peer
   (the local machine) with `AllowedIPs = 10.66.0.2/32`, plus `PostUp`/`PostDown` directives for
   the scoped MASQUERADE + FORWARD ACCEPT + catch-all DROP described in §14.1. Brought up via
   `wg-quick up wg0` and enabled at boot via `systemctl enable wg-quick@wg0`.
4. `net.ipv4.ip_forward=1` set persistently via `/etc/sysctl.d/99-wireguard-forward.conf`
   (previously `0`; the jump-box was not routing any traffic before this).
5. Local machine: `.conf` with `Address = 10.66.0.2/24`, one peer (the jump-box) with
   `Endpoint = 13.204.49.125:51820` and, critically, **`AllowedIPs = 43.239.60.30/32`** — this
   is what keeps the tunnel scoped to ITD traffic only on the client side, the same way the
   jump-box's catch-all DROP scopes it on the server side. Installed as a Windows service via
   `wireguard.exe /installtunnelservice <path>` (requires elevation — triggered a UAC prompt the
   user approved) so it survives reboots (`StartType: Automatic`, confirmed).
6. AWS Security Group `sg-0158cdd49be870e7d` (`launch-wizard-1`, attached to the `ERI-UAT-Server`
   instance — confirmed via the EC2 console before editing, not assumed) needed a new inbound
   rule: Custom UDP, port 51820, source scoped to the local machine's current public IP
   (`116.73.108.245/32`, via `api.ipify.org`) rather than `0.0.0.0/0` — WireGuard's own
   public-key auth makes a wide-open UDP port low-risk regardless, but there was no reason not
   to scope it. **This will need updating if the local machine's public IP changes** (e.g. ISP
   reassignment, router restart) — the tunnel will otherwise silently stop handshaking with no
   obvious error beyond connection timeouts.

### 15.4 Verification

- `wg show wg0` on the jump-box after a test connection: `latest handshake: 42 seconds ago`,
  `endpoint: 116.73.108.245:...` (the local machine's real public IP) — confirms the peer is who
  it should be.
- `iptables -t nat -L POSTROUTING -n -v` and `iptables -L FORWARD -n -v` packet/byte counters
  after the same test: the MASQUERADE rule and both scoped ACCEPT rules incremented; **the
  catch-all DROP rule stayed at 0 packets** — proof no other traffic attempted to transit the
  tunnel, not just that the scoping rules exist.
- `Test-NetConnection 43.239.60.30 -Port 443` from the local machine succeeded (this IP is not
  reachable at all without the tunnel, since it is whitelisted-only) — and a control test to an
  unrelated host (`www.google.com:443`) also succeeded normally, confirming the
  `AllowedIPs = 43.239.60.30/32` scoping did not accidentally capture other local traffic.
- **Update (2026-09-04, later same day): closed.** Re-ran both `eri_login()` and the full
  prefill flow (`request_prefill_otp()` → `get_prefill_data()`, PAN `GOYPT2026A`, AY 2025) with
  the tunnel live — both succeeded identically to §12.5/§13's earlier direct-IP runs. Confirmed
  the traffic genuinely transited the tunnel (not a coincidental direct path) by diffing
  `wg show wg0 transfer` and the `FORWARD` chain's packet/byte counters before and after each
  call: the login call moved counters from 1628/564 bytes and 7/3 packets to 13092/10484 bytes
  and 19/22 packets; the prefill flow (a much larger payload — the decrypted response includes
  every top-level form section, even the 53 `null` ones) moved them further to 59608/52288
  bytes and 75/100 packets. The catch-all `DROP` rule stayed at 0 packets throughout both
  calls, same as the transport-level test in §14.4 above. No code changes were needed — the
  tunnel is pure OS-level IP routing, entirely transparent to the application.

## 15. CRITICAL: `app/eri/digest.py`'s HMAC iteration count was off by
one — every Digest this engine ever computed was wrong (2026-09-04)

### 15.1 The bug

`compute_digest()` ran the HMAC-SHA256 loop exactly `iterations` times. The correct total, per
the SOP's own step numbering, is **`iterations + 1`**. The SOP (`Digest_generation_ERI 2
(2).pdf` §5.3 Step 5) lists three separate sub-steps: *"1. Initialize with the secret key. 2.
Hash the modified JSON string. 3. Repeat hashing for the specified number of iterations."* Read
literally, step 2 is **one** hash, and step 3 is **`iterations` additional** hashes on top of
that — `iterations + 1` total, not `iterations`. This module (and its
`API_Testing/digest_generator.py` sibling — a separate, unmodified script, see §15.4) both ran
the loop exactly `iterations` times, one hash short.

### 15.2 Why this went undetected for so long

This bug is **self-consistent** — `compute_digest()` always agreed with itself (recomputing over
the same content always reproduces the same, internally-consistent, but wrong, digest) — so
every offline check this session ran *before* discovering the bug (§12's digest-vs-SW_ID
verification, §13's prefill work, the JSON review in the "check this generated JSON" exchange)
correctly confirmed **internal** consistency without ever catching that the *algorithm itself*
didn't match ITD's real server. It had never been exercised against a live `validateItr`/
`submitItr` call before this session — the prior successful ITR-1 UAT/production pass that
earned Type-2 production access for ITR-1 must have used a different tool or process, not this
module (§12–14's login/prefill live-testing used the credential/signing path only; this session
is the first time `app/eri/digest.py`'s own algorithm was actually round-tripped against ITD's
server).

### 15.3 How it was found and confirmed

While validating the user's own manually-generated, manually-corrected ITR-4 JSON (SW_ID
correctly SW20014242/Type-2 UAT, schema-valid, arithmetic-verified — see the prior exchange),
`validateItr` rejected it every time with `errCd=Digest_Invalid,
desc="Modification to ITR details outside Utility is not allowed"` — regardless of five
different content-canonicalization attempts (original key order, sorted keys, float-vs-int
formatting, a pure character-level minify of the untouched downloaded file with zero Python JSON
re-parsing, and a completely fresh in-memory generation with zero file round-trip at all). Ruling
out formatting entirely, and after the user's direct assertion that ITR-1 had validated
successfully before (implying the algorithm, not the credentials, must be at fault), three
digest variants — `iterations`, `iterations + 1`, `iterations - 1` — were computed for the exact
same payload and submitted live. **Only `iterations + 1` passed**: the response changed from
`Digest_Invalid` to real ITR business-rule validation errors (§15.5), proving the digest check
itself now succeeds.

### 15.4 Fix and blast radius

Fixed: `compute_digest()`'s loop now runs `iterations + 1` times. Since `compute_digest()` is
"the single canonical source of the ITR JSON Digest" (its own module docstring) used by every
form builder (`app/engine/itd/itr1.py` through `itr4.py`, all via the shared `_creation_info()`/
`_compute_digest()` in `app/engine/itd/common.py`) for **both** Type-2 (API `validateItr`/
`submitItr`) **and** Type-3 (portal-uploaded JSON, `serialize_for_upload()`), this bug affected
**every ITR JSON this engine has ever produced**, for every form, both ERI modes, both UAT and
production. Any Type-3 JSON previously uploaded to ITD's portal via the Offline Mode would have
carried the same wrong digest and — if the portal's own integrity check is as strict as
`validateItr`'s — would have been rejected for the same reason.

`API_Testing/digest_generator.py` has the identical bug (confirmed: its `generate_digest()` also
loops exactly `iterations` times) but is **deliberately left unmodified** — the user's explicit
instruction was not to touch it, and it is a standalone script under separate development, not
depended on by the running application. `tests/test_eri_creation_info_invariant.py`'s existing
cross-reference test (which asserted `compute_digest()` matches that script's output) previously
"passed" only because both sides shared the same bug; it's been updated to call the reference
script with `iterations + 1` explicitly, preserving the cross-implementation check without
asserting the now-known-wrong `iterations`-only behavior as ground truth. A new test,
`test_compute_digest_total_hmac_operations_is_iterations_plus_one`, locks in the fix against an
independently hand-computed expected value (not derived by calling `compute_digest()` twice and
comparing to itself) — both confirmed via `git stash` to fail against the pre-fix code.

### 15.5 What surfaced once the digest check passed — not yet resolved

With `iterations + 1`, the SAME JSON that previously got `Digest_Invalid` now gets real
validation errors instead, including several that read as **old-regime rule text applied to a
new-regime return**: *"In case of Old Tax Regime, standard deduction shall be lower of Rs.50000
or Net salary"* (the JSON correctly carries the new-regime ₹75,000 standard deduction) and
*"Rebate u/s 87A cannot be more than 12,500 under old tax regime"* (the JSON's full rebate is
correct for new-regime AY 2026-27 thresholds). Also: *"Kindly enter the amount mentioned in Sl.
No E8 of Schedule BP in the field Business Income... of Part BTI"* and *"Multiple question shall
not be responded in A23"*. All nine errors from this batch were investigated and fixed — see
§16.

## 16. Four ITR-4 builder bugs found via live `validateItr` iteration — all nine errors from
§15.5 resolved to a clean pass (2026-09-04)

Once §15's digest fix let real business-rule errors through, iterating live against ITD's Type-2
UAT `validateItr` for the SRGPZ2026C ITR-4 test case (§17) surfaced 9 distinct errors across 4
independent root causes in `app/engine/itd/itr4.py`. Fixing all four, in order, took the same
JSON from 9 errors → 7 → 5 → 2 → 1 → **0, `successFlag: true`**. Each fix has a regression test
in `tests/test_filing_gateway_v2_itr4.py`, confirmed via `git stash` to fail against the pre-fix
code.

### 16.1 `ScheduleBP.PersumptiveInc44AE.IncChargeableUnderBus` was 0 whenever no 44AE business
existed

**Bug**: `_schedule_bp()` only computed `IncChargeableUnderBus` (the official schema's aggregate
"Income chargeable under Business & Profession" field — despite living inside the
`PersumptiveInc44AE` block, it is documented as the sum across **all three** presumptive
schemes, not just 44AE) inside the `if goods_44ae is not None:` branch. Any return with 44AD
and/or 44ADA income but **no** 44AE (goods-carriage) business — the common case — left this
field hardcoded at its placeholder default of `0`, even though `IncomeDeductions.
IncomeFromBusinessProf` was correctly populated. ITD's live validator caught the mismatch from
both directions: *"Kindly enter the amount mentioned in Sl. No E8 of Schedule BP in the field
Business Income... of Part BTI"* and *"Enter sum of values mentioned in field 'Presumptive
income under section 44AD, ...44ADA... and ...44AE' in the field 'Income chargeable under
Business & Profession' of schedule BP"*.

**Fix**: compute `IncChargeableUnderBus` as `income_44ad + income_44ada + income_44ae`
unconditionally, in the base `PersumptiveInc44AE` dict built before any scheme-specific branch
runs (`app/engine/itd/itr4.py` ~line 741). The `goods_44ae is not None` branch already computed
the same sum correctly when it ran; the bug only manifested in its absence.

**Test**: `test_generate_itr4_schedule_bp_income_chargeable_set_without_44ae` — the only existing
test asserting on `IncChargeableUnderBus` (`test_generate_itr4_schedule_bp_supports_all_three_
schemes`) always had 44AE present, so it never exercised the buggy path.

### 16.2 Form 10-IEA regime cascade: wrong default + two branches answered at once

**Bug, part 1**: `Form10IEAEarlierAYOldRegime` — Sl. No. **A23** of Part A-General, "Have you
filed Form 10-IEA in any earlier AY for choosing old tax regime?" — defaulted to `"NA"` in both
`ITR4FilingProfile` (`app/schemas/itr4.py`) and `ReturnDraft.filing` (`app/schemas/
return_draft.py`). The official schema's enum (`NA|Y|N`) permits this, but CBDT's own **ITR-4
Validation Rules AY 2026-27** (`tmp/cbdt_rules/CBDT_e-Filing_ITR 4_Validation Rules_AY 2026-27
(1).txt`) rule #260 states *"It is mandatory to select an Option for 115BAC question at sl.no.
A23... Applicable in case of Individual and HUF"* — `"NA"` is reserved for Firm status only
(rule #235). ITD's live validator rejected `"NA"` for our Individual test case with exactly that
message.

**Bug, part 2**: A23 gates two **mutually exclusive** sub-branches (rules #353–364): answering
"Yes" (filed 10-IEA before) activates A23(A) — `F10IEAEarlierAYNewRegime`/`F10IEACurrAYNewRegime`
and their date/ack descendants; answering "No" activates **only** A23(B) —
`F10IEACurrAYOldRegime`. `_filing_status_itr4()` emitted **both** branches unconditionally,
regardless of the A23 answer. ITD's live validator rejected this with *"Multiple question shall
not be responded in A23"*.

**Fix**: default `form_10iea_earlier_ay_old_regime`/`form10IEAEarlierAYOldRegime` to `"N"`
(`app/schemas/itr4.py`, `app/schemas/return_draft.py`). Restructured `_filing_status_itr4()`
(`app/engine/itd/itr4.py` ~line 310) so the A23(A) fields are emitted only when the answer is
`"Y"`, and A23(B) (`F10IEACurrAYOldRegime`) only when `"N"` — never both. The `profile is None`
placeholder branch got the same treatment.

**Tests**: `test_generate_itr4_filing_status_form10iea_default_answers_only_a23b`,
`test_generate_itr4_filing_status_form10iea_yes_branch_excludes_a23b`.

### 16.3 `Schedule80C` was emitted as an empty placeholder even when nothing was claimed

**Bug**: every other optional deduction schedule (`Schedule80D`, `ScheduleEA10_13A`, the
80G/80E/80EE/80EEA/80EEB family via `_emit_conditional_deduction_schedules`) is omitted from the
output entirely when nothing is claimed. `Schedule80C` was the one outlier — it was always
present in the dict literal, `{"Schedule80CDtls": [], "TotalAmt": 0}` when unclaimed. `Schedule
80C` is not in the schema's top-level `required` list, so this placeholder was legal per-schema
but not per ITD's live business rules: CBDT rule #305 says an Individual on the **new tax
regime** who has "filled" **any** of the 80C/80E/80EE/80EEA/80EEB/10(13A) schedules is rejected
— and ITD's live validator treats the mere *presence* of the key as "filled," regardless of its
contents being all-zero. Rejected with *"Since you have selected new tax regime deduction u/s
10(13A), 80C, 80E, 80EE, 80EEA or 80EEB are not applicable to you."*

**Fix**: `Schedule80C` is now added to the `itr4` dict only when `deduction("80C") > 0`
(`app/engine/itd/itr4.py` ~line 2157), matching every sibling schedule's pattern.

**Test**: `test_generate_itr4_omits_schedule80c_when_no_80c_claim`.

### 16.4 `AlternateAddress`/`SecondaryAdd` were omitted when no distinct secondary address existed

**Bug**: `SecondaryAdd` was `"Y"` only if `profile.alternate_address` was supplied, and
`AlternateAddress` was omitted entirely otherwise. `app/engine/validators/itr4/input_rules.py`'s
rule R410 had already flagged this — *"Secondary address is mandatory in Part A General
Information"* — but only as an **informational** check, never enforced at JSON-build time. ITD's
live validator confirmed it as a hard requirement, rejecting the entirely-absent block with
*"Secondary address details are not provided in Schedule Part A General information."*

**Fix**: `_personal_info_from_profile()` (`app/engine/itd/itr4.py` ~line 185) now always sets
`SecondaryAdd: "Y"` and always emits `AlternateAddress`, defaulting to
`profile.alternate_address or profile.primary_address` — i.e. "secondary same as primary" when
no genuinely distinct secondary address was supplied. This works directly because
`ITR4FilingAddress` (the primary address type) is a schema subclass of `ITR4PostalAddress` (what
`AlternateAddress` needs), so no new address-mapping code was required.

**Test**: `test_generate_itr4_defaults_alternate_address_to_primary`.

### 16.5 Net result

Live-tested end to end against Type-2 UAT `validateItr` for PAN SRGPZ2026C (§17): 9 errors → 0,
`successFlag: true`, `arnNumber`/`transactionNo: "35481079"` returned on the validate call
(non-mutating; `submitItr` was not called). All four fixes plus §15's digest fix are code
changes in this session, none yet committed as of this writing — see §17 for the full test-case
trace and current filing status.

## 17. SRGPZ2026C ITR-4 UAT test case — trace and current status (2026-09-04)

Single dummy PAN used to exercise the remaining Type-2 UAT flow for ITR-4 (ITR-1 is already
Type-2 production; ITR-2/ITR-3 are not yet production-ready, so cannot be tested this way): PAN
`SRGPZ2026C`, Sourav Hari Gupta, DOB 1995-01-01, EVC-enabled (BANKEVC).

**Test case**: salary (₹8,25,000 gross, ₹75,000 standard deduction under 115BAC), savings/FD
bank interest (₹37,027), and 44AD presumptive business income ("THE BITS HUB", cash sales of
handcrafted materials, ₹4,00,000 turnover, ₹32,415 declared income at 8%). Belated return
(`ReturnFileSec: 12`), late fee ₹5,000 u/s 234F, TDS ₹35,000, refund due ₹30,000 to an SBI
account. New tax regime throughout (no Chapter VI-A/10(13A) claims).

**Error-reduction trace** (all through live Type-2 UAT `validateItr`, WireGuard tunnel via the
AWS jump-box, §14):

| Round | Change | Errors |
|---|---|---|
| 1 | First live pass, `iterations`-only digest | `Digest_Invalid` (§15) |
| 2 | Digest fixed to `iterations + 1` | 9 errors (§15.5) |
| 3 | ScheduleBP fix (§16.1) | 7 errors |
| 3b | + regime-cascade fix attempt (`F10IEACurrAYNewRegime="Y"`, later found wrong — see below) | 5 errors, one NEW error surfaced (10-IEA ack-number requirement) |
| 4 | + correct regime-cascade fix (§16.2, A23="N" branch only) | 2 errors |
| 4b | + Schedule80C omission (§16.3) | 1 error (secondary address) |
| 4c | + AlternateAddress default (§16.4) | **0 errors**, `successFlag: true` |

One dead end worth recording: an intermediate hypothesis tried setting `F10IEACurrAYNewRegime:
"Y"` (declaring an explicit new-regime election) to satisfy the "mandatory 115BAC" check. ITD's
live response showed this was the *wrong* field — `F10IEACurrAYNewRegime="Y"` specifically means
"I am re-entering the new regime via Form 10-IEA after having previously opted out," which
doesn't apply to a taxpayer who was never in the old regime, and it triggered its own new error
(*"Since A23(A)(ii)(b) is selected as 'Yes' A(ii)(b)(i) can not be blank"*) demanding an
acknowledgement number for a form that was never filed. The actual fix (§16.2) was to answer
**only** A23(B), not A23(A) at all — found by reading CBDT's own Validation Rules text (rules
#353–364) rather than further guessing.

**Final status (updated after live `submitItr`/`getAcknowledgement` calls, 2026-09-04)**: the
return was genuinely **filed**. `submitItr`, called with round-7's frontend-generated JSON (the
first round built entirely by the fixed code, with no manual patching — see §17.1), returned a
`messages[].type == "ERROR"` entry (`ADHAAR_NOTIN_PROFILE_2026_004`, unlinked PAN-Aadhaar on the
test profile) that Taxify's own client code treated as a hard failure and raised on. It was not
one: ITD emailed the taxpayer a genuine ITR-V acknowledgement (Acknowledgement Number
**116997020040926**, filed 04-Sep-2026, u/s 139(4)) proving the submission was accepted despite
that message. See §18.1 for the `parse_response_envelope()` fix this required, and §18 generally
for every fix made after this point (e-Verification prerequisites, `getAcknowledgement`
retrieval). e-Verification itself remains blocked — see §18.4 — pending an ITD reply on the test
PAN's bank-account EVC enablement.

The official ITD Test Scenario Sheet (`Reference Docs by CBDT & ITD/Official ERI REFERENCE
Documentation/ERI Type 2 - Sunit Ramashankar Goyanka-UAT Test Scenario Sheet (3).xlsx`) has been
filled in with these results (rows 13–20); e-Verification is marked "In Progress" there pending
ITD's response.

### 17.1 Round-7: the first fully clean, unpatched frontend JSON

Rounds 1–4c (the table above) all involved the assistant manually patching a downloaded JSON in
a scratch script to test a hypothesis before the fix was reflected in a fresh app-generated file
— necessary because each fix required either a code change the running `run.py` process hadn't
picked up yet, or an explicit user action in the frontend (e.g. toggling the Form 10-IEA
dropdown). Round 7 (`CBDT_790f586e-62a0-44c7-95b6-30e75cb58b08_2026-27 (7).json`) was the first
JSON downloaded directly from the frontend, with zero manual patching, that validated with 0
errors — confirming all four `itr4.py`/schema fixes (§16) were correctly live in the running app
and that the frontend's "Form 10-IEA" dropdown (`PersonalInfoTab.tsx`) had been set to "No" for
this client. Round 8 (`... (8).json`) additionally omitted `AadhaarCardNo` (schema-optional,
confirmed via `PersonalInfo`'s `required` list) and re-validated clean before the submit attempt.

## 18. Post-submission fixes — three more live-only bugs found getting from `submitItr` to a
retrievable acknowledgement PDF (2026-09-04)

Getting the round-7/8 JSON's genuine acceptance (§17, ARN 116997020040926) fully confirmed and
then retrieving its acknowledgement surfaced three more real, live-only bugs — none catchable by
reading the spec PDFs alone, each found by iterating live calls against ITD's Type-2 UAT. This
section documents each one in the same depth as §15/§16, plus a complete file-by-file record of
every file this session's ITR-4 work touched, for future reference.

### 18.1 `parse_response_envelope()` discarded a genuine ARN because of an unconditional
raise-on-any-ERROR-message rule

**Symptom**: `submitItr` for the round-7/8 JSON returned HTTP 200 with a `messages[]` entry
`{code: "ADHAAR_NOTIN_PROFILE_2026_004", type: "ERROR", desc: "It is seen that, your PAN and
Aadhaar are not linked...", fieldName: null}`. `app/eri/type2/submit.py::submit_itr()` — via
`parse_response_envelope()` — raised `ERIApiError`, which the assistant initially (wrongly)
treated as proof the submission had failed outright, and reported that as the outcome.

**How the mistake was caught**: the user asserted from direct evidence — ITD had emailed a real
ITR-V acknowledgement PDF — that the return actually had been filed, and asked "so how will be
resubmitted" and "the aadhar rejection might just be a warning nothing else." Re-running
`validateItr`/`submitItr` for the same PAN+AY+form independently confirmed this: every
subsequent call was rejected with `EF20006 "Your return is already submitted. You cannot
resubmit it."` — impossible unless the original submission had genuinely succeeded, since a
truly-failed submission consumes no filing slot.

**Root cause**: `app/eri/envelope.py::parse_response_envelope()` (before this fix) raised on the
*first* `messages[]` entry with `type == "ERROR"`, unconditionally, discarding the rest of the
response body — including any `arnNumber` field — before the caller ever saw it. ITD's live
Type-2 UAT `submitItr` evidently uses `type: "ERROR"` for at least one condition
(PAN-Aadhaar-not-linked) that is a **warning attached to a successful submission**, not a
rejection of it — a distinction the spec text nowhere states, and one that contradicts every
other endpoint's use of `type: "ERROR"` observed this session (login, addClient, validate, where
an ERROR-typed message always did mean outright failure).

**Fix**: `parse_response_envelope()` (`app/eri/envelope.py`, function starting line ~251) now
checks `response_json.get("arnNumber")` first — if truthy, the response is returned as-is,
bypassing the ERROR-message/errors-array raise logic entirely. An ARN is the one field ITD only
issues on genuine acceptance, so its presence is a strictly more reliable success signal than
any `messages[].type` value. This does not change behavior for any endpoint that never returns
an `arnNumber` (login, addClient, everify, prefill) — the new check is a no-op for them.

**Test**: `tests/test_eri_envelope.py::test_parse_response_envelope_arn_present_overrides_error_message`
— constructs the exact response shape ITD returned live, asserts `parse_response_envelope()`
returns it (does not raise) and preserves the `arnNumber`.

**Caution for future readers**: do not read this fix as "ERROR-typed messages are generally
non-fatal." They remain fatal everywhere except when an `arnNumber` is also present. If a future
endpoint is found where a genuine ARN-bearing success also needs additional error-message
handling (e.g. surfacing the warning text to the user without treating it as failure), extend
the response object's warning list rather than loosening the raise condition further.

### 18.2 `generateEvc`/`verifyEvc` sent an undocumented, rejected `eriUserId` field inside the
signed payload

**Symptom**: `generate_evc()` (BANKEVC mode, ARN 116997020040926) was rejected with
`EF40000 "JSON data invalid"` — a generic schema-validation failure with no field-level detail.

**Root cause**: `app/eri/type2/everify.py`'s `generate_evc()` and `verify_evc()` both included
`"eriUserId": eri_user_id` as a key inside the signed `data` payload (in addition to
`build_request_envelope()` already placing `eriUserId` at the outer envelope level, which every
Type-2 endpoint requires and which is correct). Every other module in this codebase
(`login.py`, `add_client.py`, `validate.py`, `submit.py`, `acknowledgement.py`) puts `eriUserId`
*only* in the envelope, never inside the signed payload — `everify.py` was the sole outlier.
Cross-checked against `tmp/pdf_text/API_Everify_Return_v1.1 (1).txt`'s own "Details of data
attribute" tables (§5.4.3 for `generateEvc`, the equivalent table for `verifyEvc`): neither lists
`eriUserId` among the documented fields (`serviceName`, `pan`, `verMode`, `ackNum`, `ay`,
`formCode` for generate; plus `transactionId`/`otpValue`/`evcValue` for verify). ITD's live
schema validation for this specific endpoint is evidently strict about unexpected fields in a
way `validateItr`/`submitItr` are not (those tolerate the same `timeStamp` field despite it also
being absent from their own documented tables — a known, deliberately-kept quirk per this
file's earlier sections).

**Fix**: removed `"eriUserId": eri_user_id` from both payload dicts in `everify.py`. The local
`eri_user_id` variable is still resolved and still passed to `build_request_envelope()` — only
the redundant, rejected duplicate inside the signed payload was removed.

**Verification**: re-running `generate_evc()` after the fix returned a *different*, legitimate
business-rule error (`EF00101`, §18.4) instead of `EF40000` — proof the payload-shape issue
itself was resolved, isolating the remaining blocker to something else entirely.

**Test coverage note**: no new unit test was added for this specific fix (the existing
`tests/test_eri_routers.py` EVC-route tests already mock at the `everify.generate_evc`/
`verify_evc` function boundary and would not have caught a payload-shape regression one level
deeper; a live-call-verified fix without a matching unit test is an acknowledged gap here,
unlike every other fix in this file).

### 18.3 `getAcknowledgement`'s live UAT response is intermittently a malformed, Java-serialized
wrapper around the real PDF — not a clean binary body

**Symptom**: `get_acknowledgement(pan="SRGPZ2026C", ack_number="116997020040926", ...)` raised
`ERIApiError("UNEXPECTED", "Received JSON success response instead of PDF binary.")`. The
response's `Content-Type` header was `application/json`, but `response.json()` itself raised
`JSONDecodeError: Expecting value` — the declared content type was wrong on both counts (not a
real PDF binary, and not real JSON either).

**Diagnosis**: printing the raw response bytes showed they began with `\xac\xed\x00\x05` — the
standard Java `ObjectOutputStream` serialization stream header — followed by readable embedded
strings (`java.util.HashMap`, `Transfer-Encoding`, `chunked`, `Date`, `Content-Type`,
`application/pdf`) consistent with a serialized wrapper around an upstream HTTP response object,
and a `%PDF-1.4` marker further into the byte stream. This is a genuine ITD-side bug: their
`getAcknowledgement` backend appears to, at least sometimes, serialize its own internal
HTTP-response object (headers included) as the API response body instead of extracting and
returning just the PDF bytes, while still labeling the `Content-Type` header
`application/json`.

**Confirmed independently, twice**: (1) the SAME malformed structure was found inside the ITR-V
PDF file ITD emailed the taxpayer directly (`Pdf_116997020040926.pdf`, downloaded by the user) —
proving this is a bug in whatever generates the PDF content ITD-side, not an artifact of the
`getAcknowledgement` API path specifically. (2) Re-running the live API call after the fix
(twice, in separate turns) reproduced the identical wrapped structure both times for this same
ARN — not a one-off transient glitch for this specific ARN.

**Confirmed NOT universal**: `uat-login-test/acknowledgement_GOYPT2026B_111202010240326.pdf`
(saved during the original ITR-1 UAT round, a different PAN/ARN) is a **clean, unwrapped PDF**
starting directly with `%PDF-1.4` at byte 0 — no Java-serialization wrapper at all. So this is an
intermittent ITD-side inconsistency (possibly load-balanced across backend instances, one of
which has this bug and one of which doesn't), not a constant characteristic of the endpoint.
Client code must tolerate *both* shapes.

**Fix**: `get_acknowledgement()` (`app/eri/type2/acknowledgement.py`) no longer branches on the
`Content-Type` header to decide success vs. failure. It now searches `response.content` for the
`%PDF-` marker (via `bytes.find`, which returns `0` for a clean unwrapped response and a
positive offset for a wrapped one) and, if found, returns the slice from there through the last
`%%EOF` marker (`bytes.rfind`) inclusive — correctly handling both the clean case and the
wrapped case with the same code path. Only when no `%PDF-` marker is found at all does it fall
back to the original Content-Type/JSON-based error-parsing logic.

**Tests**: `tests/test_eri_acknowledgement.py` (new file) —
`test_get_acknowledgement_extracts_pdf_from_malformed_java_serialized_response` (constructs a
synthetic Java-serialization-wrapped body and asserts the correct PDF bytes are extracted) and
`test_get_acknowledgement_raises_on_real_json_error` (a genuine JSON error response, no embedded
PDF, must still raise `ERIApiError` with the server's code/desc — guards against the new
magic-bytes detection swallowing real errors). Both confirmed via `git stash` against the pre-fix
code: the malformed-extraction test fails (as expected, `UNEXPECTED` error raised instead of
returning the PDF), the error-handling test already passed (pre-existing correct behavior,
included as a regression fence).

**End-to-end verification**: after the fix, `get_acknowledgement()` was called live twice more
(fresh login each time) and both times correctly extracted a 48,880-byte PDF that opens cleanly
— confirmed both via text-content extraction (matches the emailed ITR-V exactly: Acknowledgement
Number 116997020040926, PAN SRGPZ2026C, Form ITR-4, filed u/s 139(4)) and via a full visual
render in the browser preview pane (correct layout, Income Tax Department watermark, readable
barcode/QR image, all 8 instruction paragraphs present, single page). The PDF was also saved to
`Downloads/ITR4_Acknowledgement_SRGPZ2026C_116997020040926.pdf` and auto-opened via
`os.startfile()` per the user's request that a downloaded acknowledgement auto-open — this is
scratch-script behavior for this session's testing, not yet built into the app's own frontend
(no frontend UI currently calls `POST /api/v1/eri/get-acknowledgement` at all — see the route in
`app/routers/integration.py` — so there is nothing there to add auto-open behavior to yet; that
becomes relevant only once a frontend acknowledgement-download feature is built).

### 18.4 Still open: e-Verification blocked on the test PAN's bank-account EVC enablement

`generate_evc(ver_mode="BANKEVC")` for SRGPZ2026C is rejected with `EF00101 "To generate EVC,
you need to validate and enable EVC on your bank account."` This is a live ITD-side account-state
condition, not a Taxify defect (confirmed via §18.2's fix ruling out the payload-shape
hypothesis first). The bank account in the filed JSON (SBIN0000306 / 39210261985) is not
validated/EVC-enabled on ITD's UAT profile for this PAN, despite the original test-PAN sheet's
"EVC Enabled - BANKEVC" remark. User has emailed ITD about this; held pending their reply.
Acknowledgement retrieval (§18.3) and the "already filed" status (§17) do not depend on
e-Verification succeeding, so this does not block anything else already completed.

### 18.5 Complete file-by-file record for this ITR-4 UAT round (2026-09-04)

Every file created or modified while getting SRGPZ2026C's ITR-4 through validate → submit →
acknowledgement, for future reference. Grouped by what each one is for.

**Digest/algorithm fix** (§15, carried over from earlier in this same session — listed here for
completeness of the file inventory):
- `app/eri/digest.py` — `compute_digest()`'s HMAC loop fixed to `iterations + 1`.
- `tests/test_eri_creation_info_invariant.py` — updated cross-reference test plus a new
  independently-hand-computed-expected-value test for the iteration count.

**ITR-4 CBDT-JSON builder fixes** (§16):
- `app/engine/itd/itr4.py` — four separate fixes: `ScheduleBP.PersumptiveInc44AE.
  IncChargeableUnderBus` aggregate computation (§16.1); `_filing_status_itr4()`'s Form 10-IEA
  cascade restructured to answer only one of the two mutually-exclusive A23 branches (§16.2);
  `Schedule80C` changed from an unconditional empty placeholder to conditional emission
  (§16.3); `_personal_info_from_profile()`'s `AlternateAddress`/`SecondaryAdd` now always
  emitted, defaulting to the primary address (§16.4).
- `app/schemas/itr4.py` — `ITR4FilingProfile.form_10iea_earlier_ay_old_regime` default changed
  `"NA"` → `"N"`.
- `app/schemas/return_draft.py` — `Filing.form10IEAEarlierAYOldRegime` default changed `"NA"` →
  `"N"` (same reasoning, draft-schema side).
- `frontend/src/domain/returns/factory.ts` — `createEmptyDraft()`'s
  `form10IEAEarlierAYOldRegime` default changed `"NA"` → `"N"` (the frontend has its own
  independent default; the backend schema fix alone does not reach the frontend's own draft
  factory, and a request payload with an explicit `"NA"` overrides any backend default anyway).
- `tests/test_filing_gateway_v2_itr4.py` — five new tests:
  `test_generate_itr4_schedule_bp_income_chargeable_set_without_44ae`,
  `test_generate_itr4_filing_status_form10iea_default_answers_only_a23b`,
  `test_generate_itr4_filing_status_form10iea_yes_branch_excludes_a23b`,
  `test_generate_itr4_omits_schedule80c_when_no_80c_claim`,
  `test_generate_itr4_defaults_alternate_address_to_primary`.

**Post-submission fixes** (§18.1–18.3):
- `app/eri/envelope.py` — `parse_response_envelope()` now returns early on a truthy `arnNumber`
  before evaluating the ERROR-message/errors-array raise logic (§18.1).
- `app/eri/type2/everify.py` — removed the redundant `eriUserId` key from both
  `generate_evc()`'s and `verify_evc()`'s payload dicts (§18.2).
- `app/eri/type2/acknowledgement.py` — `get_acknowledgement()` rewritten to locate the embedded
  PDF via `%PDF-`/`%%EOF` byte markers rather than trusting `Content-Type` (§18.3).
- `tests/test_eri_envelope.py` — new test
  `test_parse_response_envelope_arn_present_overrides_error_message`.
- `tests/test_eri_acknowledgement.py` — new file, two tests (§18.3).
- `tests/test_eri_type2_validate_submit.py` — one pre-existing test
  (`test_build_itr_payload_shape`) fixed in passing: it asserted `formData` was a plain JSON
  string, stale since the base64-encoding fix earlier in this session; updated to
  base64-decode before comparing. Unrelated to this round's own fixes, but touched the same
  file area and was trivial to fix alongside it.

**Documentation**:
- `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` — this file: §16 (four ITR-4 builder bugs), §17
  (SRGPZ2026C test-case trace, updated in this pass with the final filed/ARN outcome and the
  round-7/8 clean-JSON note at §17.1), §18 (this section).
- `CLAUDE.md` — pointer to §16's four builder bugs added under the existing digest paragraph
  (added earlier in this session); a further pointer to §18's post-submission fixes is added in
  this same pass.

**Reference material read (not modified)**, for anyone retracing this investigation:
- `tmp/cbdt_rules/CBDT_e-Filing_ITR 4_Validation Rules_AY 2026-27 (1).txt` — source for rules
  #260, #235, #305, #353–364 (the Form 10-IEA/A23 cascade and Schedule80C business rules).
- `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-4_2026_Main_V1.1 (2).json` — source for
  confirming `AadhaarCardNo`/`Schedule80C`/the various Form-10IEA fields' required-vs-optional
  status, and for ruling out a standalone "115BAC election" field distinct from the Form 10-IEA
  cascade.
- `tmp/pdf_text/API_Everify_Return_v1.1 (1).txt`, `tmp/pdf_text/API_AcknowledgementFlow (1).txt`
  — sources for §18.2/§18.3's documented-field cross-checks.
- `uat-login-test/get_acknowledgement.sh`,
  `uat-login-test/acknowledgement_GOYPT2026B_111202010240326.pdf` — the original ITR-1 UAT
  round's acknowledgement retrieval, used as the counter-example proving §18.3's malformed
  response is intermittent, not universal.

**Test-only artifacts (not part of the repo, not committed)**: numerous ad-hoc scripts in this
session's scratchpad directory (`validate_round{3,4,4b,4c,6,7,8}*.py`,
`submit_round7.py`, `generate_evc.py`, `check_ack.py`, `check_real_ack*.py`,
`get_ack_and_open.py`, `retry_login_validate_submit.py`, `add_client_*.py`, `recheck_fresh.py`,
`digest_iteration_test.py`) were used to iterate live against ITD's Type-2 UAT one hypothesis at
a time before each fix was written into the actual application code. None of these are meant to
be preserved long-term; the corresponding application code and `tests/` files above are the
durable record.

## 19. References

- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/ERI API Specification_v1.1 (4).pdf`
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/Digest_generation_ERI 2 (2).pdf`
  (the Type-3 onboarding SOP, including the UAT-certification process description)
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/API_Everify_Return_v1.1 (1).pdf`
- `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` — original architecture, phase history
- `Docs/ERI_UAT_EXPANSION_PLAN.md` — multi-form UAT-pack rollout plan (§2.3 flags a discrepancy)
- `Docs/ITR1_ITR4_FILING_SUBMISSION_PIPELINE_AUDIT_AY2026_27.md` — the full pipeline audit this
  document's findings were drawn from, with additional detail (e.g. `_personal_info_base`'s
  unreachable PII fallback defaults, the test-isolation fix) not repeated here
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/API_SubmitFlow_v1.1 (1).pdf`
  — §12.5's source for `validate.py`/`submit.py`'s request/response shape and the errCd/errFld
  error format
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/ERI Data Signature process
  guide V0.2 2 1 1 (3).pdf` — ITD's own reference Java/BouncyCastle signing implementation;
  §12.2's confirmation that CMS/PKCS#7 SignedData (not a bare RSA signature) is the expected
  format
- `List of UAT/Production URLs for Type 2` PDFs (same folder) — §12.3's source for the IP
  whitelisting precondition
- `Docs/AWS_FREE_TIER_DEPLOYMENT.md` — §12.3 corrects its "RESOLVED — ITD IP whitelisting" claim
- `app/eri/type2/validate.py`, `app/eri/type2/submit.py`, `tests/test_eri_type2_validate_submit.py`
  — §12.5's new code and tests
- `API_Testing/local-dsc-signer/` — the working Java reference read (not modified, not
  depended on) to confirm §12.2's signature structure findings
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/API_Prefill_v1.1 (3).pdf`
  — §13's source, and the origin of two of §13.2's spec-vs-reality mismatches
- `Docs/PreFillSchemaJSON_V6.5/PreFillSchemaJSON_V6.5.json` — the official prefill JSON schema;
  §13.3's source of the `scheduleCFL`-type mismatch against live server behavior
- `app/eri/type2/prefill.py`, `tests/test_eri_type2_prefill.py` — §13's fixed code and its tests
- `uat-login-test/get_prefill_goypt2026a.sh` and its saved
  `get_prefill_response_goypt2026a.json` (outside this repo, on the user's machine) — the
  authoritative reference for §13.2 finding #2's real working request shape
- `app/routers/filing.py`, `tests/test_filing_type2_submit.py` — §13.5's `/submit` Type-2 wiring
  and its tests
