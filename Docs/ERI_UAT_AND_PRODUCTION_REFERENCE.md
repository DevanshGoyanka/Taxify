# ERI Type-2 & Type-3 — UAT/Production Reference and Findings (AY 2026-27)

**Date:** 2026-09-03
**Purpose:** one authoritative document for everything ERI-operational — how Type-2 and Type-3
actually get from UAT to production (corrected here from an earlier wrong assumption, with the
real process below), credential architecture, Digest computation, login/session mechanics,
the Type-3 submission automation, acknowledgement retrieval, and every finding from the
filing/submission pipeline audit. Complements, and where the two disagree corrects,
`Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` (original architecture plan) and
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

## 11. References

- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/ERI API Specification_v1.1 (4).pdf`
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/Digest_generation_ERI 2 (2).pdf`
  (the Type-3 onboarding SOP, including the UAT-certification process description)
- `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/API_Everify_Return_v1.1 (1).pdf`
- `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` — original architecture, phase history
- `Docs/ERI_UAT_EXPANSION_PLAN.md` — multi-form UAT-pack rollout plan (§2.3 flags a discrepancy)
- `Docs/ITR1_ITR4_FILING_SUBMISSION_PIPELINE_AUDIT_AY2026_27.md` — the full pipeline audit this
  document's findings were drawn from, with additional detail (e.g. `_personal_info_base`'s
  unreachable PII fallback defaults, the test-isolation fix) not repeated here
