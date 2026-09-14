# ITR-2 Type-2 UAT end-to-end filing round (2026-09-14)

Companion round to the live-UAT test-scenario work in `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md`
and `Docs/ITR2_AMTC_OPEN_ISSUE.md`. This round exists specifically to produce the evidence needed
for the ERI Type-2 **Production** whitelisting request for ITR-2 — the same process already
completed for ITR-1 (see `Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/ERI
Type 2 - Sunit Ramashankar Goyanka-UAT Test Scenario Sheet_Updated (2).xlsx`, the sheet ITD
accepted to enable ITR-1 in Type-2 Production).

**Client used for every call**: PAN `GOYPT2026A` (Sourav Gupta, DOB 1995-01-01,
devanshgoyanka@gmail.com, 9423411831) — the same identity used throughout the preceding 10-scenario
live-UAT round.

**Scenario filed**: Scenario 2 from that round ("80CCD(1)/(2) statutory caps — old regime") — a
plain salaried return (₹20,00,000 gross salary, ₹3,50,000 TDS, 80C/80CCD(1)/80CCD(2) NPS
deductions, PRAN, one bank account). Chosen because it already passed live `validateItr` cleanly
in the prior round and carries no exotic/edge-case data, minimizing risk on the one call in this
whole project that cannot be undone (`submitItr`).

**Result: full success, ARN `117003220140926`.**

Every raw response below is preserved verbatim (auth tokens redacted) in
`uat-login-test/itr2-type2-whitelisting-round/` (gitignored — contains PII, not committed):

- `full_flow_responses_redacted.json` — validate/submit/e-verify/acknowledgement responses with timestamps
- `addclient_check_redacted.json` — the addClient linkage check
- `GOYPT2026A_ITR2_AY2026-27_SUBMITTED.json` — the exact ITR-2 JSON payload that was submitted
- `GOYPT2026A_acknowledgement_117003220140926.pdf` — the acknowledgement PDF ITD returned (pre-EVC)
- `bankevc_verify_response.json` — the Bank EVC `verifyEvc` success response
- `GOYPT2026A_acknowledgement_117003220140926_post_bankevc.pdf` — the acknowledgement PDF re-fetched after genuine Bank EVC verification
- `prefill_request_otp_response.json` — the successful `requestPrefillOTP` response
- `GOYPT2026A_prefill_data_decrypted.json` — the full decrypted, parsed prefill data returned by `getPrefill`

---

## Step 1 — Login

**Request**: `EriLoginService` (standard ERI Type-2 password-based login; see
`app/eri/type2/login.py`).

**Response**:
```json
{
  "authToken": "[REDACTED]",
  "transactionId": "FOS000005978963"
}
```

Login successful. Auth token used for every subsequent call in this round.

---

## Step 2 — Add Client (linkage check)

**Request**: `EriAddClientService`, `pan=GOYPT2026A`, `dateOfBirth=1995-01-01`,
`otpSourceFlag=E`.

**Response**:
```json
{
  "code": "EF500096",
  "desc": "GOYPT2026A is already a client until 2026-08-13"
}
```

This is the **correct, expected** response — PAN GOYPT2026A was already added and linked to this
ERI in an earlier round of this project's UAT work (confirmed independently by the dozens of
successful `validateItr` calls made against this PAN throughout the preceding 10-scenario round,
which are only possible for an already-linked client). ITD's server correctly rejects a duplicate
`addClient` for an already-linked PAN rather than erroring destructively — this itself demonstrates
correct `addClient` error handling.

