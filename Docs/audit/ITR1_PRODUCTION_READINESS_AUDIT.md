# Taxify ITR-1 Production-Readiness Audit

**Audit target:** Taxify `main` at commit `0208ebf`

**Assessment year:** AY 2026–27

**Audit scope:** Real-client, end-to-end ITR-1 filing readiness

**Decision:** **NO — Taxify cannot safely or correctly file ITR-1 returns for real clients in production.**

---

## 1. Executive decision

Taxify has a substantial ITR-1 calculation, validation, and official-JSON foundation, including a 339-rule Category-A validation matrix. That work does **not** make the product filing-ready.

The production user journey is currently broken at several independent points:

```text
Add client
→ collect/edit ITR-1 data
→ save/load
→ compute
→ display final computation
→ validate
→ generate official ITD JSON
→ submit through ERI
→ acknowledge/e-verify
```

Confirmed release blockers include:

1. The rich frontend draft is not converted through one complete, typed `ReturnDraft → ITR1Input` adapter.
2. Important entered data can be ignored or dropped, including salary TDS, structured loan deductions, disability/disease deductions, and capital-gain transactions.
3. The production download button returns the saved frontend draft, not official ITD JSON.
4. Official JSON generation hard-fails when home-loan interest under Section 24(b) is present.
5. TDS2/TCS claimed-credit fields default to zero while the calculator credits the full amount.
6. Generated JSON is not validated against the official CBDT JSON schema at runtime.
7. No real submit-return ERI pipeline exists; submission and verification service methods are placeholders.
8. ERI TLS certificate verification is disabled.
9. Sensitive ERI operations lack adequate application authorization, tenant binding, and client ownership enforcement.
10. Real or apparently real taxpayer PII is committed in tracked source/history.
11. Sensitive ERI payloads, tokens, OTP/EVC data, and responses can be printed in plaintext.
12. Production identity, session, storage, audit, deployment, and operational controls are not adequate for real taxpayer data.

Any one of the P0 findings is sufficient for a **NO** decision. Several apply simultaneously.

---

## 2. Scope and method

This audit reviewed the complete real-client filing flow rather than repeating the Category-A validation-rule audit. Four focused passes covered:

- Client onboarding, stable identity, ownership, archive/restore, and save/load behavior.
- Frontend editor fields, canonical return model, compatibility serialization, and backend mappings.
- Tax calculation, schedules, final result, official ITD JSON, artifact lifecycle, ERI submission, acknowledgement, and e-verification.
- Authentication, authorization, TLS, secrets, PII, storage, logging, dependencies, deployment, and operations.

Principal areas reviewed:

- `app/routers/clients.py`, `client_itr.py`, `tax.py`, `itr.py`, `eri.py`, `integration.py`
- `app/schemas/itr1.py`
- `app/engine/calculators/itr1.py`
- `app/engine/schedules/**`
- `app/engine/itd/itr1.py`, `common.py`
- `app/engine/validators/itr1/**`
- `app/eri/**`, `app/services/submission_service.py`
- Authentication, database, cryptography, application configuration, and dependencies
- Frontend return domain, editor, tabs, managers, API clients, calculation services, save/load, validate, and download actions

### Explicit limitation

The 339-rule matrix reports all Category-A rules mapped or reconciled, but this audit does **not** treat that matrix as proof of full tax correctness. Three known exploratory failures remain outside the main suite:

- `test_cbdt_rounding_gap_499995_scenario`
- `test_marginal_relief_precision_gap`
- `test_tds_reconciliation_gap`

No full differential certification against the official ITD utility has been completed. Therefore the final tax computation cannot yet be represented as fully certified, even though the engine contains extensive statutory logic and the main test suite passes.

---

## 3. End-to-end flow assessment

