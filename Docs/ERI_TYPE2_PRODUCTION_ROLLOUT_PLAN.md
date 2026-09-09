# ERI Type-2 Production Rollout Plan

Status: **Planning only — no code changes made under this plan yet.** Written 2026-09-08 after
verifying UAT status and the current `.env`/code state directly (not assumed from prior docs).

## 1. Current state, verified directly

**UAT — every operation on the requested checklist is genuinely proven live**, against ITD's real
Type-2 UAT sandbox (not just desk-reviewed), for **ITR-1 and ITR-4 only**:

| Operation | UAT status | Evidence |
|---|---|---|
| Login | ✅ Proven | Live, repeated, stable across sessions |
| Add Client | ✅ Proven | Client added and confirmed reachable (a downstream call succeeded that would fail for a non-added PAN) |
| Prefill download | ✅ Proven | 4 real bugs found & fixed against live responses; now correctly decrypts real prefill data |
| Validate | ✅ Proven | A real return iterated from `Digest_Invalid` to `successFlag: true` across 7 live rounds |
| Submit | ✅ Proven | Genuinely **filed** a real return (ARN `116997020040926`), independently confirmed by ITD's own emailed ITR-V |
| Acknowledgement | ✅ Proven | Retrieved live twice, including ITD's own intermittent malformed-response shape |

**Not on the checklist, but relevant**: e-Verification (`generate_evc`/`verify_evc`) has a fixed
payload-shape bug but **has never completed successfully live** — blocked by an ITD-side
test-account state issue (`EF00101`, bank account not EVC-enabled on the UAT profile), still
pending ITD's reply as of the last update. This is the single least-proven step in the whole
lifecycle and is treated specially in Phase 4 below.

**Credential leak** (`Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` and ~17 other tracked files carry a
real, live ERI Type-2 UAT Client ID and related secrets in plaintext, already pushed to
`origin/devansh-dev`): **the user is handling this separately.** This plan does not touch those
files and does not depend on their remediation timeline, but the practice that caused it —
pasting a real credential value into a doc, script, or test file instead of `.env` alone — must
not be repeated for production credentials (Phase 2 below is explicit about this).

**Production credentials: none are currently configured in this environment.** Checked `.env`
directly (presence only, not values): every single `_PRODUCTION`-suffixed ERI field is blank —
`ERI_CLIENT_ID_TYPE2_PRODUCTION`, `ERI_CLIENT_SECRET_TYPE2_PRODUCTION`,
`ERI_DIGEST_SECRET_KEY_TYPE2_PRODUCTION`, `ERI_PASSWORD_TYPE2_PRODUCTION`,
`ERI_SW_ID_TYPE2_PRODUCTION`, `ERI_USER_ID_TYPE2_PRODUCTION` — for both Type-2 and Type-3. The
user has confirmed they hold real ITR-1 Type-2 production credentials separately (earned via an
earlier UAT certification) that simply haven't been added here yet.

**ITR-4 production enablement is a separate, external, unfinished track**: per
`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §12, ITR-4's path to production requires the completed
UAT Test Scenario Sheet to be sent to ITD and their enablement decision awaited — this has not
concluded. ITR-4 production is **not** part of this plan's first rollout for that reason (§8).

**No code-level safety gate distinguishes a production submit from a UAT one today.** Checked
`app/routers/filing.py` and `app/eri/config.py` directly: the only gate is a *form* restriction
(`{"ITR-1", "ITR-4"}` — same set for both UAT and production), enforced identically regardless of
`creds.environment`. The moment `ERI_ENV=production` is set and `assert_credentials_at_startup()`
passes, `_submit_via_type2_api()` will file a **real** return for a matching client with no
additional confirmation step. `assert_credentials_at_startup()` (`app/eri/config.py:270`) only
guards against unsafe *configuration* (mock/ngrok DSC signing, missing digest secret) — it does
not guard against an accidental *use* of a correctly-configured production bundle. Phase 3 below
proposes closing this gap before Phase 4's first real filing.

## 2. Scope

- **In scope for this rollout**: ITR-1 Type-2 production only — the one form with existing
  certification and credentials already earned.
- **Explicitly out of scope, tracked separately**: ITR-4 production (blocked on ITD's own
  enablement decision, §8); ITR-2/ITR-3 Type-2 production (these forms are not production-ready
  by this project's own existing standards — see `Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md`
  and `CLAUDE.md`'s scope boundaries — and were never part of this UAT round at all).
- **Explicitly out of scope, indefinitely**: any unattended or scheduled production filing.
  Every production `submitItr` call should remain a deliberate, attended action with the
  responsible person present for the foreseeable future — this mirrors the discipline
  `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §9 already established for Type-3's first filing of
  each less-common variant, applied here because a real Type-2 production submission is
  equally irreversible and equally consequential for a real taxpayer.