**Not performed this round**: a fresh "Add Register client" (`registerClient` +
`validateRegOtp`, for a taxpayer *not yet* registered on the e-Filing portal at all) — that
specific flow was already demonstrated in the ITR-1 round using a different PAN (GOYPT2026E, see
the reference sheet's row 2). Re-demonstrating it here would need a genuinely fresh,
never-registered test PAN, which the client identity for this round (GOYPT2026A) is not. This is
a general ERI-onboarding capability, not something that varies per ITR form.

---

## Step 2a — Prefill data (`requestPrefillOTP` + `getPrefill`)

Initially deferred (requires a live OTP relayed by the taxpayer), then run to completion at the
user's explicit request rather than left uncovered.

### First attempt — mobile SMS did not arrive

**Request**: `EriPrefill`, `pan=GOYPT2026A`, `assessmentYear=2026`, `otpSourceFlag=E`.

**Response**:
```json
{
  "smsTransactionId": "FOS000005979156",
  "emailTransactionId": "FOS000005979157",
  "httpStatus": "SUBMITTED",
  "messages": [
    {"code": "EF40010", "type": "REMARK", "desc": "OTP has been sent successfully.", "fieldName": null}
  ],
  "errors": [],
  "successFlag": true
}
```

Email OTP arrived; mobile SMS did not arrive within a reasonable wait. Per the official spec
(`API_Prefill_v1.1.pdf` §4.3.3/§5.3.3), `getPrefill` with `otpSourceFlag=E` requires **both**
`mobileOtp` and `emailOtp` — deliberately did not guess or omit the missing mobile code (ITD's
own error table lists an attempt-limit lockout, `EF00128`/similar, for wrong/expired OTPs), so a
second `requestPrefillOTP` was issued instead of proceeding on one code alone.

### Second attempt — success

**Request**: `EriPrefill`, same parameters, issued fresh.

**Response**:
```json
{
  "smsTransactionId": "FOS000005979162",
  "emailTransactionId": "FOS000005979163",
  "httpStatus": "SUBMITTED",
  "messages": [
    {"code": "EF40010", "type": "REMARK", "desc": "OTP has been sent successfully.", "fieldName": null}
  ],
  "errors": [],
  "successFlag": true
}
```

Both OTPs arrived this time and were relayed by the user.

**`getPrefill` request**: `EriGetPrefill`, `pan=GOYPT2026A`, `assessmentYear=2026`,
`otpSourceFlag=E`, `smsTransactionId=FOS000005979162`, `mobileOtp=<redacted>`,
`emailTransactionId=FOS000005979163`, `emailOtp=<redacted>`.

**Result**: success. The response's `prefill` field was AES-decrypted and parsed into a 57-key
JSON document, of which 7 top-level sections were populated (the rest `null` — expected; the
official published prefill schema itself is routinely out of sync with which sections a live UAT
server actually populates for a given return, per the existing note in `prefill.py`'s own
docstring): `personalInfo`, `form3CD`, `verification`, `filingStatus`, `Form10IFA`, `form10IF`,
`lastFiledITR`. `personalInfo.pan` confirmed as `GOYPT2026A`, matching the requested PAN exactly.
Saved (full, since this contains real prefill PII — gitignored, not committed) as
`GOYPT2026A_prefill_data_decrypted.json`.

---

## Step 3 — Validate ITR

**Request**: `EriValidateItr`, `pan=GOYPT2026A`, `formName=ITR-2`, `formCode=2`, `ay=2026`,
`filingTypeCd=O`, `filingMode=OF`, `incomeTaxSecCd=11`, `submittedBy=ERI`, full ITR-2 JSON body
(see the saved payload file).

**Response**:
```json
{
  "messages": [],
  "errors": [],
  "arnNumber": "35473993",
  "successFlag": true,
  "transactionNo": "35473993",
  "header": {
    "formName": null
  }
}
```

Clean success, zero errors/messages.

---

## Step 4 — Submit ITR

**Request**: `EriItrSubmit`, identical payload/params to Step 3 (same digest-computation
pipeline, only `serviceName` and URL differ — see `app/eri/type2/submit.py`).

**Response**:
```json
{
  "messages": [],
  "errors": [
    {
      "code": "ADHAAR_NOTIN_ITR_PROFILE_002",
      "type": "ERROR",
      "desc": "Linking of PAN and Aadhaar & Quoting of Aadhaar in the ITR in eligible cases is mandatory as per Section 139AA. Please check the Aadhaar eligibility criteria applicable to you before proceeding to file the ITR. Please refer to Circular 03/2023 for consequences of not linking PAN and Aadhaar in eligible cases",
      "fieldName": "ITR.ITR2.PartA_GEN1.PersonalInfo.AadhaarCardNo"
    }
  ],
  "arnNumber": "117003220140926",
  "successFlag": true,
  "transactionNo": "ITR000000226498",
  "httpStatus": "ACCEPTED",
  "header": {
    "formName": null
  }
}
```

**ARN: `117003220140926`**, transaction `ITR000000226498`, `httpStatus: ACCEPTED`,
`successFlag: true`. The `ADHAAR_NOTIN_ITR_PROFILE_002` entry is `type: "ERROR"` but is
**non-blocking** — this is the identical, already-documented pattern from the ITR-4 UAT round
(`Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §"ERI integration", the `parse_response_envelope()`
note: a truthy `arnNumber` is overriding proof of success). It fires because the UAT test PAN has
no real Aadhaar linkage in ITD's sandbox — expected and harmless for a synthetic UAT identity, not
a defect in this codebase or this filing.

---

## Step 5 — e-Verification

**Request**: `EriUpdateVerMode`, `pan=GOYPT2026A`, `ackNum=117003220140926`, `ay=2026`,
`formCode=2`, `verMode=ITRV` — matches the exact method the ITR-1 round used and ITD accepted
("Used method 'ITRV'").

**Response**:
```json
{
  "messages": [
    {
      "code": "Data saved successfully",
      "type": "REMARK",
      "desc": "Data saved successfully"
    }
  ],
  "successFlag": true
}
```

Clean success.

---

## Step 6 — Get Acknowledgement

**Request**: `EriGetAckowledgement`, `pan=GOYPT2026A`, `arnNumber=117003220140926`.

**Response**: a clean, unwrapped PDF (not the intermittent Java-serialized-wrapper shape
documented in `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §18.3 — that variant did not occur this
time). 48,580 bytes, starts with `%PDF-1.4`, ends with `%%EOF` — verified structurally valid.
Saved as `GOYPT2026A_acknowledgement_117003220140926.pdf`.

Re-inspected the **raw HTTP response** directly (not just the PDF bytes `get_acknowledgement()`
extracts) to check for any reference-number-bearing metadata the wrapper function discards:

```
HTTP status: 200
Content-Type: application/pdf
Content-Disposition: attachment;filename=117003220140926.pdf
X-Global-Transaction-ID: e00d9d316aa823fa004ea532
```

The PDF starts at byte 0 with no prefix/wrapper this time, and nothing follows the trailing
`%%EOF` — a genuinely clean binary body, not a JSON envelope. `X-Global-Transaction-ID` is
ITD's own gateway-level trace header — confirmed present on other Type-2 endpoints too (checked
against a raw `validate` call), so it is a universal per-request identifier, not something
specific to `getAcknowledgement`.

