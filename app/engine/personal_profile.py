"""Shared canonical personal-profile normalization (Phase 5F).

Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md Phase 5F: one shared place that
parses and validates the taxpayer-level facts every form's official filing
profile needs, instead of ``filing_gateway_v2.py``'s three independent,
subtly-diverging implementations (``_filing_profile``/``_itr4_filing_profile``/
``_itr2_filing_profile`` and their property/bank-account/TRP siblings).

Two conceptually separate groups of types live in this one module. Keep them
separate in your head even though they're co-located for now — Phase 5G and
Phase 8 (ITR-3) will need this boundary to stay clean:

  * ``NormalizedPersonalProfile`` and its sub-types — taxpayer-level, one per
    return: identity, addresses, filing status, verification, representative,
    bank accounts, TRP.
  * ``NormalizedPropertyProfile`` and its sub-types — schedule-level, one per
    house-property row. NOT part of the personal profile.

Per-form differences that are genuinely NOT shared are deliberately NOT
unified here: verification-capacity allow-lists (ITR-1: SELF/REPRESENTATIVE;
ITR-2: SELF/KARTA; ITR-4: all four), account-type enums, assessee-status
sets, ITR-4's Form-10IEA block, ITR-2's residential-status/FII-FPI/
Portuguese-code fields, and each form's own property-row shape (list vs.
single vs. flat, with or without co-owner/tenant nesting) all stay in each
form's adapter in ``filing_gateway_v2.py``. This module handles trimming,
required-field checks, address/date/representative/bank-account/TRP parsing,
and structural relationships common to every form — nothing more.

Address values are returned at full canonical length — this module never
truncates taxpayer data to fit a target CBDT schema's field-length limit.
Where a form's official schema needs truncation (ITR-4 today), that is an
explicit, separately-named step in that form's own adapter, not something
this module does silently.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.return_draft import BankAccount as DraftBankAccount
    from app.schemas.return_draft import ReturnDraft

_ZERO = Decimal("0")

# Filing-section code map (CBDT FilingStatus.ReturnFileSec, min=11 max=20) —
# identical across every form that has been checked (ITR-1/2/4); the section
# a draft declares maps to the same integer everywhere it is accepted.
FILING_SECTION_CODES: dict[str, int] = {
    "139(1)": 11,
    "139(4)": 12,
    "142(1)": 13,
    "148": 14,
    "153C": 16,
    "139(5)": 17,
    "139(9)": 18,
    "119(2)(b)": 20,
}

_BANK_TYPE_MAP: dict[str, str] = {
    "SB": "savings",
    "CA": "current",
    "CC": "cash_credit",
    "OD": "overdraft",
    "NRO": "nro",
    "OTH": "other",
}

_IFSC_PATTERN = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
_ACCOUNT_NUMBER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9/-]*[0-9])?")


class PersonalProfileError(ValueError):
    """Raised by this module's normalizers; always caught and re-wrapped by
    each form's adapter into that form's own ``FilingGatewayV2Error`` (kept
    in ``filing_gateway_v2.py`` — importing it here would be circular, since
    that module imports this one).
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]


def require_field(value: str | None, field: str, *, form_error_prefix: str) -> str:
    """Return stripped required text or raise an actionable error.

    ``field`` may be a bare key (prefixed with ``personal.``) or an
    already-qualified draft path (used as-is) — mirrors the convention the
    ITR-1 gateway already established, applied uniformly here.

    Public (not ``_required``) because it is also the tool a form adapter
    reaches for to enforce required-ness on a field that
    ``normalize_personal_profile`` parses but leaves optional by default —
    ``employer_category`` below is one such field: every form shares the
    same *source* (``personal.employerCategory``), but only ITR-1/ITR-4's
    filing-profile types have a field to receive it, so only their
    adapters may treat it as required.
    """
    cleaned = (value or "").strip()
    if cleaned:
        return cleaned
    path = field if "." in field else f"personal.{field}"
    raise PersonalProfileError(
        f"{form_error_prefix} filing profile is incomplete.",
        [f"{path} is required for official CBDT JSON."],
    )


# ===========================================================================
# NormalizedPersonalProfile — taxpayer-level facts
# ===========================================================================

@dataclass(frozen=True)
class NormalizedAddress:
    residence_no: str
    residence_name: str
    road_or_street: str
    locality_or_area: str
    city_or_town_or_district: str
    state_code: str
    country_code: str
    pin_code: str | None
    zip_code: str
    mobile_country_code: int
    mobile_no: str
    email: str
    secondary_mobile_country_code: int
    secondary_mobile_no: str | None
    secondary_email: str | None


