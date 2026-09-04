"""
Phase 5F — shared personal-profile normalizer tests.

Exercises app/engine/personal_profile.py's normalizers, projections, and
source-hash function directly, against hand-built ReturnDraft fixtures.
Mirrors tests/test_itr1_filing_gateway_profile_v2.py's fixture-building
pattern.

Run: pytest tests/test_personal_profile.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.personal_profile import (
    PersonalProfileError,
    normalize_bank_accounts,
    normalize_personal_profile,
    normalize_property_details,
    normalize_tax_return_preparer,
    personal_profile_source_hash,
    profile_hash_payload,
    project_bank_account_itr1,
    project_bank_account_itr4,
    validate_bank_accounts_strict,
)
from app.schemas.return_draft import (
    BankAccount,
    CoOwner,
    Employer,
    HouseProperty,
    Presumptive44AD,
    TaxReturnPreparer as DraftTaxReturnPreparer,
    create_empty_draft,
)


def _base_draft():
    draft = create_empty_draft("2026-27", "ITR-1", "old")
    p = draft.personal
    p.pan = "abcde1234f"
    p.firstName = "Asha"
    p.middleName = "Rani"
    p.surnameOrOrgName = "Sharma"
    p.name = "Asha Rani Sharma"
    p.dateOfBirth = "1990-01-15"
    p.aadhaar = "123456789012"
    p.fatherName = "Ramesh Sharma"
    p.employerCategory = "OTH"
    p.flatNo = "12A"
    p.roadOrStreet = "MG Road"
    p.localityOrArea = "Central Colony"
    p.city = "Delhi"
    p.stateCode = "07"
    p.countryCode = "91"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "asha.sharma@example.com"
    draft.filing.filingSection = "139(1)"
    draft.verification.capacity = "SELF"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="State Bank of India",
        accountNumber="1234567890", ifscCode="SBIN0001234",
        accountType="SB", useForRefund=True,
    )]
    return draft


def test_normalize_personal_profile_uses_draft_identity():
    draft = _base_draft()
    profile = normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert profile.pan == "ABCDE1234F"
    assert profile.surname == "Sharma"
    assert profile.primary_address.city_or_town_or_district == "Delhi"
    assert profile.verification_place == "Delhi"
    assert profile.return_file_section == 11
    assert profile.regime_is_old is True


def test_normalize_personal_profile_requires_dob():
    draft = _base_draft()
    draft.personal.dateOfBirth = ""
    with pytest.raises(PersonalProfileError) as caught:
        normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert "filing profile is incomplete" in caught.value.message.lower()


def test_normalize_personal_profile_rejects_bad_dob_format():
    draft = _base_draft()
    draft.personal.dateOfBirth = "15-01-1990"
    with pytest.raises(PersonalProfileError) as caught:
        normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert "YYYY-MM-DD" in " ".join(caught.value.errors)


def test_normalize_personal_profile_requires_declaration_accepted():
    draft = _base_draft()
    draft.verification.declarationAccepted = False
    with pytest.raises(PersonalProfileError) as caught:
        normalize_personal_profile(draft, form_error_prefix="ITR-4")
    assert caught.value.message == "Verification declaration must be accepted for official ITR-4 JSON."


def test_normalize_personal_profile_requires_representative_when_capacity_representative():
    draft = _base_draft()
    draft.verification.capacity = "REPRESENTATIVE"
    with pytest.raises(PersonalProfileError) as caught:
        normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert "representative details are incomplete" in caught.value.message.lower()


def test_normalize_personal_profile_alternate_address_required_when_flagged():
    draft = _base_draft()
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = None
    with pytest.raises(PersonalProfileError) as caught:
        normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert "alternateAddress is required" in " ".join(caught.value.errors)


def test_normalize_personal_profile_rejects_unsupported_filing_section():
    draft = _base_draft()
    draft.filing.filingSection = "999"
    with pytest.raises(PersonalProfileError):
        normalize_personal_profile(draft, form_error_prefix="ITR-1")


def test_normalize_personal_profile_maps_92cd_to_code_19():
    """Section 92CD (modified return) maps to CBDT ReturnFileSec code 19.

    Regression test for audit finding §4.5: the frontend's filing-section
    dropdown omitted 92CD entirely, and FILING_SECTION_CODES had no entry
    for it either -- ITR2FilingProfile.return_file_section's own
    MODIFIED_92CD = 19 enum member was unreachable from any draft.
    """
    draft = _base_draft()
    draft.filing.filingSection = "92CD"
    profile = normalize_personal_profile(draft, form_error_prefix="ITR-2")
    assert profile.return_file_section == 19


# ── Bank accounts ────────────────────────────────────────────────────────

def test_bank_account_projections_derive_from_the_same_normalized_row():
    draft = _base_draft()
    normalized = normalize_bank_accounts(draft.bankAccounts)
    assert len(normalized) == 1
    itr1_fields = project_bank_account_itr1(normalized[0])
    assert itr1_fields["account_number"] == "1234567890"
    assert itr1_fields["ifsc_code"] == "SBIN0001234"
    assert itr1_fields["bank_name"] == "State Bank of India"
    assert itr1_fields["account_type"] == "savings"
    assert itr1_fields["is_primary"] is True

    errors, cleaned = validate_bank_accounts_strict(normalized, error_prefix="bankAccounts")
    assert not errors
    itr4_fields = project_bank_account_itr4(cleaned[0])
    assert itr4_fields["account_number"] == "1234567890"
    assert itr4_fields["ifsc_code"] == "SBIN0001234"
    assert itr4_fields["bank_name"] == "State Bank of India"
    assert itr4_fields["is_primary"] is True


def test_bank_account_projection_is_raw_unstripped_for_itr1():
    """ITR-1's historical mapping does no cleaning — preserved exactly."""
    draft = _base_draft()
    draft.bankAccounts[0].bankName = "  State Bank of India  "
    normalized = normalize_bank_accounts(draft.bankAccounts)
    itr1_fields = project_bank_account_itr1(normalized[0])
    assert itr1_fields["bank_name"] == "  State Bank of India  "


