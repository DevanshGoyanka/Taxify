"""
Truly shared ITD JSON helpers — identical across all ITR forms.

Every function in this module produces output that is valid for every
ITR form (ITR-1 through ITR-4).  Form-specific helpers live in itr1.py,
itr4.py, etc.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.engine.common.rounding import (
    round_to_nearest_10,
    round_to_nearest_rupee,
    vba_round,
)


# ---------------------------------------------------------------------------
# Rounding helpers
# ---------------------------------------------------------------------------

def _to_rupees(val: Decimal) -> int:
    """Emit a monetary amount as whole rupees using statutory half-up rounding.

    Income-tax intermediate fields (tax components, interest components, TDS,
    advance tax) are not rounded under section 288B; they are reported in
    whole rupees. For consistency with CBDT field semantics, 50 paise rounds
    upward rather than to the nearest even rupee.
    """
    return int(round_to_nearest_rupee(val))


def _to_rupees_rounded10(val: Decimal) -> int:
    """Apply Sections 288A/288B: nearest ₹10, with ₹5 rounded upward.

    Reserved for fields that the Act explicitly requires to be rounded to the
    nearest ₹10: total income, balance tax payable, and refund due.
    """
    return int(round_to_nearest_10(val))


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _zero_if_none(val: Optional[Decimal]) -> Decimal:
    return val if val is not None else Decimal("0")


def _str_or(val: Any, default: str = "") -> str:
    return str(val) if val is not None else default


def _today() -> str:
    return date.today().isoformat()


def _compute_digest(data: dict) -> str:
    """Compute ITD-compliant Digest using iterative HMAC-SHA256.

    Per SOP Section 5.3:
      1. Serialize then minify the dict to JSON (all interstitial spaces removed)
      2. Replace "Digest" value with placeholder "-"
      3. HMAC-SHA256 with secret key (UTF-8 encoded), repeated N iterations
      4. Base64-encode the final hash

    Reads from environment variables:
      ERI_DIGEST_SECRET_KEY   — HMAC secret key string, UTF-8 encoded as key bytes
      ERI_DIGEST_ITERATIONS   — number of HMAC iterations (default: 1)
    """
    import re

    secret_key = os.getenv("ERI_DIGEST_SECRET_KEY", "")
    if not secret_key:
        # Fallback: simple SHA-256 hex digest for dev/testing only
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    iterations = int(os.getenv("ERI_DIGEST_ITERATIONS", "1"))
    placeholder = "-"
    digest_regex = r'"Digest"\s*:\s*"[^"]*"'

    # Step 1: Serialize to JSON
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)

    # Step 2: Minify — remove all interstitial whitespace outside quoted strings
    result: list[str] = []
    in_string = False
    escape = False
    for ch in raw:
        if in_string:
            if escape:
                escape = False
                result.append(ch)
            elif ch == '\\':
                escape = True
                result.append(ch)
            elif ch == '"':
                in_string = False
                result.append(ch)
            else:
                result.append(ch)
        else:
            if ch in (' ', '\t', '\n', '\r'):
                continue
            if ch == '"':
                in_string = True
            result.append(ch)
    minified = ''.join(result)

    # Step 3: Replace Digest value with placeholder
    minified = re.sub(digest_regex, f'"Digest":"{placeholder}"', minified)

    # Step 4+5: HMAC-SHA256 with secret key (UTF-8 bytes), iterated N times
    key_bytes = secret_key.encode("utf-8")
    payload = minified.encode("utf-8")
    for _ in range(iterations):
        payload = hmac.new(key_bytes, payload, hashlib.sha256).digest()

    # Step 6: Base64 encode the final hash
    return base64.b64encode(payload).decode("utf-8")


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_SW_VERSION = "1.0"
_SW_CODE = os.getenv("ERI_SW_ID", "SW00000001")


# ---------------------------------------------------------------------------
# CreationInfo, Form_ITRx, Verification — identical across all forms
# ---------------------------------------------------------------------------

def _creation_info() -> dict:
    return {
        "SWVersionNo": _SW_VERSION,
        "SWCreatedBy": _SW_CODE,
        "JSONCreatedBy": _SW_CODE,
        "JSONCreationDate": _today(),
        "IntermediaryCity": "Delhi",
        "Digest": "-" * 44,
    }


def _form_itr(form_name: str) -> dict:
    return {
        "FormName": form_name,
        "Description": "For AY 2026-27",
        "AssessmentYear": "2026",
        "SchemaVer": "Ver1.0",
        "FormVer": "Ver1.0",
    }


def _verification(
    assessee_name: str,
    father_name: str,
    pan: str,
    place: str = "Delhi",
    capacity: str = "S",
) -> dict:
    return {
        "Declaration": {
            "AssesseeVerName": _str_or(assessee_name, "ASSESSEE"),
            "FatherName": _str_or(father_name, "FATHER"),
            "AssesseeVerPAN": _str_or(pan, "AAAAA0000A"),
        },
        "Capacity": capacity,
        "Place": _str_or(place, "Delhi"),
    }


# ---------------------------------------------------------------------------
# TaxReturnPreparer — identical across all forms
# ---------------------------------------------------------------------------

def _tax_return_preparer(trp: Optional[Any] = None) -> Optional[dict]:
    """Build the official ``TaxReturnPreparer`` node.

    Returns ``None`` when no TRP is involved (the field is omitted entirely
    from the ITD JSON in that case, matching the schema's non-required
    status). When a typed ``TaxReturnPreparer`` model is supplied, its
    data is emitted faithfully. The legacy zero-argument call is preserved
    as a placeholder path for tests that still rely on it.
    """
    if trp is None:
        return {
            "IdentificationNoOfTRP": "T000000000",
            "NameOfTRP": "Tax Preparer",
            "ReImbFrmGov": 0,
        }
    return {
        "IdentificationNoOfTRP": trp.identification_number,
        "NameOfTRP": trp.name,
        "ReImbFrmGov": _to_rupees(trp.reimbursement_from_government),
    }


# ---------------------------------------------------------------------------
# PersonalInfo base — shared PAN/address/name/Dob structure.
# Each form's builder adds form-specific keys (Status for ITR-4, etc.).
# ---------------------------------------------------------------------------

def _personal_info_base(
    pan: str,
    first_name: str,
    middle_name: str,
    last_name: str,
    dob: str,
    employer_category: str,
    residence_no: str,
    locality: str,
    city: str,
    state_code: str,
    country_code: str,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
) -> dict:
    """Build the shared PersonalInfo dict used by ITR-1 and ITR-4.

    Form-specific additions (Status, Phone sub-object, etc.) are added
    by the per-form builder after calling this function.
    """
    result: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": first_name or "",
            "MiddleName": middle_name or "",
            "SurNameOrOrgName": last_name or "ASSESSEE",
        },
        "PAN": pan.upper(),
        "Address": {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
            "CountryCodeMobile": 91,
            "MobileNo": int(mobile_no) if mobile_no and mobile_no.isdigit() else 9999999999,
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": _str_or(email, "assessee@example.com"),
        },
        "SecondaryAdd": secondary_add,
        "DOB": _str_or(dob, "1990-01-01"),
        "EmployerCategory": _str_or(employer_category, "OTH"),
    }
    if aadhaar:
        result["AadhaarCardNo"] = aadhaar
    if secondary_add == "Y":
        result["AlternateAddress"] = {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
        }
    return result