## 3. Phase 0 — Credential leak (user-owned, not part of this plan's execution)

Noted for sequencing only: whatever the user's own remediation timeline is, it should complete
(or at minimum, the rotation half of it) before Phase 1 wires in new production secrets, so the
same repository doesn't end up holding one already-compromised UAT credential and one freshly
exposed production credential side by side. Not a blocking dependency for *planning* the phases
below, but worth finishing before Phase 1 is actually executed.

## 4. Phase 1 — Wire ITR-1 production credentials safely

1. Add the following to `.env` **only** — never to a doc, script, test fixture, or chat message
   (the exact mistake behind the Phase 0 leak): `ERI_CLIENT_ID_TYPE2_PRODUCTION`,
   `ERI_CLIENT_SECRET_TYPE2_PRODUCTION`, `ERI_USER_ID_TYPE2_PRODUCTION`,
   `ERI_PASSWORD_TYPE2_PRODUCTION`, `ERI_SW_ID_TYPE2_PRODUCTION`,
   `ERI_DIGEST_SECRET_KEY_TYPE2_PRODUCTION`, `ERI_DIGEST_ITERATIONS_TYPE2_PRODUCTION`,
   `ERI_BASE_URL_TYPE2_PRODUCTION` (ITD's production gateway URL, distinct from the UAT one).
2. Confirm `.gitignore` actually covers `.env` in this repo (expected, per `CLAUDE.md`'s "never
   commit `.env`" rule) before adding anything to it.
3. Confirm which DSC certificate ITD has on file as the *production* signing certificate for this
   ERI registration. `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §12.1 documents the UAT signing
   certificate as a specific physical USB hardware token (HyperPKI HYP2003) whose private key is
   confirmed non-exportable. Production may use the same token or a separately-registered one —
   this must be confirmed with ITD/the DSC records before Phase 2, not assumed.
4. Leave `ERI_ENV=uat` for now. Nothing in this phase changes which gateway the running app
   actually talks to.

## 5. Phase 2 — Connectivity + signing smoke test (read-only calls only, attended session)

Goal: prove the production credential bundle, DSC signing, and IP whitelisting all work — without
ever coming close to a real filing action.

1. In a single attended session, temporarily set `ERI_ENV=production` and restart the app so
   `assert_credentials_at_startup()` validates the new bundle (forbids mock/ngrok signing,
   confirms the digest secret is present).
2. Call Type-2 `login.py` against the **production** gateway for the real client's PAN. This is
   the first genuine test that the production Client ID/Secret, DSC signature, and whitelisted
   egress IP are all accepted by ITD's live production system — none of this has been exercised
   yet in this environment.
3. If login succeeds, confirm (do not assume) whether this client is already an ITD-registered
   Type-2 client on the **production** side. A PAN being a UAT client does not make it a
   production client — these are separate ITD-side registrations. If not registered, `add_client`
   must be run for production before anything else.
4. Stop here. Do **not** call `validateItr`/`submitItr` in this phase — Phase 2 exists purely to
   prove connectivity and identity before any return-specific call is made.
5. Set `ERI_ENV` back to `uat` at the end of the session. Never leave it blank (this repo has a
   real prior incident of a blanked `.env` value being silently misread — `get_eri_credentials()`
   now fails loudly on a blank `ERI_ENV` for exactly this reason, but there's no reason to rely on
   that fail-safe when simply setting it back to `uat` explicitly is just as easy).

## 6. Phase 3 — Add a real safety gate before any production submit (code change)

This is the one part of this plan that requires a code change, and it should land **before**
Phase 4, not during it. As noted in §1, nothing today stops an accidental real filing once
`ERI_ENV=production` is set — Phase 2's own login smoke test would be running against the same
unguarded path.

Proposed design (for review, not yet implemented):
- Add an explicit, separate arming flag — e.g. `ERI_PRODUCTION_FILING_ARMED=true` — that
  `_submit_via_type2_api()` checks in addition to `creds.environment == "production"` before ever
  calling `submit_itr()`. Absent or not exactly `"true"`, the endpoint should raise a clear,
  actionable error rather than silently no-op or silently proceed.
- This is a second, independent switch from `ERI_ENV`, specifically so Phase 2's connectivity
  testing (which legitimately needs `ERI_ENV=production` for login) can never accidentally reach
  a real submission — the two concerns (which gateway to talk to, and whether real filing is
  currently authorized) become genuinely separable.
- `validateItr` should **not** be gated the same way — it's non-destructive (ITD's own validation
  endpoint, no filing consequence) and gating it would block legitimate pre-filing checks.
- Add a test asserting `_submit_via_type2_api()` refuses to call `submit_itr()` when the arming
  flag is absent, even with valid production credentials and a passing `validateItr` — mirroring
  the existing `tests/test_filing_type2_submit.py` pattern that already asserts a `validateItr`
  rejection stops the flow before `submitItr` is reached.

## 7. Phase 4 — First real production filing (fully attended, single return)

Only after Phases 1–3 are complete:

1. Choose one real client's ITR-1 return, already fully reviewed and validated in UAT-equivalent
   form (i.e., the same JSON that would have been generated and validated cleanly under Type-3 or
   UAT Type-2 for this client).
2. With the responsible person present throughout: login → confirm/complete production
   `add_client` → `validateItr` → arm the Phase 3 gate → `submitItr`. Treat this exactly like
   Type-3's "operator must watch the first filing of each variant" discipline — do not run this
   step and walk away.
3. Immediately follow with e-Verification for this same real client, using their own real
   Aadhaar OTP or bank EVC. **This is the highest-risk step in the entire plan**: the UAT round
   never got to prove `verify_evc`'s success path at all (§1) — only that the payload-shape bug
   was fixed, not that a real verification can complete end-to-end. Have the manual ITD-portal
   e-verification flow ready as an immediate fallback if the API path fails or behaves
   unexpectedly, exactly as a taxpayer would do this manually today.
4. Retrieve the acknowledgement PDF through the app afterward, to confirm the existing
   malformed-response handling (`app/eri/type2/acknowledgement.py`, proven against UAT's
   intermittent Java-serialization-wrapped responses) also holds up against production's real
   traffic pattern.
5. Only once this single filing has completed cleanly end-to-end (submit → verify → acknowledge)
   should a second, then a third, real filing follow — building confidence incrementally rather
   than treating Phase 4 as a one-time gate after which everything is unattended.

## 8. Phase 5 — ITR-4 production (separate, later track)

Blocked on ITD's own enablement decision following the completed UAT Test Scenario Sheet
submission (§1) — this is an external approval this plan cannot accelerate. Once ITD confirms
enablement, repeat Phases 1–4 for ITR-4 specifically: its production credentials may or may not
be the same Client ID/Secret as ITR-1 (confirm with ITD, don't assume), and it needs its own
Phase 4 first-filing dry run — ITR-1 completing cleanly does not prove ITR-4's production path,
since the two forms exercise different JSON-builder code (`app/engine/itd/itr1.py` vs `itr4.py`)
even though they share the same Type-2 transport layer.

## 9. Go/no-go checklist

- [ ] Phase 0: credential leak remediation underway or complete (user-owned)
- [ ] Phase 1: ITR-1 production credentials added to `.env` only; production DSC certificate
      confirmed with ITD
- [ ] Phase 2: production login smoke test passed; client's production registration confirmed
- [ ] Phase 3: arming-flag safety gate implemented and tested
- [ ] Phase 4: first real ITR-1 production filing completed end-to-end (submit → verify →
      acknowledge), attended
- [ ] Phase 5: ITD has confirmed ITR-4 production enablement (separate track, own timeline)

## 10. References

- `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` — the full UAT evidence trail this plan's §1 status
  table summarizes (§10, §12–18)
- `Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md` — original Type-2/Type-3 architecture (also the file
  currently carrying the leaked credential, §1/§3)
- `app/eri/config.py` — credential resolution and `assert_credentials_at_startup()`
- `app/routers/filing.py` — `_submit_via_type2_api()`, the function Phase 3's gate extends
- `SECURITY.md` — credential-handling policy this whole plan is written to comply with