| Stage | Status | Assessment |
|---|---:|---|
| Add client | Partial | Stable public IDs, ownership checks, and archive/restore exist; production RBAC, organization controls, PII protection, and strong field validation do not. |
| Collect/edit all ITR-1 data | Fail | UI captures many fields, but form eligibility and some limits are stale or inconsistent; ITR-1 permits two properties in one UI path; permitted 112A treatment is wrong in frontend selection logic. |
| Save/load exact draft | Partial | Raw JSON persistence is broadly faithful, but save mutates/zeros fields, no-return loading fabricates a draft, and concurrent saves are last-write-wins. |
| Backend computation | Fail | The legacy compatibility mapper omits or misclassifies material frontend data. The calculation engine cannot compensate for missing input. |
| Frontend computation display | Fail | Some component field names do not match backend response names; stale results are not bound to an exact input snapshot. |
| Filing validation | Fail | The client validate path invokes canonical computation but does not run the same full Category-A input/calculation validation pipeline as `/itr1/compute`. |
| Official ITD JSON | Fail | Current filing UI does not use the official endpoint; Section 24(b) fails; TDS/TCS claims can serialize incorrectly; no runtime official-schema gate exists. |
| Persist canonical artifact | Fail | `computed_result` is stored as `{}` and no immutable, hash-addressed official filing artifact is persisted. |
| ERI upload/submission | Fail | No real submit-return implementation or route exists. |
| Acknowledgement/e-verification | Fail | Supporting modules exist but cannot complete an end-to-end filing; placeholder methods, unsafe token handling, missing authorization, and disabled TLS verification remain. |
| Production security/operations | Fail | Critical TLS, authorization, logging, PII, storage, session, auditability, secret-management, and deployment gaps remain. |

---

## 4. P0 release blockers

### P0-1 — No real ERI return-submission pipeline

**Evidence:** `app/services/submission_service.py` explicitly returns `status: "not_implemented"` from `submit_itr()`. Aadhaar OTP and EVC verification methods are placeholders. `app/routers/eri.py` has no canonical submit-return/upload-return route.

**Impact:** Taxify cannot perform the central act required by the product objective: submit an official return and establish a retry-safe filing lifecycle.

**Required remediation:**

- Implement an approved ERI submit-return client using the exact validated official artifact.
- Enforce approved DSC signing; reject mock/ngrok signing in production.
- Persist idempotency key, request ID, artifact hash, submission attempts, state transitions, acknowledgement number, and redacted responses.
- Implement retry-safe transitions through queued, submitting, submitted, acknowledged, and verified states.
- Implement post-submission e-verification and acknowledgement reconciliation.
- Fail production startup when UAT/mock ERI URLs or signing modes are configured.

### P0-2 — Section 24(b) official JSON is not implemented

**Evidence:** `app/engine/itd/itr1.py` raises when `home_loan_interest_paid > 0` instead of serializing `Rentdetails.Section24B`. The frontend `homeLoans` data is not mapped into `loan_details_24b_list`.

**Impact:** A common ITR-1 case—salary plus self-occupied property and housing-loan interest—cannot generate filing JSON.

**Required remediation:**

- Map each frontend home-loan row to a typed canonical loan row.
- Include lender type/name, account or reference number, loan date, original amount, outstanding amount, and Section 24(b) interest.
- Emit `Rentdetails.Section24B.Section24BDtls` and `TotalInterestUs24B`.
- Cross-foot schedule rows against computed deductible interest.
- Add official-schema and representative self-occupied/let-out test fixtures.

### P0-3 — TDS2 and TCS official claimed credits can serialize as zero

**Evidence:** `app/routers/tax.py` creates `TDS2Entry(tds_deducted=tax)` and `TCSEntry(tcs_collected=collected)` but does not populate `tds_claimed_this_year` or `tcs_credit_claimed`. Those values default to zero. The calculator nevertheless credits full deducted/collected amounts.

**Impact:** The computed balance/refund can disagree with official `TaxesPaid` and TDS/TCS schedules. The return can be rejected or materially underclaim tax credit.

**Required remediation:**

- Carry explicit claimed amounts from the draft, with safe full-claim defaults only where legally intended.
- Populate financial year and claimed-credit fields in canonical rows.
- Cross-foot schedule totals, `TaxesPaid`, balance payable, and refund.
- Add tests for full, partial, carried-forward, duplicate, and zero claims.

### P0-4 — ERI TLS certificate verification is disabled

**Evidence:** ERI modules including `login.py`, `client.py`, `add_client.py`, `prefill.py`, `everify.py`, and `acknowledgement.py` use `verify=False`.

**Impact:** A network attacker can intercept or alter ERI credentials, PAN/DOB, OTP/EVC, tokens, prefills, acknowledgements, and filing data.

**Required remediation:**

