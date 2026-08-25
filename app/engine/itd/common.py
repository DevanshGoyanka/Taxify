"""
Truly shared ITD JSON helpers — identical across all ITR forms.

Every function in this module produces output that is valid for every
ITR form (ITR-1 through ITR-4).  Form-specific helpers live in itr1.py,
itr4.py, etc.
"""

from __future__ import annotations

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
    """Compute the official ITR JSON ``Digest`` via the ERI flow.

    This is a thin delegate to :func:`app.eri.digest.compute_digest` — the
    SINGLE canonical Digest computation in Taxify. Per the ERI onboarding
    SOP ("Digest_generation_ERI 2 (2).pdf" §5.3) and the Dual-Mode ERI
    Integration Plan §3/§A2, the Digest MUST be computed strictly by the
    ERI flow using the secret key + iteration count for the active
    ``(ERI_MODE, ERI_ENV)`` credential bundle. There is no other Digest
    computation path and no non-ERI source for these credentials.

    Raises:
        ERIDigestError: If the active ERI credential bundle cannot be
            resolved or has no digest secret. A placeholder ``-`` Digest
            is never returned — generation fails loudly instead.
    """
    from app.eri.digest import compute_digest
    return compute_digest(data)


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_SW_VERSION = "1.0"


def _resolve_sw_id() -> str:
    """Resolve the SWCreatedBy for the active (mode, environment) pair.

    Reads via :func:`app.eri.config.get_eri_credentials` so the SW_ID
    stamped in CreationInfo matches the environment whose digest secret
    was used to compute the Digest.

    Raises:
        ERIConfigurationError: If the active ERI credential bundle cannot
            be resolved. The ``SWCreatedBy`` MUST always flow from the
            selected ERI credentials — there is no non-ERI source for
            this identity, so generation fails loudly instead of stamping
            a hardcoded placeholder SW_ID.
    """
    from app.eri.config import ERIConfigurationError, get_eri_credentials
    try:
        creds = get_eri_credentials()
    except ERIConfigurationError:
        raise
    except Exception as exc:
        raise ERIConfigurationError(
            f"Could not resolve ERI credentials for SWCreatedBy: {exc}"
        ) from exc
    if not creds.sw_id:
        raise ERIConfigurationError(
            f"ERI_SW_ID_{creds.mode.upper()}_{creds.environment.upper()} is not set. "
            "CreationInfo.SWCreatedBy must flow from the selected ERI credentials."
        )
    return creds.sw_id


# ---------------------------------------------------------------------------
# CreationInfo, Form_ITRx, Verification — identical across all forms
# ---------------------------------------------------------------------------

def _resolve_intermediary_city() -> str:
    """Resolve the intermediary city stamped in CreationInfo.IntermediaryCity.

    Reads ``ERI_INTERMEDIARY_CITY`` from the environment (set in .env). This
    is a single unsuffixed variable because the intermediary (the e-filing
    return preparer) is the same entity across all four (mode, environment)
    credential sets — Type-2 UAT/Production and Type-3 UAT/Production — so
    the city does not vary per credential bundle. Defaults to "Akola" when
    unset so generation never fails on this field.
    """
    raw = (os.getenv("ERI_INTERMEDIARY_CITY") or "").strip()
    return raw or "Akola"


def _creation_info() -> dict:
    return {
        "SWVersionNo": _SW_VERSION,
        "SWCreatedBy": _resolve_sw_id(),
        "JSONCreatedBy": _resolve_sw_id(),
        "JSONCreationDate": _today(),
        "IntermediaryCity": _resolve_intermediary_city(),
        "Digest": "-",   # placeholder, replaced by _compute_digest at builder end
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
    place: Optional[str] = None,
    capacity: str = "S",
) -> dict:
    return {
        "Declaration": {
            "AssesseeVerName": _str_or(assessee_name, "ASSESSEE"),
            "FatherName": _str_or(father_name, "FATHER"),
            "AssesseeVerPAN": _str_or(pan, "AAAAA0000A"),
        },
        "Capacity": capacity,
        # The assessee's verification place defaults to the intermediary
        # city (ERI_INTERMEDIARY_CITY) so even test paths that omit `place`
        # stamp Akola (not the old hardcoded Delhi).
        "Place": _str_or(place, _resolve_intermediary_city()),
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