@dataclass(frozen=True)
class NormalizedAlternateAddress:
    residence_no: str
    residence_name: str
    road_or_street: str
    locality_or_area: str
    city_or_town_or_district: str
    state_code: str
    country_code: str
    pin_code: str | None
    zip_code: str


@dataclass(frozen=True)
class NormalizedRepresentative:
    name: str
    email: str
    mobile_country_code: int
    mobile_no: str


@dataclass(frozen=True)
class NormalizedSeventhProviso:
    """Raw parsed primitives — NOT a shared output shape.

    ITR-1's ``SeventhProvisoDetails`` has no deposit fields at all. ITR-4's
    ``ITR4SeventhProvisoDetails`` adds ``deposit_exceeds_one_crore``/
    ``deposit_amount`` on top of the same base fields. ITR-2 collapses all
    four flags into one boolean and drops per-clause detail rows. Each
    adapter decides how much of this superset to use and how to shape its
    own output — this dataclass only carries the raw parsed values.
    """

    deposit_exceeds_one_crore: bool
    deposit_amount: Decimal
    foreign_travel: bool
    foreign_travel_amount: Decimal
    electricity_expenditure: bool
    electricity_expenditure_amount: Decimal
    other_clause_iv: bool
    clause_iv_details: list[tuple[str, Decimal]]


@dataclass(frozen=True)
class NormalizedBankAccount:
    """Raw, unstripped parse of one canonical bank-account row.

    Deliberately does no cleaning (no ``.strip()``/``.upper()``) and no rule
    checking (no "exactly one primary", no IFSC/account-number format
    validation) — see ``validate_bank_accounts_strict`` for the ITR-4-style
    rich rules, and each form's projection function for how raw vs. cleaned
    values are used. This keeps the parse step itself behavior-neutral so
    projecting it into ITR-1's historically raw (unstripped) shape and
    ITR-4's historically cleaned shape are both exact, byte-for-byte
    continuations of what each form already does today.
    """

    account_number: str
    ifsc_code: str
    bank_name: str
    account_type_raw: str  # draft's raw SB/CA/CC/OD/NRO/OTH code
    is_primary: bool


@dataclass(frozen=True)
class NormalizedTaxReturnPreparer:
    identification_number: str
    name: str
    reimbursement_from_government: Decimal