- Remove every `verify=False`.
- Use platform CA validation or an approved ITD CA bundle.
- Enforce certificate and hostname verification.
- Fail startup in production if verification is disabled.
- Add integration tests proving invalid certificates and hostnames are rejected.

### P0-5 — Sensitive ERI routes lack adequate application authorization

**Evidence:** Sensitive client registration, OTP, prefill, e-verification, and acknowledgement operations in `app/routers/eri.py` do not consistently depend on `get_current_user`. Caller-supplied ERI tokens are not bound to an application user, organization, owned client, PAN, or filing permission.

**Impact:** A caller holding an ERI token may act on arbitrary taxpayer identifiers without enforceable tenant or client ownership.

**Required remediation:**

- Authenticate every ERI operation.
- Store ERI sessions server-side and bind each to user, organization, role, client public ID, PAN, scope, and expiry.
- Resolve PAN only from an owned client record.
- Add granular filing permissions and maker-checker controls.
- Require taxpayer consent evidence and step-up authentication for submission and verification.

### P0-6 — Open signup exposes a shared ERI identity

**Evidence:** Public signup exists; no organization/tenant role model or filing permissions exist; ERI identity is globally configured in environment variables.

**Impact:** Any ordinary registered user may be able to invoke the firm's shared ERI integration identity.

**Required remediation:** Disable public production signup or require invitation and administrator approval. Add organizations, memberships, filing roles, disabled/locked states, session revocation, MFA, and explicit ERI permissions.

### P0-7 — Sensitive ERI data is logged in plaintext

**Evidence:** Request envelopes and ERI login response material are printed in `app/eri/envelope.py` and `app/eri/login.py`.

**Impact:** Logs can expose PAN, DOB, mobile/email, OTP, EVC, tokens, signatures, cookies, transaction IDs, and acknowledgement data.

**Required remediation:** Remove direct printing; use structured, allowlisted, redacted logging. Protect and retain logs according to a documented policy and forward security events to monitored immutable storage.

### P0-8 — Taxpayer PII is committed in tracked source/history

**Evidence:** Tracked files reported with apparent taxpayer identities include `debug_pdf_passwords.py`, `test_26as_parser.py`, and `check_schema_compliance.py`, including names, PANs, DOBs, or password derivation inputs.

**Impact:** This is a potential privacy incident, not merely test-data hygiene.

**Required remediation:**

1. Confirm whether the identities are real.
2. Open the incident/privacy process.
3. Remove the data from the working tree and Git history using an approved history-rewrite procedure.
4. Replace it with clearly synthetic identities.
5. Purge accessible caches, CI artifacts, logs, and forks where possible.
6. Rotate any related credentials and assess notification obligations.
7. Add PAN/Aadhaar/DOB/secret scanning to pre-commit and CI.

---

## 5. P1 correctness and filing-workflow findings

### P1-1 — No single complete `ReturnDraft → ITR1Input` adapter

The production UI sends a legacy compatibility payload to `/tax-summary/compute`. The backend manually reconstructs only a subset of `ITR1Input`. Compute, validation, JSON generation, persistence, and submission therefore do not share one authoritative input.

**Required architecture:**

```text
ReturnDraft
→ typed toITR1Input()
→ compute + statutory validation
→ official JSON builder
→ official schema validation
→ immutable artifact persistence
→ submit the exact persisted artifact
```

The frontend draft, backend domain input, and official ITD JSON must remain separate representations, connected by explicit typed adapters.

### P1-2 — Official filing profile, property profile, and bank accounts are not mapped

The UI captures personal, address, filing, property, and bank information, but the compatibility compute path does not build `ITR1FilingProfile`, `PropertyFilingProfile`, or `BankAccount[]`.

Missing or incomplete mappings include PAN/name components, DOB, father name, employer category, address, country codes, contact details, Aadhaar, verification place/capacity, filing section, revised-return references, property address, bank rows, and refund-account selection.

**Impact:** A draft successfully computed through the current route cannot directly generate official JSON.

### P1-3 — Salary-tab TDS is ignored unless duplicated in the TDS tab

`EmployerEntryManager` stores `employerEntries[].tdsDeducted`; `app/routers/tax.py` reads tax credit only from `tdsEntries`.

**Impact:** Entered employer TDS can disappear, producing an incorrect payable/refund.

**Fix:** Normalize salary TDS into canonical Section 192 `TDS1Entry` rows, with deterministic deduplication if both UI sources contain the same Form 16 credit.