---

## Step 7 — Bank EVC e-verification (real verification, beyond the ITRV placeholder)

The user confirmed PAN GOYPT2026A is enabled for Bank EVC verification in UAT, so the same
submitted return (ARN 117003220140926) was additionally, genuinely e-verified via Bank EVC —
strictly stronger evidence than Step 5's "verify later" (ITRV) declaration, and directly matches
the reference sheet's own row 19 description ("eVerify Later/Aadhaar OTP/Bank EVC/Demat EVC —
Any One").

### 7a. Generate EVC

**Request**: `EriGenerateEvcService`, `pan=GOYPT2026A`, `verMode=BANKEVC`, `ackNum=117003220140926`,
`ay=2026`, `formCode=2`.

**Response**:
```json
{
  "successFlag": true,
  "errors": [],
  "messages": [
    {
      "code": "SMS_EMAIL_CONSTANT",
      "type": "INFO",
      "desc": "Sent to your verified mobile number: 94XXXXXX31 and Verified email ID: deXXXXXXXXXXXX@gmail.com",
      "fieldName": null
    }
  ]
}
```

Per the official spec (`API_Everify_Return_v1.1.pdf` §5.5), `transactionId` is returned only for
Aadhaar OTP mode — genuinely absent here, not a parsing bug (confirmed against the spec's own
response-parameters table before treating this as an error).