@dataclass(frozen=True)
class NormalizedPersonalProfile:
    pan: str
    first_name: str
    middle_name: str
    surname: str
    date_of_birth: date
    employer_category: str
    aadhaar_number: str | None
    father_name: str
    primary_address: NormalizedAddress
    alternate_address: NormalizedAlternateAddress | None
    verification_place: str
    verification_capacity_raw: str
    representative: NormalizedRepresentative | None
    return_file_section: int
    is_revised: bool
    original_acknowledgement_no: str | None
    original_return_date: date | None
    notice_number: str | None
    notice_date: date | None
    seventh_proviso: NormalizedSeventhProviso
    regime_is_old: bool


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def normalize_personal_profile(
    draft: "ReturnDraft", *, form_error_prefix: str
) -> NormalizedPersonalProfile:
    """Parse and validate the common-core identity/address/filing-section/
    verification/representative fields shared by every form.

    Raises ``PersonalProfileError`` (never ``FilingGatewayV2Error`` directly
    — see that class's docstring) for missing required fields or an
    unparseable date. Does NOT decide whether ``return_file_section`` is
    supported for a given form (all forms checked so far accept the same
    codes, but a future form might not) or whether
    ``verification_capacity_raw`` is an allowed capacity for a given form —
    both stay the caller's decision, since they are real per-form policy,
    not incidental duplication.
    """
    personal = draft.personal
    filing = draft.filing
    verification = draft.verification

    try:
        dob = date.fromisoformat(
            require_field(personal.dateOfBirth, "dateOfBirth", form_error_prefix=form_error_prefix)
        )
    except ValueError as exc:
        if isinstance(exc, PersonalProfileError):
            raise
        raise PersonalProfileError(
            f"{form_error_prefix} filing profile is invalid.",
            ["personal.dateOfBirth must be a valid YYYY-MM-DD date."],
        ) from exc

    return_section = FILING_SECTION_CODES.get(filing.filingSection)
    if return_section is None:
        # "ReturnFileSec" (the CBDT field this maps to) is asserted on by
        # tests/test_itr1_filing_gateway_profile.py::
        # test_flat_mapper_rejects_unsupported_filing_section, which checks
        # this exception's message text directly — keep the phrase present.
        raise PersonalProfileError(
            f"{form_error_prefix} filing profile has an unsupported filing "
            "section (CBDT ReturnFileSec).",
            [
                f"filingSection {filing.filingSection!r} is not a supported "
                "section code. Use one of: " + ", ".join(FILING_SECTION_CODES),
            ],
        )
    is_revised = filing.returnType == "REVISED" or return_section == 17

    if not verification.declarationAccepted:
        raise PersonalProfileError(
            f"Verification declaration must be accepted for official {form_error_prefix} JSON.",
            ["verification.declarationAccepted must be true."],
        )

    secondary_mobile = (personal.secondaryMobile or "").strip() or None
    secondary_email = (personal.secondaryEmail or "").strip() or None
    mobile_cc_raw = (personal.mobileCountryCode or "91").strip() or "91"
    if not mobile_cc_raw.isdigit():
        raise PersonalProfileError(
            f"{form_error_prefix} filing profile is invalid.",
            ["personal.mobileCountryCode must be numeric."],
        )
    secondary_mobile_cc_raw = (personal.secondaryMobileCountryCode or "").strip() or mobile_cc_raw
    secondary_mobile_cc = 0
    if secondary_mobile:
        if not secondary_mobile_cc_raw.isdigit():
            raise PersonalProfileError(
                f"{form_error_prefix} filing profile is invalid.",
                ["personal.secondaryMobileCountryCode must be numeric."],
            )
        secondary_mobile_cc = int(secondary_mobile_cc_raw)

    address = NormalizedAddress(
        residence_no=require_field(personal.flatNo, "flatNo", form_error_prefix=form_error_prefix),
        residence_name=(personal.residenceName or "").strip(),
        road_or_street=(personal.roadOrStreet or "").strip(),
        locality_or_area=require_field(
            personal.localityOrArea, "localityOrArea", form_error_prefix=form_error_prefix
        ),
        city_or_town_or_district=require_field(
            personal.city, "city", form_error_prefix=form_error_prefix
        ),
        state_code=require_field(personal.stateCode, "stateCode", form_error_prefix=form_error_prefix),
        country_code=(personal.countryCode or "91").strip() or "91",
        pin_code=(personal.pinCode or "").strip() or None,
        zip_code=(personal.zipCode or "").strip(),
        mobile_country_code=int(mobile_cc_raw),
        mobile_no=require_field(personal.mobile, "mobile", form_error_prefix=form_error_prefix),
        email=require_field(personal.email, "email", form_error_prefix=form_error_prefix),
        secondary_mobile_country_code=secondary_mobile_cc,
        secondary_mobile_no=secondary_mobile,
        secondary_email=secondary_email,
    )

    alternate_address: NormalizedAlternateAddress | None = None
    if personal.secondaryAddressDifferent:
        alt = personal.alternateAddress
        if alt is None:
            raise PersonalProfileError(
                f"{form_error_prefix} filing profile is incomplete.",
                ["personal.alternateAddress is required when secondaryAddressDifferent is true."],
            )
        alternate_address = NormalizedAlternateAddress(
            residence_no=(alt.residenceNo or "").strip(),
            residence_name=(alt.residenceName or "").strip(),
            road_or_street=(alt.roadOrStreet or "").strip(),
            locality_or_area=(alt.localityOrArea or "").strip(),
            city_or_town_or_district=(alt.cityOrTownOrDistrict or "").strip(),
            state_code=(alt.stateCode or "").strip(),
            country_code=(alt.countryCode or "91").strip() or "91",
            pin_code=(alt.pinCode or "").strip() or None,
            zip_code=(alt.zipCode or "").strip(),
        )

    representative: NormalizedRepresentative | None = None
    if verification.capacity == "REPRESENTATIVE":
        rep = filing.representative
        if rep is None:
            raise PersonalProfileError(
                f"{form_error_prefix} representative details are incomplete.",
                ["filing.representative is required for representative verification."],
            )
        representative = NormalizedRepresentative(
            name=require_field(rep.name, "filing.representative.name", form_error_prefix=form_error_prefix),
            email=require_field(rep.email, "filing.representative.email", form_error_prefix=form_error_prefix),
            mobile_country_code=int(
                require_field(
                    rep.mobileCountryCode,
                    "filing.representative.mobileCountryCode",
                    form_error_prefix=form_error_prefix,
                )
            ),
            mobile_no=require_field(
                rep.mobile, "filing.representative.mobile", form_error_prefix=form_error_prefix
            ),
        )

    seventh = filing.seventhProviso
    seventh_proviso = NormalizedSeventhProviso(
        deposit_exceeds_one_crore=seventh.depositExceedsOneCrore,
        deposit_amount=seventh.depositAmount,
        foreign_travel=seventh.foreignTravel,
        foreign_travel_amount=seventh.foreignTravelAmount,
        electricity_expenditure=seventh.electricityExpenditure,
        electricity_expenditure_amount=seventh.electricityExpenditureAmount,
        other_clause_iv=seventh.otherClauseIV,
        clause_iv_details=[(row.nature, row.amount) for row in seventh.clauseIVDetails],
    )

    surname = (personal.surnameOrOrgName or "").strip() or (personal.name or "").strip()

    return NormalizedPersonalProfile(
        pan=require_field(personal.pan, "pan", form_error_prefix=form_error_prefix).upper(),
        first_name=(personal.firstName or "").strip(),
        middle_name=(personal.middleName or "").strip(),
        surname=require_field(surname, "surnameOrOrgName", form_error_prefix=form_error_prefix),
        date_of_birth=dob,
        # Not required here: ITR-2's filing-profile type has no field to
        # receive this at all, so this module cannot know whether it is
        # required without knowing which form is calling — that decision
        # belongs to the ITR-1/ITR-4 adapters (the only ones with a place to
        # put it), via require_field() on this raw value.
        employer_category=(personal.employerCategory or "").strip(),
        aadhaar_number=(personal.aadhaar or "").strip() or None,
        father_name=require_field(personal.fatherName, "fatherName", form_error_prefix=form_error_prefix),
        primary_address=address,
        alternate_address=alternate_address,
        verification_place=require_field(
            verification.place, "verification.place", form_error_prefix=form_error_prefix
        ),
        verification_capacity_raw=verification.capacity,
        representative=representative,
        return_file_section=return_section,
        is_revised=is_revised,
        original_acknowledgement_no=(filing.originalAcknowledgementNumber or "").strip() or None,
        original_return_date=_to_date(filing.originalFilingDate),
        notice_number=(filing.noticeNumber or "").strip() or None,
        notice_date=_to_date(filing.noticeDate),
        seventh_proviso=seventh_proviso,
        regime_is_old=draft.regime == "old",
    )