### P1-4 — Structured 80E/80EE/80EEA/80EEB data is ignored

The frontend stores detailed rows under `deductionLoans`, but the compatibility mapper does not populate deduction amounts or official loan schedules.

**Impact:** Entered claims disappear from calculation and JSON.

**Fix:** Map structured rows into aggregate deduction values and the typed schedule lists required by official JSON, then cross-foot them.

### P1-5 — 80DD, 80DDB, and 80U data is ignored

The UI captures disability and specified-disease details, but the mapper omits `amount_80dd`, `amount_80ddb`, `details_80ddb`, `amount_80u`, `schedule_80dd`, and `schedule_80u`.

**Impact:** Material deductions entered by the user can be omitted.

### P1-6 — Capital-gain transaction rows are dropped by compute

The capital-gains UI writes `capitalGainTransactions`; save clears legacy scalar fallbacks when transaction rows exist; the backend reads only scalar 112A fields.

**Impact:** Eligible Section 112A gain can become zero in computation and official output.

**Fix:** Add a typed canonical capital-gains adapter. Do not erase fallback values until every consumer uses canonical rows.

### P1-7 — Frontend wrongly treats every capital gain as ITR-2

Backend ITR-1 models permit the statutory Section 112A exception up to the applicable threshold, while frontend form-selection logic rejects all gains.

**Impact:** Eligible ITR-1 filers are incorrectly forced to ITR-2.

**Fix:** Distinguish permitted 112A gain from disqualifying gain types/amounts and use the same backend-authoritative eligibility result in the UI.

### P1-8 — Validate and download actions use legacy client endpoints

The filing page calls `/clients/{clientId}/itr/{year}/validate` and `/download`. The latter returns stored `form_data`, not official ITD JSON. The official endpoint is `/itr1/compute-json`, but the filing UI does not use it.

**Impact:** A file labeled and downloaded as an ITR JSON is not filing-grade.

**Fix:** Rename the existing endpoint/artifact as a draft export. Generate official JSON only through the canonical compute/validate/build/schema-validate pipeline.

### P1-9 — Official JSON is not validated against the official CBDT schema at runtime

`/itr1/compute-json` serializes builder output without running the official AY 2026–27 JSON schema.

**Impact:** Missing required fields, invalid enums, accidental additional properties, or builder regressions may be detected only by ITD after attempted submission.

**Fix:** Package a versioned, checksum-verified official schema artifact and validate every output before persistence/download/submission. Treat schema failure as an internal release-blocking error, not a taxpayer validation error.

### P1-10 — Official artifact lifecycle is absent

`ClientITR.computed_result` is saved as `{}`. No immutable generated artifact, schema version, input revision, calculation revision, hash, validation record, signature, or submission binding is stored.

**Impact:** The system cannot prove that the reviewed/downloaded/submitted bytes are identical.

**Fix:** Persist immutable artifacts with SHA-256, schema/calculator versions, source draft revision, creation actor/time, validation outcome, and lifecycle state. Submit only by artifact ID and verify the hash before transmission.

### P1-11 — Client validate path does not execute the complete canonical validator pipeline

`validate_client_itr` invokes the compatibility compute route. That route runs computation and internal gates but not the same formal Category-A input and calculation validators used by `/itr1/compute`.

**Impact:** The UI may report valid while the official pipeline rejects the same return.

**Fix:** Extract a shared application service used by all compute, validate, JSON, and submission endpoints.

### P1-12 — House-property count and annual-value mappings are inconsistent

The frontend permits two ITR-1 properties in one component, while backend ITR-1 supports at most one and maps only the first. The router passes municipal/fair-rent values that are absent from the canonical schema, causing them to be dropped; standard rent is incomplete.

**Impact:** A second property may be ignored, and let-out annual value may be understated or computed from incomplete inputs.

**Fix:** Enforce one property for ITR-1 at the editor boundary; route more than one to ITR-2. Add municipal value, fair rent, and standard rent to the canonical schema and test statutory GAV logic.

### P1-13 — AY/FY values remain hardcoded

Hardcoded AY/FY logic exists in frontend age calculation, TDS defaults, salary and house-property services, 26AS import, and the backend client-validation path.

**Impact:** Age, financial year, interest, defaults, and validation can be wrong when the selected assessment year changes.