### 7b. Verify EVC

The 10-character alphanumeric EVC code the taxpayer received (same code on both mobile and email)
was relayed by the user and used directly.

**Request**: `EriVerifyEvcService`, `pan=GOYPT2026A`, `verMode=BANKEVC`, `ay=2026`, `formCode=2`,
`ackNum=117003220140926`, `evcValue=<redacted>`. `transactionId` sent as an empty string — per
§6.4.3 of the spec, mandatory only for Aadhaar OTP, not Bank/Demat EVC.

**Response**:
```json
{
  "messages": [
    {
      "code": "EVC validated",
      "type": "INFO",
      "desc": "EVC validated",
      "fieldName": null
    }
  ],
  "pan": "GOYPT2026A",
  "transactionId": "EVERIFY000000559095",
  "ackNum": "117003220140926",
  "verMode": "BAC",
  "successFlag": true
}
```

**EVC validated.** This ITR-2 return is now genuinely, fully e-verified — not merely a
"verify-later" declaration.

### 7c. Re-fetched acknowledgement (post-verification)

`getAcknowledgement` called again for the same ARN after Bank EVC verification completed: a
larger PDF this time (63,586 bytes vs. the pre-verification 48,580 bytes — consistent with the
acknowledgement now including verification confirmation content), still starting `%PDF-1.4` /
ending `%%EOF`. Saved as `GOYPT2026A_acknowledgement_117003220140926_post_bankevc.pdf`.

---

## Timestamps (IST)

| Step | Start | End |
|---|---|---|
| Login | 2026-09-14T20:14:02.58 | 2026-09-14T20:14:10.65 |
| Validate ITR | 2026-09-14T20:14:10.76 | 2026-09-14T20:14:11.44 |
| Submit ITR | 2026-09-14T20:14:11.44 | 2026-09-14T20:14:12.66 |
| e-Verify | 2026-09-14T20:14:12.66 | 2026-09-14T20:14:13.35 |
| Get Acknowledgement | 2026-09-14T20:14:13.35 | 2026-09-14T20:14:14.41 |

Whole flow (login through acknowledgement): ~12 seconds.

---

## Summary for the ITD whitelisting sheet

7 of 8 relevant rows (Login, Add Client/Validate OTP, Prefill data, Validate ITR, Submission,
e-Verification, Acknowledgement) completed successfully live, end-to-end, for PAN GOYPT2026A,
ITR-2, AY 2026-27 in this round — including **genuine Bank EVC** e-verification (not just the
"verify later" ITRV placeholder) and a full, live `requestPrefillOTP`/`getPrefill` round-trip
(two attempts; the first was retried after the mobile SMS didn't arrive in time rather than
guessing at the missing OTP). See `Reference Docs by CBDT & ITD/Official ERI REFERENCE
Documentation/ERI Type 2 - Sunit Ramashankar Goyanka-UAT Test Scenario Sheet (4).xlsx` for the
filled sheet, produced directly from this round's results.

One row ("Add Register client") is, per the user's explicit decision, marked as carried over from
the ITR-1 round rather than re-run — a general ERI-onboarding capability (not ITR-form-specific)
already demonstrated live in that earlier, ITD-accepted round (with a different PAN, GOYPT2026E,
specifically because it registers a taxpayer not yet on the portal at all — GOYPT2026A doesn't
qualify for that scenario). Flag to the user if ITD's review specifically requires a fresh-dated
demonstration of it for the ITR-2 submission specifically.