# ===========================================================================
# Bank accounts
# ===========================================================================

def normalize_bank_accounts(banks: list["DraftBankAccount"]) -> list[NormalizedBankAccount]:
    """Parse raw bank-account rows only — no rules, no cleaning.

    See ``validate_bank_accounts_strict`` for the ITR-4-style rich checks
    (kept opt-in per form, not applied here) and each form's projection
    function for how these raw values are used.
    """
    return [
        NormalizedBankAccount(
            account_number=b.accountNumber or "",
            ifsc_code=b.ifscCode or "",
            bank_name=b.bankName or "",
            account_type_raw=b.accountType,
            is_primary=b.useForRefund,
        )
        for b in banks
    ]


def project_bank_account_itr1(n: NormalizedBankAccount) -> dict[str, Any]:
    """Field values for ``app.schemas.itr1.BankAccount`` — raw/unstripped,
    exactly matching ``draft_to_itr1_input._map_bank_accounts``'s historical
    behavior (no eager cleaning; downstream validators/builders handle it).
    """
    return {
        "bank_name": n.bank_name or None,
        "account_number": n.account_number or None,
        "ifsc_code": n.ifsc_code or None,
        "account_type": _BANK_TYPE_MAP.get(n.account_type_raw, "savings"),
        "is_primary": n.is_primary,
    }


def project_bank_account_itr4(n: NormalizedBankAccount) -> dict[str, Any]:
    """Field values for ``app.schemas.itr4.ITR4BankAccount`` from an ALREADY
    ``validate_bank_accounts_strict``-cleaned ``NormalizedBankAccount``
    (stripped/upper-cased) — do not call this on raw, unvalidated rows.
    """
    return {
        "account_number": n.account_number,
        "ifsc_code": n.ifsc_code,
        "bank_name": n.bank_name,
        "account_type": n.account_type_raw,
        "is_primary": n.is_primary,
    }