**Fix:** Centralize AY/FY/date derivation and require the selected AY through every adapter and service.

### P1-14 — Displayed computation is not cryptographically or logically tied to the current draft

Request-generation rejection exists, but the UI does not bind the result to a stable fingerprint of the exact draft, regime, and AY. Existing revision-aware domain state is not used by the page.

**Impact:** A result for a superseded draft can be displayed or acted upon.

**Fix:** Hash a canonicalized input snapshot and retain that hash with the compute result. Disable validation, download, and submission when the current snapshot hash differs.

### P1-15 — Save mutates the editor snapshot

Before persistence, save normalizes and clears compatibility fields instead of storing the exact editor representation.

**Impact:** Data can be lost across save/reload, especially while backend consumers still depend on legacy fields.

**Fix:** Persist the exact editor draft separately from derived compute input and generated artifacts.

---

## 6. P1 security and operational findings

### P1-16 — Sensitive taxpayer data is stored in plaintext SQLite

PAN, Aadhaar, DOB, contact information, bank/return content, and computed results are stored in a local SQLite database without production-grade access controls, encryption strategy, backups, HA, or point-in-time recovery.

**Fix:** Use managed PostgreSQL with TLS, encrypted disks/backups, least-privilege identities, migrations, monitoring, and PITR. Apply KMS/HSM-backed field-level protection or tokenization to high-risk fields, with versioned keys and controlled lookup tokens.

### P1-17 — Long-lived JWTs are stored in browser `localStorage`

Access tokens are valid for approximately 24 hours and persisted in `localStorage`, with no refresh rotation, server-side revocation, `jti`, issuer/audience validation, MFA, or sensitive-operation reauthentication.

**Fix:** Use short-lived in-memory access tokens and rotating refresh sessions in `HttpOnly`, `Secure`, `SameSite=Strict` cookies, with server-side revocation and step-up authentication.

### P1-18 — Production secrets rely on workstation `.env`

ERI credentials/configuration, JWT material, and a shared portal-encryption key are stored in a local `.env`. It is ignored by Git but is not an acceptable production secret lifecycle.

**Fix:** Move secrets to an approved secret manager/KMS, use workload identity, separate UAT and production identities, rotate existing values before use, and remove insecure fallbacks.

### P1-19 — No security-grade audit trail

There is no append-only audit model for PII views/exports, return edits, ERI actions, consent, OTP/EVC, signing, submission, acknowledgement, or administration.

**Fix:** Record actor, tenant, client/resource, purpose, action, outcome, time, source/session, correlation ID, artifact hash, and redacted metadata. Forward to restricted immutable/WORM-capable storage and SIEM.

### P1-20 — Authentication lacks abuse controls

Login/signup lack rate limiting, strong password controls, MFA, lock/delay policy, verification, and disabled-user/session checks.

**Fix:** Add per-account and per-IP controls, breached-password screening, minimum/maximum length, account approval, MFA, failed-login audit events, and revocation-aware user status.

### P1-21 — Dependencies are not reproducibly pinned

Python dependencies use broad or absent version constraints and no hash-locked production file.

**Fix:** Generate reviewed exact-version, hash-locked runtime/dev dependency sets; run SCA, license scanning, SBOM generation, and controlled updates in CI.

---

## 7. P2 and lower-priority discrepancies

These items do not change the binary verdict but should be resolved before certification:

- No-return loading returns identity fields as if they were a saved return, allowing a fabricated empty draft to be persisted.
- ITR type is inferred from legacy scalar business fields the canonical serializer may not emit, risking ITR-4 misclassification.
- Integer database IDs remain accepted alongside public UUIDs; ownership is enforced, but production routes should use only opaque public IDs.
- Client email, mobile, Aadhaar, and DOB validation is insufficient at persistence boundaries.
- Client return saves have no optimistic concurrency control; multiple tabs can silently overwrite each other.
- Search does not escape SQL LIKE wildcards; SQLAlchemy parameterizes the query, so this is a search-correctness issue rather than SQL injection.
- Portal-password AES-GCM lacks record-bound associated data, key versioning, and a rotation lifecycle.
- CORS includes development origins and broad methods/headers; production must use exact HTTPS origins and a minimal allowlist.
- Raw upstream ERI errors can be reflected to clients instead of mapped to safe public error codes.
- File imports lack strict size/content/resource controls and may fall back to mock data after parser failure.
- Salary-manager and backend result field names differ, so backend-authoritative salary details can be hidden.
- Other-source detailed display fields do not match the tax-summary response.
- Interest on income-tax refund is not mapped to its canonical other-source field.
- 26AS bank-interest import uses a legacy field alias rather than the current canonical field.
- Filing due date and deducted/collected year values include hardcoded builder behavior that must be reconciled with official schema and filing section.
- Legacy official-builder fallbacks can fabricate placeholder contact/address data; production paths must reject missing identity data.
- No production Dockerfile, orchestration/IaC, reverse-proxy TLS configuration, migration framework, backup policy, security CI workflow, or operational runbook was found.