def test_validate_bank_accounts_strict_rejects_malformed_rows():
    draft = _base_draft()
    draft.bankAccounts[0].bankName = ""
    draft.bankAccounts[0].accountNumber = "INVALID"
    draft.bankAccounts[0].ifscCode = "BAD"
    normalized = normalize_bank_accounts(draft.bankAccounts)
    errors, _cleaned = validate_bank_accounts_strict(normalized, error_prefix="bankAccounts")
    assert any("bankAccounts[0].bankName" in e for e in errors)
    assert any("bankAccounts[0].accountNumber" in e for e in errors)
    assert any("bankAccounts[0].ifscCode" in e for e in errors)


def test_validate_bank_accounts_strict_requires_exactly_one_refund_account():
    draft = _base_draft()
    draft.bankAccounts.append(draft.bankAccounts[0].model_copy(update={"id": "b2"}))
    normalized = normalize_bank_accounts(draft.bankAccounts)
    errors, _cleaned = validate_bank_accounts_strict(normalized, error_prefix="bankAccounts")
    assert any("exactly one account" in e for e in errors)
    assert any("duplicates another bank account" in e for e in errors)


# ── Tax Return Preparer ──────────────────────────────────────────────────

def test_normalize_tax_return_preparer_none_when_unused():
    draft = _base_draft()
    assert normalize_tax_return_preparer(draft) is None


def test_normalize_tax_return_preparer_when_used():
    draft = _base_draft()
    draft.taxReturnPreparer = DraftTaxReturnPreparer(
        used=True, identificationNumber="trp123", name="Prep Name",
        reimbursementFromGovernment=Decimal("500"),
    )
    trp = normalize_tax_return_preparer(draft)
    assert trp is not None
    assert trp.identification_number == "TRP123"
    assert trp.name == "Prep Name"


# ── Property details ─────────────────────────────────────────────────────

def test_normalize_property_details_empty_when_no_rows():
    draft = _base_draft()
    assert normalize_property_details(draft, form_error_prefix="ITR-1") == []


def test_normalize_property_details_inherits_personal_address_fallbacks():
    draft = _base_draft()
    draft.houseProperties = [HouseProperty(id="hp1", propertyType="SELF_OCCUPIED")]
    rows = normalize_property_details(draft, form_error_prefix="ITR-1")
    assert len(rows) == 1
    assert rows[0].city_or_town_or_district == "Delhi"
    assert rows[0].state_code == "07"


def test_normalize_property_details_co_owners():
    draft = _base_draft()
    draft.houseProperties = [HouseProperty(
        id="hp1", propertyType="SELF_OCCUPIED", isCoOwned=True,
        ownershipShare=Decimal("50"),
        coOwners=[CoOwner(name="Spouse", pan="XYZAB5678C", share=Decimal("50"))],
    )]
    rows = normalize_property_details(draft, form_error_prefix="ITR-1")
    assert len(rows) == 1
    assert rows[0].is_co_owned is True
    assert rows[0].assessee_share_percentage == Decimal("50")
    assert len(rows[0].co_owners) == 1
    assert rows[0].co_owners[0].name == "Spouse"


# ── Source hash ───────────────────────────────────────────────────────────

def test_hash_identical_drafts_produce_identical_hashes():
    draft_a = _base_draft()
    draft_b = _base_draft()
    assert personal_profile_source_hash(draft_a) == personal_profile_source_hash(draft_b)


