"""
Truly shared ITD JSON helpers — identical across all ITR forms.

Every function in this module produces output that is valid for every
ITR form (ITR-1 through ITR-4).  Form-specific helpers live in itr1.py,
itr4.py, etc.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.engine.common.rounding import vba_round, round_to_nearest_10


# ---------------------------------------------------------------------------
# Rounding helpers
# ---------------------------------------------------------------------------

def _to_rupees(val: Decimal) -> int:
    """Rupee Decimal to integer whole rupees (banker's rounding, VBA-compatible)."""
    return int(vba_round(val))


def _to_rupees_rounded10(val: Decimal) -> int:
    """Rupee Decimal to nearest Rs 10 (Section 288A/288B)."""
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
    """44-character SHA-256 digest for CreationInfo.Digest."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_SW_VERSION = "1.0"
_SW_CODE = "SW00000001"


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

def _tax_return_preparer() -> dict:
    return {
        "IdentificationNoOfTRP": "T000000000",
        "NameOfTRP": "Tax Preparer",
        "ReImbFrmGov": 0,
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