---

## 8. Frontend-to-backend mapping status

| Frontend area | Canonical/backend status | Filing impact |
|---|---|---|
| Personal identity/address | Captured, not fully mapped to `ITR1FilingProfile` | Official JSON blocked/incomplete |
| Filing section/revised return | Captured, incomplete canonical mapping | Wrong/missing filing metadata |
| Bank accounts/refund account | Captured, not mapped to canonical bank rows | Official JSON blocked/incomplete |
| Salary | Partially mapped | Employer TDS can be lost |
| House property | First row only; annual-value fields incomplete | Wrong computation; 24(b) JSON fails |
| Home loans | Structured UI exists; no canonical 24(b) serialization path | Official JSON blocked |
| Other sources | Partially mapped | IT-refund interest misclassified; display mismatch |
| Section 112A capital gain | Transaction rows ignored; UI eligibility stale | Gain can be dropped or form misclassified |
| 80C/80D | Broadly mapped, subject to complete pipeline tests | Needs end-to-end cross-foot proof |
| 80E/80EE/80EEA/80EEB | Structured rows ignored | Claims disappear |
| 80DD/80DDB/80U | Captured, canonical mapping missing | Claims disappear |
| Donations/other schedules | Some typed support exists | Must be verified through one canonical adapter |
| TDS1 | TDS tab mapped; salary-tab TDS not normalized | Credit can be lost |
| TDS2/TCS | Deducted/collected mapped; claimed amounts omitted | Official credit may be zero |
| Challans/self-assessment/advance tax | Canonical support not consistently wired from filing UI | Taxes-paid reconciliation risk |
| Verification | Data captured in places; no single authoritative mapping | Official JSON/submission incomplete |

---

## 9. Calculation assessment

### What is strong

The backend includes dedicated schedules and common modules for salary, house property, other sources, deductions, TDS/TCS, slab tax, rebate, surcharge, cess, interest, and rounding. The main backend suite previously passed 435 tests, and the Category-A rule matrix reports 339/339 rules accounted for.

### What remains uncertified

- The three known exploratory failures must be resolved or formally disproved.
- The frontend frequently fails to deliver the intended data to the engine.
- TDS/TCS official serialization conflicts with calculator crediting.
- Full official-utility differential testing is absent.
- Representative golden returns covering every supported schedule combination are absent.
- Final computation UI is not strongly bound to an exact canonical input revision.

**Conclusion:** The engine is a strong foundation, but the product's final tax result is not certifiable end to end until mapping, reconciliation, differential testing, and artifact binding are complete.

---

## 10. Required production architecture

A production filing must use one application service and one immutable artifact chain:

```text
Owned client + exact ReturnDraft revision
    ↓ typed, versioned adapter
ITR1Input
    ↓ input validation
Canonical calculation result
    ↓ calculation validation and cross-foot checks
Official ITD JSON
    ↓ official schema validation
Immutable filing artifact (bytes + SHA-256 + versions)
    ↓ maker-checker approval + taxpayer consent
ERI submission with idempotency key
    ↓
Acknowledgement reconciliation
    ↓
E-verification and final status
```

Required invariants:

1. The same `ITR1Input` drives compute, validation, JSON, and submission.
2. The frontend never performs authoritative statutory calculation.
3. The builder serializes computed values and does not independently decide eligibility.
4. Downloaded, approved, signed, and submitted bytes have the same artifact hash.
5. A stale draft invalidates prior calculation/validation/approval.
6. Every transition is authorization-checked, audited, retry-safe, and tenant-bound.
7. Production cannot start with mock/UAT endpoints, disabled TLS, development secrets, or missing schema artifacts.

---