def validate_bank_accounts_strict(
    accounts: list[NormalizedBankAccount], *, error_prefix: str
) -> tuple[list[str], list[NormalizedBankAccount]]:
    """The ITR-4-style rich bank-account rules, extracted verbatim from the
    original ``_itr4_bank_accounts`` (identical message text and
    ``bankAccounts[{index}].*`` prefix format — two existing tests assert on
    this exact wording).

    Returns ``(errors, cleaned)`` — ``cleaned`` holds stripped/upper-cased
    copies of every row (even ones with errors, so index alignment is
    preserved for callers that want it), for use with
    ``project_bank_account_itr4``. Does not raise — the caller decides
    whether/how to surface the errors (ITR-4's gateway raises immediately;
    a future caller could instead fold them into a ``ValidationReport``).
    """
    errors: list[str] = []
    seen_accounts: set[tuple[str, str]] = set()
    refund_count = sum(1 for a in accounts if a.is_primary)
    if refund_count != 1:
        errors.append("bankAccounts must select exactly one account for refund.")

    cleaned: list[NormalizedBankAccount] = []
    for index, a in enumerate(accounts):
        prefix = f"bankAccounts[{index}]"
        account_number = a.account_number.strip()
        ifsc = a.ifsc_code.strip().upper()
        bank_name = a.bank_name.strip()
        if not bank_name:
            errors.append(f"{prefix}.bankName is required.")
        elif len(bank_name) > 125:
            errors.append(f"{prefix}.bankName must not exceed 125 characters.")
        if not _ACCOUNT_NUMBER_PATTERN.fullmatch(account_number) \
                or not any(char in "123456789" for char in account_number):
            errors.append(
                f"{prefix}.accountNumber must be 1-20 valid characters, contain "
                "a non-zero digit, and end in a digit."
            )
        elif len(account_number) > 20:
            errors.append(f"{prefix}.accountNumber must not exceed 20 characters.")
        if not _IFSC_PATTERN.fullmatch(ifsc):
            errors.append(
                f"{prefix}.ifscCode must contain 4 letters, 0, and 6 "
                "alphanumeric characters."
            )
        key = (ifsc, account_number.upper())
        if ifsc and account_number:
            if key in seen_accounts:
                errors.append(f"{prefix} duplicates another bank account.")
            seen_accounts.add(key)
        cleaned.append(NormalizedBankAccount(
            account_number=account_number,
            ifsc_code=ifsc,
            bank_name=bank_name,
            account_type_raw=a.account_type_raw,
            is_primary=a.is_primary,
        ))
    return errors, cleaned


# ===========================================================================
# Tax Return Preparer
# ===========================================================================

def normalize_tax_return_preparer(draft: "ReturnDraft") -> NormalizedTaxReturnPreparer | None:
    """Parse the optional canonical TRP block. ``_itr1_tax_return_preparer``
    and ``_itr4_tax_return_preparer`` are already byte-identical apart from
    output type — this is that one shared implementation. ITR-2 has no TRP
    field on ``ITR2Input`` at all and simply never calls this.
    """
    trp = draft.taxReturnPreparer
    if not trp.used:
        return None
    return NormalizedTaxReturnPreparer(
        identification_number=trp.identificationNumber.strip().upper(),
        name=trp.name.strip(),
        reimbursement_from_government=trp.reimbursementFromGovernment,
    )


# ===========================================================================
# NormalizedPropertyProfile — schedule-level, NOT part of the personal profile
# ===========================================================================

@dataclass(frozen=True)
class NormalizedCoOwner:
    serial_number: int
    name: str
    pan: str | None
    aadhaar: str | None
    share_percentage: Decimal | None


@dataclass(frozen=True)
class NormalizedTenant:
    serial_number: int
    name: str
    pan: str | None
    aadhaar: str | None
    pan_or_tan: str | None


@dataclass(frozen=True)
class NormalizedPropertyProfile:
    address_detail: str
    city_or_town_or_district: str
    state_code: str
    country_code: str
    pin_code: str | None
    zip_code: str | None
    property_owner: str
    property_owner_other: str | None
    is_co_owned: bool
    assessee_share_percentage: Decimal
    co_owners: list[NormalizedCoOwner]
    tenants: list[NormalizedTenant]