def test_hash_key_order_independence():
    draft = _base_draft()
    payload = profile_hash_payload(draft)
    reordered = {k: payload[k] for k in reversed(list(payload.keys()))}
    import json, hashlib
    h1 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    h2 = hashlib.sha256(
        json.dumps(reordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert h1 == h2 == personal_profile_source_hash(draft)


def test_hash_changes_when_personal_field_changes():
    draft = _base_draft()
    before = personal_profile_source_hash(draft)
    draft.personal.city = "Mumbai"
    after = personal_profile_source_hash(draft)
    assert before != after


def test_hash_changes_when_bank_account_reordered():
    draft = _base_draft()
    draft.bankAccounts.append(BankAccount(
        id="b2", bankName="HDFC Bank", accountNumber="9998887770",
        ifscCode="HDFC0001111", accountType="CA", useForRefund=False,
    ))
    before = personal_profile_source_hash(draft)
    draft.bankAccounts.reverse()
    after = personal_profile_source_hash(draft)
    assert before != after


def test_hash_unaffected_by_unrelated_schedule_changes():
    from app.schemas.return_draft import Employer
    draft = _base_draft()
    before = personal_profile_source_hash(draft)
    draft.employers = [Employer(id="e1", basic=Decimal("999999"))]
    after = personal_profile_source_hash(draft)
    assert before == after


def test_hash_payload_scoped_to_exactly_five_keys():
    draft = _base_draft()
    payload = profile_hash_payload(draft)
    assert set(payload.keys()) == {
        "personal", "filing", "verification", "bankAccounts", "taxReturnPreparer",
    }


def test_hash_none_and_empty_string_are_not_collapsed():
    draft_a = _base_draft()
    draft_a.personal.aadhaar = ""
    draft_b = _base_draft()
    # aadhaar has no None state on the draft (defaults to ""), but pinCode
    # illustrates the same principle for an Optional-shaped field elsewhere —
    # here we just confirm changing "" to a real value changes the hash,
    # i.e. empty-string is a real, hashed state, not silently ignored.
    draft_b.personal.aadhaar = "999988887777"
    assert personal_profile_source_hash(draft_a) != personal_profile_source_hash(draft_b)


# ── Truncation compatibility (Phase 5F review requirement) ─────────────────
# normalize_personal_profile() itself never truncates — confirm each form's
# adapter reproduces its own pre-existing, unchanged behavior: ITR-4
# truncates to the CBDT schema's length limit (relocated, not new); ITR-1
# has never truncated and still rejects an over-length field.

def test_normalizer_itself_returns_full_untruncated_value():
    draft = _base_draft()
    draft.personal.city = "X" * 80
    profile = normalize_personal_profile(draft, form_error_prefix="ITR-1")
    assert profile.primary_address.city_or_town_or_district == "X" * 80


def test_itr4_adapter_truncates_over_length_city_unchanged():
    from app.engine.filing_gateway_v2 import _itr4_filing_profile

    draft = _base_draft()
    draft.form = "ITR-4"
    draft.personal.city = "X" * 80
    profile = _itr4_filing_profile(draft)
    assert profile.primary_address.city_or_town_or_district == "X" * 50


def test_itr1_adapter_rejects_over_length_city_unchanged():
    from app.engine.filing_gateway_v2 import FilingGatewayV2Error, _filing_profile

    draft = _base_draft()
    draft.personal.city = "X" * 80
    with pytest.raises(FilingGatewayV2Error):
        _filing_profile(draft)


# ── personal_profile_source_hash wired into the pipeline results ───────────

def test_itr1_pipeline_result_carries_matching_source_hash():
    from app.engine.filing_gateway_v2 import compute_canonical_itr1

    draft = _base_draft()
    draft.personal.pan = "ABCDE1234F"  # full compute needs a schema-valid PAN
    draft.employers = [Employer(id="e1", basic=Decimal("600000"))]
    pipeline = compute_canonical_itr1(draft)
    assert pipeline.personal_profile_source_hash == personal_profile_source_hash(draft)
    assert pipeline.personal_profile_source_hash != ""


def test_itr4_pipeline_result_carries_matching_source_hash():
    from app.engine.filing_gateway_v2 import compute_canonical_itr4

    draft = _base_draft()
    draft.personal.pan = "ABCDE1234F"  # full compute needs a schema-valid PAN
    draft.form = "ITR-4"
    draft.businesses = [Presumptive44AD(
        id="b1", natureCode="01001",
        digitalReceipts=Decimal("5000000"), nonDigitalReceipts=Decimal("1000000"),
        declaredIncome=Decimal("600000"),
    )]
    pipeline = compute_canonical_itr4(draft)
    assert pipeline.personal_profile_source_hash == personal_profile_source_hash(draft)
    assert pipeline.personal_profile_source_hash != ""