## 11. Minimum release gates

Taxify should not process real-client data or submit a return until all gates below pass.

### Filing correctness

- [ ] One complete typed `ReturnDraft → ITR1Input` adapter exists.
- [ ] Every ITR-1 editor field has a documented and tested canonical destination.
- [ ] Salary TDS, TDS2, TCS, challans, loans, disability/disease schedules, bank accounts, profiles, and capital gains round-trip without loss.
- [ ] Section 24(b) official serialization is implemented and schema-valid.
- [ ] Compute, validate, JSON, download, and submit use the same canonical service.
- [ ] The complete Category-A validator pipeline runs before artifact generation.
- [ ] Official JSON passes the packaged official schema at runtime.
- [ ] TaxesPaid, TDS/TCS/challans, balance payable, and refund cross-foot.
- [ ] Known exploratory calculation failures are closed.
- [ ] A differential golden-return suite agrees with the official ITD utility for all supported scenarios.

### Artifact and ERI lifecycle

- [ ] Exact editor revisions and immutable official artifacts are stored separately.
- [ ] Artifact hashes bind review, approval, signature, submission, and acknowledgement.
- [ ] ERI submit-return is implemented, certified, idempotent, and retry-safe.
- [ ] Acknowledgement and e-verification complete end to end.
- [ ] Maker-checker approval and explicit taxpayer consent exist.
- [ ] Production rejects UAT/mock endpoints and signing modes.

### Security and privacy

- [ ] TLS verification is enabled and tested for every ERI call.
- [ ] Every ERI route requires authentication, tenant/client ownership, and granular permission.
- [ ] Public signup cannot access the shared ERI identity.
- [ ] ERI sessions are server-side, scoped, encrypted, expiring, and revocable.
- [ ] Sensitive logging is removed and redaction tests pass.
- [ ] The potential committed-PII incident is resolved, including history and artifact cleanup.
- [ ] Production database, backups, and sensitive fields are appropriately protected.
- [ ] Secrets are managed and rotated through KMS/secret-manager infrastructure.
- [ ] Short-lived sessions, MFA, step-up auth, rate limits, lockouts, and revocation exist.
- [ ] Append-only security and filing audit events are retained and monitored.
- [ ] Dependencies are hash-locked and scanned; SBOMs are generated.

### Operations

- [ ] Repeatable production deployment and migration processes exist.
- [ ] Backups and point-in-time recovery are tested.
- [ ] Monitoring, alerting, incident response, privacy response, and rollback runbooks exist.
- [ ] Filing retries and partial upstream failures are tested in UAT.
- [ ] Load, concurrency, stale-write, and disaster-recovery tests pass.
- [ ] A formal ERI/CBDT production certification and controlled pilot are complete.

---

## 12. Recommended remediation order

1. **Contain privacy/security exposure:** remove sensitive logging, enable TLS verification, lock down ERI routes and signup, investigate committed PII, and rotate relevant secrets.
2. **Create the canonical adapter/service:** make one full `ITR1Input` path authoritative for compute, validation, JSON, and submission.
3. **Close material mapping defects:** salary TDS, TDS2/TCS claims, profiles, banks, challans, 24(b), loan deductions, disability/disease schedules, and 112A transactions.
4. **Complete official artifact generation:** implement Section 24(b), runtime schema validation, cross-footing, immutable persistence, hashing, and official download.
5. **Resolve calculation-certification gaps:** close exploratory failures and run differential golden returns against the official utility.
6. **Implement ERI submission lifecycle:** production signing, idempotent upload, durable states, acknowledgement, e-verification, and reconciliation.
7. **Productionize identity/data/operations:** organizations and RBAC, secure sessions/MFA, managed database/KMS, audit trail, pinned dependencies, deployment, monitoring, backups, and runbooks.
8. **Run a controlled UAT and security assessment:** complete end-to-end tests with synthetic taxpayers before any tightly controlled pilot.

---

## 13. Final answer

> **Can Taxify file ITR-1 for real clients in production today?**
>
> **NO.**

Taxify can support continued development and synthetic/UAT testing after immediate security containment. It must not be represented as production filing-ready, must not submit real returns, and should not ingest additional real taxpayer data until the P0 security/privacy issues are contained. Production approval requires every minimum release gate in this report to be evidenced by automated tests, operational controls, and an end-to-end ERI certification run.