def _normalize_one_property(row: Any, personal: Any, *, form_error_prefix: str) -> NormalizedPropertyProfile:
    address = (row.address or row.premisesName or row.name
               or personal.flatNo or personal.residenceName).strip()
    city = (row.city or personal.city).strip()
    state = (row.state or personal.stateCode).strip()
    country = (row.countryCode or personal.countryCode or "91").strip()
    pin = (row.pinCode or personal.pinCode).strip() or None
    zip_code = (row.zipCode or personal.zipCode).strip() or None
    is_co_owned = row.isCoOwned
    co_owners = [
        NormalizedCoOwner(
            serial_number=index,
            name=require_field(
                owner.name, f"property.coOwners[{index}].name", form_error_prefix=form_error_prefix
            ),
            pan=owner.pan.strip().upper() or None,
            aadhaar=owner.aadhaar.strip() or None,
            share_percentage=owner.share,
        )
        for index, owner in enumerate(row.coOwners, start=1)
    ] if is_co_owned else []
    tenants = [
        NormalizedTenant(
            serial_number=index,
            name=require_field(
                tenant.name, f"property.tenantDetails[{index}].name", form_error_prefix=form_error_prefix
            ),
            pan=tenant.pan.strip().upper() or None,
            aadhaar=tenant.aadhaar.strip() or None,
            pan_or_tan=tenant.panOrTan.strip().upper() or None,
        )
        for index, tenant in enumerate(row.tenantDetails, start=1)
    ]
    return NormalizedPropertyProfile(
        # address/city/state are returned as-is (possibly empty) — whether
        # they're *required* is real per-form policy: ITR-1's adapter
        # requires them (raises via _required if empty), ITR-4's tolerates
        # a missing address and returns no property profile at all instead.
        # Baking a raise in here would force one form's policy onto both.
        address_detail=address,
        city_or_town_or_district=city,
        state_code=state,
        country_code=country or "91",
        pin_code=pin,
        zip_code=zip_code,
        property_owner=row.propertyOwnerType,
        property_owner_other=row.propertyOwnerOther.strip() or None,
        is_co_owned=is_co_owned,
        assessee_share_percentage=row.ownershipShare if is_co_owned else Decimal("100"),
        co_owners=co_owners,
        tenants=tenants,
    )


def normalize_property_details(
    draft: "ReturnDraft", *, form_error_prefix: str
) -> list[NormalizedPropertyProfile]:
    """The shared property/co-owner/tenant fallback chain: property row →
    property name → primary address; city/state/country/pin/zip inherited
    from ``draft.personal`` when the row omits them.

    Returns one entry per row in ``draft.houseProperties`` — callers decide
    whether to fall back to a synthetic row when the list is empty (ITR-1/
    ITR-4's historical behavior) or return an empty list (ITR-2's, since its
    ``ITR2Input.validate_cross_schedule_contract`` requires an exact 1:1
    count against ``draft.houseProperties``) — that divergence is real
    per-form policy, not incidental duplication, and stays in each adapter.
    """
    return [
        _normalize_one_property(row, draft.personal, form_error_prefix=form_error_prefix)
        for row in draft.houseProperties
    ]


# ===========================================================================
# Personal-profile source hash
# ===========================================================================

def profile_hash_payload(draft: "ReturnDraft") -> dict[str, object]:
    """The exact, centralized hash input — scoped to personal-profile fields
    only (identity/contact/filing-status/verification/bank-accounts/TRP),
    NOT property schedules (schedule-level per the module docstring's
    ownership boundary; a separate hash for those is Phase 5G's concern if
    it turns out to be needed).
    """
    return {
        "personal": draft.personal.model_dump(mode="json"),
        "filing": draft.filing.model_dump(mode="json"),
        "verification": draft.verification.model_dump(mode="json"),
        "bankAccounts": [b.model_dump(mode="json") for b in draft.bankAccounts],
        "taxReturnPreparer": draft.taxReturnPreparer.model_dump(mode="json"),
    }


def personal_profile_source_hash(draft: "ReturnDraft") -> str:
    """SHA-256 over a canonical (sorted-keys) JSON serialization of exactly
    ``profile_hash_payload``. Not the same as a future "complete prepared
    return" hash (which would additionally cover schedules) — this one is
    deliberately narrow; see the module docstring's ownership boundary.

    Bank-account list order is treated as semantically meaningful (a
    reorder changes the hash) — a deliberate simplicity choice, not a
    data-model requirement.
    """
    payload = json.dumps(
        profile_hash_payload(draft), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
