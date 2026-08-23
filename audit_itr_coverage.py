"""End-to-end coverage audit: build a maximally-populated draft, generate the
official CBDT JSON, and report which REQUIRED schema fields are missing or
empty in the output.

This is the ground-truth compliance check: even if a field is "in the
frontend", if the builder never emits it (or emits it empty), the JSON
fails the CBDT schema gate. The schema validator already enforces this
on every generate_cbdt_json call; this script surfaces the gaps BEFORE
validation (so we can see which required fields are blank, not just that
validation failed).

Run: python audit_itr_coverage.py
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.engine.filing_gateway_v2 import generate_cbdt_json, FilingGatewayV2Error
from app.schemas.return_draft import (
    AlternateAddress,
    BankAccount,
    Category80D,
    CoOwner,
    DeductionLoan,
    DividendIncome,
    Donation80G,
    Employer,
    ExemptIncomeEntry,
    Form10IAFiling,
    HomeLoan,
    HouseProperty,
    InterestIncome,
    Investment80C,
    OtherIncomeEntry,
    PensionContribution80CCC,
    Policy80D,
    RepresentativeAssessee,
    Schedule80GGAEntry,
    Schedule80GGCEntry,
    Section80D,
    SeventhProviso,
    SeventhProvisoClause,
    TaxChallan,
    TaxReturnPreparer,
    TcsCredit,
    TenantDetail,
    TdsCredit,
    ReturnDraft,
    create_empty_draft,
)


def _load_required_fields(form: str) -> list[str]:
    """Load the REQUIRED leaf field paths from the extracted inventory CSV."""
    csv_path = Path(f"audit_{form.lower().replace('-', '')}_schema_fields.csv")
    fields: list[str] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["required"] == "Y":
                fields.append(row["path"])
    return fields
    """Load the REQUIRED leaf field paths from the extracted inventory CSV."""
    csv_path = Path(f"audit_{form.lower().replace('-', '')}_schema_fields.csv")
    fields: list[str] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["required"] == "Y":
                fields.append(row["path"])
    return fields


def _get_path(obj: Any, path: str) -> Any:
    """Resolve a dotted schema path, matching any row for ``[]`` segments."""
    parts = path.split(".")

    def resolve(cur: Any, index: int) -> Any:
        if index == len(parts):
            return cur
        part = parts[index]
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        if key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        if not is_array:
            return resolve(cur, index + 1)
        if not isinstance(cur, list):
            return None
        values = [resolve(item, index + 1) for item in cur]
        populated = [value for value in values if not _is_empty(value)]
        return populated[0] if populated else None

    return resolve(obj, 0)


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def _populate_official_filing_addons(draft: ReturnDraft) -> ReturnDraft:
    """Populate the four official-filing addon path groups on a draft.

    Adds the schema paths that are missing in BOTH ITR-1 and ITR-4 when the
    base draft only carries the income/deduction/tax schedules:

    1. ``PersonalInfo.AlternateAddress`` (ResidenceNo, LocalityOrArea,
       CityOrTownOrDistrict, StateCode) — emitted by the gateway only when
       ``personal.secondaryAddressDifferent`` is true and
       ``personal.alternateAddress`` is populated.
    2. ``FilingStatus.clauseiv7provisio139iDtls[]`` + children
       (clauseiv7provisio139iNature, clauseiv7provisio139iAmount) — emitted
       by the ITD builder only when ``filing.seventhProviso.otherClauseIV``
       is true and at least one ``SeventhProvisoClause`` row is present.
       Foreign-travel (>₹2L) and electricity (>₹1L) flags are also turned
       on with amounts above their schema thresholds so the
       AmtSeventhProvisio139ii / AmtSeventhProvisio139iii keys are exercised.
    3. ``FilingStatus.AssesseeRep`` (RepName, RepEmailID,
       CountryCodeRepMobileNo, RepMobileNo) — emitted only when
       ``verification.capacity`` is ``"REPRESENTATIVE"`` and
       ``filing.representative`` is populated. CBDT R294/R410 require a
       secondary address for a representative, so the AlternateAddress
       block from group 1 satisfies that constraint.
    4. ``TaxReturnPreparer`` (IdentificationNoOfTRP, NameOfTRP) — emitted
       only when ``taxReturnPreparer.used`` is true. The TRP identification
       number must match the official pattern ``T[0-9]{9}`` and the
       reimbursement must stay within the 14-digit upper bound.

    Args:
        draft: The canonical draft to augment in place.

    Returns:
        The same draft (mutated) for fluent chaining.
    """
    # ── 1. AlternateAddress ─────────────────────────────────────────────
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="9A",
        residenceName="Heritage Apartments",
        roadOrStreet="Park Avenue",
        localityOrArea="Civil Lines",
        cityOrTownOrDistrict="Gurugram",
        stateCode="06",
        countryCode="91",
        pinCode="122001",
        zipCode="",
    )

    # ── 2. Seventh-proviso clause-(iv) details ──────────────────────────
    # Foreign-travel threshold >₹2L, electricity threshold >₹1L, deposit
    # threshold >₹1Cr. Amounts set above each threshold so the builder
    # emits AmtSeventhProvisio139ii / AmtSeventhProvisio139iii and the
    # clause-iv array together.
    draft.filing.seventhProviso = SeventhProviso(
        depositExceedsOneCrore=True,
        depositAmount=Decimal("15000000"),
        foreignTravel=True,
        foreignTravelAmount=Decimal("250000"),
        electricityExpenditure=True,
        electricityExpenditureAmount=Decimal("125000"),
        otherClauseIV=True,
        clauseIVDetails=[
            SeventhProvisoClause(
                id="sp1", nature="1", amount=Decimal("150000"),
            ),
        ],
    )

    # ── 3. Representative assessee ──────────────────────────────────────
    # Setting capacity to REPRESENTATIVE makes the gateway emit the
    # AssesseeRep block. The representative mobile must be a 10-digit
    # string starting with 1-9 (cast to int by the builder) and the email
    # must differ from the assessee's primary email.
    draft.verification.capacity = "REPRESENTATIVE"
    draft.filing.representative = RepresentativeAssessee(
        name="Vikram Representative",
        email="vikram.rep@example.org",
        mobileCountryCode="91",
        mobile="9123456780",
    )

    # ── 4. Tax Return Preparer ──────────────────────────────────────────
    # The TRP identification number must match the official pattern
    # ``T[0-9]{9}`` (or 6 digits); the reimbursement must stay within the
    # 14-digit upper bound (le=99999999999999). A modest amount is used.
    draft.taxReturnPreparer = TaxReturnPreparer(
        used=True,
        identificationNumber="T123456789",
        name="Example TRP",
        reimbursementFromGovernment=Decimal("5000"),
    )

    return draft


def build_full_itr1_draft(*, loan_variant: str = "80EEA") -> ReturnDraft:
    """A maximally-populated canonical ITR-1 draft (every income head).

    Args:
        loan_variant: ``"80EEA"`` (default) keeps the first-time-home-buyer
            loan under Section 80EEA (loan sanctioned FY2019-20 onward,
            stamp-duty ≤ ₹45L). ``"80EE"`` swaps in a Section 80EE loan
            (loan sanctioned FY2016-17, loan ≤ ₹35L) instead — 80EE and
            80EEA are MUTUALLY EXCLUSIVE (validator ITR1-R123), so the two
            variants cannot coexist in one draft. The ``"80EE"`` variant
            also makes the assessee a senior citizen so the senior 80D
            policy arrays (Sec80DSelfFamSrCtznHIDtls / Sec80DParentsSrCtznHIDtls)
            are exercised; the default variant stays non-senior.

    Returns:
        A maximally-populated ``ReturnDraft`` for ITR-1.
    """
    draft = create_empty_draft("2026-27", "ITR-1", "old")
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Asha"
    p.middleName = "Rani"
    p.surnameOrOrgName = "Sharma"
    p.name = "Asha Rani Sharma"
    # The 80EE variant makes the assessee a senior citizen (age 60-80) so
    # the engine's age-bracket-driven `senior_self` flag is True and the
    # senior 80D policy arrays are populated. The default variant stays 36.
    if loan_variant == "80EE":
        p.dateOfBirth = "1958-01-15"
        p.age = 68
    else:
        p.dateOfBirth = "1990-01-15"
        p.age = 36
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
    draft.verification.declarationAccepted = True
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="State Bank of India", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]
    draft.employers = [Employer(
        id="e1", employerName="Acme Corp", employerTAN="DELX12345A",
        employerAddress="1 Business Park", employerCity="Delhi",
        employerStateCode="07", employerPinCode="110001",
        basic=Decimal("600000"), hra=Decimal("120000"),
        rentPaid=Decimal("180000"), isMetroCity=True,
        natureOfEmployment="PE",
    )]
    # Maximally populated property row, including conditional co-owner,
    # tenant, rent, and Section 24(b) structures.
    # The 80EE variant's home loan is sanctioned in FY 2016-17 (Section 80EE
    # eligibility window) with loan ≤ ₹35L, so the matching 80EE deduction
    # loan (R222: 80EE loan must also appear in 24(b)) can reuse it. The
    # default variant keeps the FY 2020-21 loan for 80EEA.
    home_loan_date = "2016-04-01" if loan_variant == "80EE" else "2020-04-01"
    home_loan_amount = Decimal("3000000")  # ≤ ₹35L → eligible for 80EE
    draft.houseProperties = [HouseProperty(
        id="h1", propertySequenceNo=1, propertyType="LET_OUT",
        address="12A MG Road", city="Delhi", state="07", countryCode="91",
        pinCode="110001", propertyOwnerType="OT",
        propertyOwnerOther="Family trust", ownershipType="JOINT",
        ownershipShare=Decimal("70"), isCoOwned=True,
        isPropertyInJointOwnership=True,
        coOwners=[CoOwner(
            coOwnerSNo=1, name="Co Owner", pan="EFGHI1234J",
            aadhaar="234567890123", share=Decimal("30"),
        )],
        tenantDetails=[TenantDetail(
            tenantSNo=1, name="Example Tenant", pan="JKLMN1234K",
            aadhaar="345678901234", panOrTan="DELA12345B",
        )],
        annualLettingValue=Decimal("300000"),
        unrealizedRent=Decimal("10000"),
        municipalTaxesPaid=Decimal("20000"),
        arrearsOfRent=Decimal("5000"),
        interestOnLoan=Decimal("100000"),
        homeLoans=[HomeLoan(
            lenderType="B", lenderName="Example Bank",
            loanAccountNo="HOME123", dateOfLoan=home_loan_date,
            totalLoanAmount=home_loan_amount,
            loanOutstandingAmount=Decimal("2500000"),
            interestUs24B=Decimal("100000"),
        )],
    )]
    # Other-sources interest + deductions.
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("10000"),
    )]
    draft.otherSources.dividends = [DividendIncome(
        id="d1", section="194", grossAmount=Decimal("15000"),
        q1=Decimal("1000"), q2=Decimal("2000"), q3=Decimal("3000"),
        q4=Decimal("4000"), q5=Decimal("5000"),
    )]
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="os1", nature="OTHER", description="Consulting honorarium",
        amount=Decimal("5000"),
    )]
    # Exempt-income detail row — emits
    # ITR1_IncomeDeductions.ExemptIncAgriOthUs10.ExemptIncAgriOthUs10Dtls[]
    # (Category/SubCategory/Description/OthAmount). The ITR-1 builder's
    # ``_exempt_income_rows`` serializes ``input_data.exempt_income_entries``
    # verbatim; the draft mapper flattens ``exemptIncome.otherExemptIncome``
    # into those entries.
    draft.exemptIncome.otherExemptIncome = [ExemptIncomeEntry(
        id="ei1", category="OTH", subCategory="10(10D)",
        description="Life insurance maturity (exempt)",
        grossAmount=Decimal("15000"),
    )]
    # 80C investments + 80D health insurance (correct canonical shape:
    # Deductions.section80C is list[Investment80C]; section80D is a
    # Section80D object with selfFamily/parents sub-categories).
    draft.deductions.section80C = [Investment80C(
        id="c1", investmentType="PF", amount=Decimal("115000"),
        identificationNo="PF-12345", accountOrPolicyNo="EPF-001",
    )]
    # The 80EE variant sets BOTH senior-citizen flags to "Y" and moves the
    # policies into the senior buckets (selfFamilySenior / parentsSenior)
    # so the builder emits the Sec80DSelfFamSrCtznHIDtls.Sch80DInsDtls[]
    # and Sec80DParentsSrCtznHIDtls.Sch80DInsDtls[] arrays. Senior self
    # cap is ₹50,000 and senior parents cap is ₹50,000 (vs ₹25,000 each
    # for non-seniors), so the aggregate ₹45,000 still fits.
    if loan_variant == "80EE":
        draft.deductions.section80D = Section80D(
            selfSeniorCitizen="Y", parentsSeniorCitizen="Y",
            selfFamilySenior=Category80D(
                policies=[Policy80D(
                    id="d1", policyType="INDIVIDUAL", premiumAmount=Decimal("20000"),
                    insurerName="Star Health", policyNo="SH-001",
                )],
                preventiveCheckup=Decimal("5000"), medicalExpense=Decimal("0"),
            ),
            parentsSenior=Category80D(
                policies=[Policy80D(
                    id="d2", policyType="FAMILY_FLOATER", premiumAmount=Decimal("25000"),
                    insurerName="HDFC Ergo", policyNo="HE-002",
                )],
                preventiveCheckup=Decimal("0"), medicalExpense=Decimal("0"),
            ),
        )
    else:
        draft.deductions.section80D = Section80D(
            selfSeniorCitizen="N", parentsSeniorCitizen="N",
            selfFamily=Category80D(
                policies=[Policy80D(
                    id="d1", policyType="INDIVIDUAL", premiumAmount=Decimal("20000"),
                    insurerName="Star Health", policyNo="SH-001",
                )],
                preventiveCheckup=Decimal("5000"), medicalExpense=Decimal("0"),
            ),
            parents=Category80D(
                policies=[Policy80D(
                    id="d2", policyType="FAMILY_FLOATER", premiumAmount=Decimal("25000"),
                    insurerName="HDFC Ergo", policyNo="HE-002",
                )],
                preventiveCheckup=Decimal("0"), medicalExpense=Decimal("0"),
            ),
        )
    draft.deductions.pensionContribution80CCC = [PensionContribution80CCC(
        id="ccc1", identifierType="PRAN", identifierName="PRAN123456",
        amount=Decimal("10000"),
    )]
    draft.deductions.chapterVIA.section80CCC = Decimal("10000")
    draft.deductions.chapterVIA.section80D = Decimal("45000")
    # Section 80G — exercise ALL four mutually-exclusive donation categories so
    # every Schedule80G.* schema path (Don100Percent, Don50PercentNoApprReqd,
    # Don100PercentApprReqd, Don50PercentApprReqd) is emitted by the builder.
    # Each row uses a unique doneePAN, complete address, and a positive
    # non-cash amount. The engine's eligibility rule (see
    # app/engine/schedules/deductions/section_80g.py) computes:
    #   100_without_limit (Don100Percent)          : amount * 1.0  = 5000
    #   50_without_limit  (Don50PercentNoApprReqd): amount * 0.5  = 2500
    #   100_with_limit    (Don100PercentApprReqd) : min(amount,10% GTI)*1.0 = 5000
    #   50_with_limit     (Don50PercentApprReqd)  : min(rem,10% GTI)*0.5 = 2500
    # statutory_eligible = 5000+2500+5000+2500 = 15000. The 10%-of-GTI ceiling
    # (~Rs 60,000+ on this draft's GTI) does not bind for the two limited
    # categories because their combined base (Rs 10,000) is well under the cap.
    # allowed_deduction = min(user_claim, statutory, adjusted_gti) = 15000, so
    # chapterVIA.section80G MUST equal 15000 to satisfy the builder's
    # _schedule_80g cross-foot assertion (emitted_eligible == allowed_deduction)
    # and the ITR1-R242 calc validator (amount_80g <= eng_80g).
    draft.deductions.section80G = [
        Donation80G(
            id="g1", category="100_NO_APPROVAL",
            doneeName="Prime Minister Relief Fund", doneePAN="AAAPA1234A",
            arnNumber="",
            addrDetail="1 North Block", city="New Delhi", stateCode="07",
            pinCode="110001", donationAmtOtherMode=Decimal("5000"),
            transactionRefNum="UTR80G1", ifscCode="SBIN0001234",
        ),
        Donation80G(
            id="g2", category="50_NO_APPROVAL",
            doneeName="Indira Gandhi Memorial Trust", doneePAN="AAAPB1234B",
            arnNumber="",
            addrDetail="2 South Avenue", city="New Delhi", stateCode="07",
            pinCode="110011", donationAmtOtherMode=Decimal("5000"),
            transactionRefNum="UTR80G2", ifscCode="SBIN0001234",
        ),
        Donation80G(
            id="g3", category="100_APPROVAL_REQD",
            doneeName="National Education Society", doneePAN="AAAPC1234C",
            arnNumber="ARN80G3",
            addrDetail="3 Education Street", city="Mumbai", stateCode="27",
            pinCode="400001", donationAmtOtherMode=Decimal("5000"),
            transactionRefNum="UTR80G3", ifscCode="SBIN0001234",
        ),
        Donation80G(
            id="g4", category="50_APPROVAL_REQD",
            doneeName="Relief Fund", doneePAN="AAAPD1234D",
            arnNumber="ARN80G4",
            addrDetail="1 Main Road", city="Delhi", stateCode="07",
            pinCode="110001", donationAmtOtherMode=Decimal("5000"),
            transactionRefNum="UTR80G4", ifscCode="SBIN0001234",
        ),
    ]
    draft.deductions.chapterVIA.section80G = Decimal("15000")
    # Interest-deduction loans. 80EE and 80EEA are MUTUALLY EXCLUSIVE
    # (validator ITR1-R123), so the variant selects which one is active.
    # The 80EE loan must (a) be sanctioned in FY 2016-17, (b) carry a
    # loan ≤ ₹35L (R227), and (c) match a Section 24(b) loan by lender
    # name + account number (R222) — it reuses the house-property home
    # loan above (same lender/account/FY2016-17 date/₹30L amount).
    # 80EEB (EV-loan interest, max ₹1,50,000) is NOT mutually exclusive
    # with 80EE/80EEA, so it is added to BOTH variants. Its loan date
    # must fall in FY 2019-20 through FY 2022-23 (R232) and it carries
    # a vehicle registration number.
    loans: list[DeductionLoan] = [
        DeductionLoan(
            id="edu1", section="80E", loanTakenFrom="B", lenderName="Example Bank",
            loanAccountNo="EDU123", dateOfLoan="2022-01-01",
            totalLoanAmount=Decimal("200000"), outstandingAmount=Decimal("150000"),
            interestAmount=Decimal("10000"),
        ),
        DeductionLoan(
            id="eeb1", section="80EEB", loanTakenFrom="B",
            lenderName="Example Bank", loanAccountNo="EV456",
            dateOfLoan="2021-04-01", totalLoanAmount=Decimal("800000"),
            outstandingAmount=Decimal("600000"),
            interestAmount=Decimal("50000"),
            vehicleRegNo="DL01AB1234",
        ),
    ]
    if loan_variant == "80EE":
        loans.append(DeductionLoan(
            id="ee1", section="80EE", loanTakenFrom="B",
            lenderName="Example Bank", loanAccountNo="HOME123",
            dateOfLoan="2016-04-01", totalLoanAmount=Decimal("3000000"),
            outstandingAmount=Decimal("2500000"),
            interestAmount=Decimal("50000"),
        ))
        draft.deductions.chapterVIA.section80EE = Decimal("50000")
        draft.deductions.chapterVIA.section80EEA = Decimal("0")
        draft.deductions.loans.section80EEAStampDutyValue = Decimal("0")
    else:
        loans.append(DeductionLoan(
            id="eea1", section="80EEA", loanTakenFrom="B",
            lenderName="Example Bank", loanAccountNo="HOME123",
            dateOfLoan="2020-04-01", totalLoanAmount=Decimal("3000000"),
            outstandingAmount=Decimal("2500000"),
            interestAmount=Decimal("50000"),
        ))
        draft.deductions.chapterVIA.section80EE = Decimal("0")
        draft.deductions.chapterVIA.section80EEA = Decimal("50000")
        draft.deductions.loans.section80EEAStampDutyValue = Decimal("4000000")
    draft.deductions.loans.loans = loans
    # 80E education-loan interest (shared across both variants).
    draft.deductions.chapterVIA.section80E = Decimal("10000")
    # 80EEB interest is shared across both variants (not mutually exclusive).
    draft.deductions.chapterVIA.section80EEB = Decimal("50000")
    # Restricted 112A (listed-equity LTCG) — the canonical draft carries the
    # raw ``capitalGainsSchedule`` dict; the ITR-1/ITR-4 draft mappers read
    # the ``simplified112A`` block (``totalSaleConsideration`` minus
    # ``totalCostAcquisition``, floored at 0). The builder's
    # ``_ltcg_112a_schedule`` emits the three official fields
    # (TotSaleCnsdrn / TotCstAcqisn / LongCap112A) whenever BOTH sale and
    # cost are non-None. A POSITIVE gain (₹80,000, under the ₹1,25,000
    # annual exemption) now exercises the corrected GTI path: the FULL
    # pre-exemption gain flows into GrossTotIncomeIncLTCG112A, the
    # exemption zeroes the 12.5% special-rate tax, and the gain is removed
    # from the normal slab base. This was previously blocked by two
    # validator/calculator inconsistencies (ITR1-R022 expected GTI built
    # from the post-exemption taxable 112A; ITR4-R264 compared
    # result.capital_gains_112a against the post-exemption taxable_income);
    # both are now fixed so a positive gain validates cleanly.
    draft.capitalGainsSchedule = {
        "simplified112A": {
            "totalSaleConsideration": Decimal("180000"),
            "totalCostAcquisition": Decimal("100000"),
        },
    }
    draft.deductions.schedule80GGA = [Schedule80GGAEntry(
        id="gga1", relevantClause="80GGA2a", doneeName="Research Fund",
        doneePAN="BBBBB1234B", addressLine="2 Science Road", city="Delhi",
        stateCode="07", pinCode="110001", otherModeAmount=Decimal("3000"),
    )]
    draft.deductions.chapterVIA.section80GGA = Decimal("3000")
    draft.deductions.schedule80GGC = [Schedule80GGCEntry(
        id="ggc1", otherModeAmount=Decimal("4000"),
        contributionDate="2025-06-01", transactionRef="UTR80GGC1",
        ifscCode="SBIN0001234", politicalPartyName="Example Party",
        politicalPartyPAN="CCCCC1234C",
    )]
    draft.deductions.chapterVIA.section80GGC = Decimal("4000")
    # Section 80DD — dependent disability (normal severity, ₹75,000 flat).
    # The builder reads the chapterVIA scalar + disability metadata to build
    # ITR1.Schedule80DD. Normal severity (not severe) → deduction must
    # equal SECTION_80DD_LIMIT (₹75,000). Dependent must be a real
    # relationship (not "member_of_huf" — blocked for ITR-1). Form 10-IA
    # must be filed ("Y") with an acknowledgement number.
    draft.deductions.chapterVIA.section80DD = Decimal("75000")
    draft.deductions.chapterVIA.section80DDNatureOfDisability = "1"  # NORMAL
    draft.deductions.chapterVIA.section80DDTypeOfDisability = "2"     # OTHER
    draft.deductions.chapterVIA.section80DDDependentType = "1"        # SPOUSE
    draft.deductions.chapterVIA.section80DDDependentPAN = "EFGHI1234J"
    draft.deductions.chapterVIA.section80DDDependentAadhaar = "234567890123"
    draft.deductions.chapterVIA.section80DDForm10IA = Form10IAFiling(
        filed="Y",
        acknowledgementNumber="80DD10IA26001",
        filingDate="2025-06-01",
        formAckNum11A="80DD11A26001",
    )
    draft.deductions.chapterVIA.section80DDUDIDNumber = "80DDUDID12345"
    # Section 80U — self disability (normal severity, ₹75,000 flat).
    # Same severity/amount contract as 80DD but no dependent fields.
    draft.deductions.chapterVIA.section80U = Decimal("75000")
    draft.deductions.chapterVIA.section80UNatureOfDisability = "1"  # NORMAL
    draft.deductions.chapterVIA.section80UTypeOfDisability = "2"     # OTHER
    draft.deductions.chapterVIA.section80UForm10IA = Form10IAFiling(
        filed="Y",
        acknowledgementNumber="80U10IA26001",
        filingDate="2025-06-01",
        formAckNum11A="80U11A26001",
    )
    draft.deductions.chapterVIA.section80UUDIDNumber = "80UUDID12345"
    # PRAN (NPS) — emits UsrDeductUndChapVIA.PRANDtls[].PRANNum. The
    # draft mapper reads ``chapterVIA.pranNumber`` and the builder emits
    # ``PRANDtls: [{PRANNum: <pran>}]`` whenever it is set. CBDT Sl 407
    # requires that a PRAN be accompanied by a positive 80CCD(1) and/or
    # 80CCD(1B) NPS contribution, so both are claimed here. The PRAN is a
    # 12-digit string (the ITR-4 ``ITR4Input.pran_number`` field enforces
    # ``max_length=12``).
    draft.deductions.chapterVIA.section80CCDEmployeeOrSE = Decimal("25000")
    draft.deductions.chapterVIA.section80CCD1B = Decimal("25000")
    draft.deductions.chapterVIA.pranNumber = "110002347890"
    # TDS credit (salary TDS — deductor is the employer). The CBDT schema
    # enforces a city-prefix TAN pattern (DEL/BLR/MUM/...); use a valid one.
    draft.taxes.tds = [TdsCredit(
        id="t1", deductorTAN="DELX12345A", deductorName="Acme Corp",
        section="192", taxDeducted=Decimal("30000"),
        grossAmount=Decimal("600000"),
    ), TdsCredit(
        id="t2", deductorTAN="DELY12345B", deductorName="Example Bank",
        section="194A", schedule="TDS2", deductedYr=2025,
        taxDeducted=Decimal("1000"), grossAmount=Decimal("10000"),
    ), TdsCredit(
        id="t3", schedule="TDS3", section="194IB", tdsSectionCode="194IB",
        nameOfTenant="Example Tenant", panOfTenant="DDDDD1234D",
        grsRcptToTaxDeduct=Decimal("120000"), taxDeducted=Decimal("6000"),
        tdsClaimed=Decimal("6000"), deductedYr=2025,
    )]
    draft.taxes.tcs = [TcsCredit(
        id="tcs1", collectorName="Example Collector", collectorTAN="DELZ12345C",
        grossAmount=Decimal("100000"), taxCollected=Decimal("1000"),
        tcsClaimedAmtCollOwnHand=Decimal("1000"), deductedYr=2025,
    )]
    draft.taxes.challans = [
        TaxChallan(
            id="at1", kind="ADVANCE_TAX", bsrCode="1234567",
            depositDate="2025-06-15", challanSerialNo=1, amount=Decimal("5000"),
        ),
        TaxChallan(
            id="sat1", kind="SELF_ASSESSMENT", bsrCode="1234567",
            depositDate="2026-04-15", challanSerialNo=2, amount=Decimal("2000"),
        ),
    ]
    # Populate the four official-filing addon path groups
    # (AlternateAddress, seventh-proviso clause-iv, AssesseeRep, TRP) so
    # the audit exercises the FilingStatus/PersonalInfo/TaxReturnPreparer
    # paths that the income-only base draft does not carry.
    _populate_official_filing_addons(draft)
    return draft


def build_full_itr4_draft(*, scheme: str = "44AD", loan_variant: str = "80EEA") -> ReturnDraft:
    """A maximally-populated canonical ITR-4 draft for one presumptive scheme.

    Mirrors the ``loan_variant`` pattern in :func:`build_full_itr1_draft`:
    the three ITR-4 presumptive schemes (44AD, 44ADA, 44AE) are best
    exercised as separate draft variants because each emits a distinct
    ``ScheduleBP.NatOfBus44XX[]`` block. The ``scheme`` argument selects
    which canonical business row :func:`tests.test_filing_gateway_v2_itr4.
    _filing_ready_itr4` builds (a valid 44AD/44ADA/44AE shape including
    the ``_financial_particulars()`` balance-sheet block the ITR-4
    Category A validator requires for every scheme).

    Per-variant enrichments (so each variant exercises a distinct set of
    previously-missing ScheduleBP / TaxExmpIntIncDtls paths):

      * ``44AD`` — sets ``businessName`` (so ``NatOfBus44AD[].NameOfBusiness``
        + ``CodeAD`` emit), adds a ``GstinTurnoverRow`` (so
        ``TurnoverGrsRcptForGSTIN[]`` + ``GSTINNo`` /
        ``AmtTurnGrossRcptGSTIN`` emit), and adds one ``ExemptIncomeEntry``
        (so ``TaxExmpIntIncDtls.OthersInc.OthersIncDtls[]`` + ``OthAmount``
        emit).
      * ``44ADA`` — sets ``businessName`` (so ``NatOfBus44ADA[].NameOfBusiness``
        + ``CodeADA`` emit) and adds a ``GstinTurnoverRow`` (so the GSTIN
        turnover block is exercised under the professional scheme too).
      * ``44AE`` — sets ``businessName`` (so ``NatOfBus44AE[].NameOfBusiness``
        + ``CodeAE`` emit); the ``VehicleRecord`` already supplied by
        ``_filing_ready_itr4("44AE")`` drives
        ``GoodsDtlsUs44AE[].RegNumberGoodsCarriage`` /
        ``OwnedLeasedHiredFlag`` / ``TonnageCapacity`` / ``HoldingPeriod`` /
        ``PresumptiveIncome``.

    Validity constraints honoured (see
    ``app/engine/validators/itr4/input_rules.py`` and
    ``app/engine/validators/itr4/calc_rules.py``):
      * 44ADA declared income >= 50% of gross receipts (R014) and <= gross
        receipts (R013); the helper's 20L/40L split satisfies both.
      * 44AE <= 10 vehicles and <= 120 aggregate owned months (R141); the
        helper's single 12-month vehicle satisfies both.
      * 44ADA cash (nonDigitalReceipts) <= 5% when gross > 50L (R238); the
        helper's 40L gross is under the 50L trigger.
      * 44AD/44ADA receipts split (digital + nonDigital + other = total)
        (R239/R240); the mapper derives total from the split, so it always
        matches by construction.
      * Schedule BP financial particulars supplied on EVERY variant
        (Category A Sl 139).

    Args:
        scheme: ``"44AD"`` (default), ``"44ADA"``, or ``"44AE"``.
        loan_variant: forwarded to ``build_full_itr1_draft`` so the
            inherited deductions carry the 80EE loan + senior-citizen
            80D arrays when ``"80EE"``. Defaults to ``"80EEA"``.

    Returns:
        A maximally-populated ``ReturnDraft`` for ITR-4 in the given scheme.
    """
    from app.schemas.return_draft import (
        GstinTurnoverRow,
    )
    from tests.test_filing_gateway_v2_itr4 import _filing_ready_itr4
    draft = _filing_ready_itr4(scheme)
    conditional = build_full_itr1_draft(loan_variant=loan_variant)
    draft.regime = "old"
    draft.employers = conditional.employers
    draft.houseProperties = conditional.houseProperties
    draft.otherSources = conditional.otherSources
    draft.deductions = conditional.deductions
    # The ITR-4 draft mapper reuses the shared ``_map_capital_gains`` helper,
    # which reads ``draft.capitalGainsSchedule["simplified112A"]`` the same
    # way as ITR-1. The conditional ITR-1 draft carries the block, but
    # ``build_full_itr4_draft`` builds its own draft object, so mirror the
    # same restricted-112A block here so the three LTCG112A fields are
    # emitted by the ITR-4 ITD builder too.
    draft.capitalGainsSchedule = conditional.capitalGainsSchedule
    # 80GGA is not available to a taxpayer with business income in ITR-4.
    draft.deductions.schedule80GGA = []
    draft.deductions.chapterVIA.section80GGA = Decimal("0")
    draft.taxes = conditional.taxes
    # The ScheduleBP.NatOfBus44XX[] rows are only emitted when BOTH
    # businessName AND natureCode are present (the mapper filters on both).
    # _filing_ready_itr4 sets natureCode but not businessName, so set it
    # here to exercise NatOfBus44XX[].NameOfBusiness + CodeXX on every
    # variant.
    business = draft.businesses[0]
    if scheme == "44AD":
        business.businessName = "Sharma Stores"
        business.description = "Retail trade of general merchandise"
        # GSTIN turnover row -> ScheduleBP.TurnoverGrsRcptForGSTIN[] +
        # GSTINNo + AmtTurnGrossRcptGSTIN. The 44AD total turnover
        # (digital+nonDigital+other) is unaffected -- GSTIN turnover is a
        # separate Schedule BP disclosure.
        business.gstinTurnovers = [
            GstinTurnoverRow(
                id="gst-1",
                gstin="07ABCDE1234F1Z5",
                turnover=Decimal("6250000"),
            )
        ]
        # Exempt-income detail row -> TaxExmpIntIncDtls.OthersInc.
        # OthersIncDtls[] + OthAmount. Use a Section 10(10D) life-insurance
        # maturity proceeds sub-category with a positive gross amount.
        draft.exemptIncome.otherExemptIncome = [
            ExemptIncomeEntry(
                id="ei-1",
                category="OTH",
                subCategory="10(10D)",
                description="Maturity proceeds of life insurance policy",
                grossAmount=Decimal("50000"),
            )
        ]
    elif scheme == "44ADA":
        business.businessName = "Sharma Consultancy"
        business.description = "Management consultancy services"
        # Exercise the GSTIN turnover block under the 44ADA scheme too.
        business.gstinTurnovers = [
            GstinTurnoverRow(
                id="gst-1",
                gstin="07ABCDE1234F1Z5",
                turnover=Decimal("4000000"),
            )
        ]
    elif scheme == "44AE":
        business.businessName = "Sharma Transport"
        business.description = "Goods carriage business"
        # _filing_ready_itr4("44AE") already supplies one VehicleRecord
        # (HEAVY, tonnage 16, 12 months) -- the builder emits the full
        # GoodsDtlsUs44AE[] row (RegNumberGoodsCarriage /
        # OwnedLeasedHiredFlag / TonnageCapacity / HoldingPeriod /
        # PresumptiveIncome) from that record.
    # The ITR-4 draft builds its own personal/filing/verification/
    # taxReturnPreparer objects (via _filing_ready_itr4), so populate the
    # four official-filing addon path groups on the ITR-4 draft directly.
    # CBDT ITR-4 R410 requires a secondary address for a representative,
    # which the AlternateAddress block in the helper satisfies.
    _populate_official_filing_addons(draft)
    return draft


def audit(form: str, draft: ReturnDraft) -> None:
    """Generate the official JSON and report required-field coverage."""
    print(f"\n{'=' * 70}\n{form} end-to-end coverage audit\n{'=' * 70}")
    try:
        official, summary = generate_cbdt_json(draft)
    except FilingGatewayV2Error as exc:
        print(f"  generate_cbdt_json FAILED: {exc.message}")
        for err in exc.errors[:6]:
            print(f"    - {err[:160]}")
        return
    required = _load_required_fields(form)
    # Dedupe the required list (allOf can produce duplicate paths).
    seen: set[str] = set()
    required = [r for r in required if not (r in seen or seen.add(r))]
    print(f"  JSON generated OK. Checking {len(required)} required schema fields...")
    missing, empty, present = _classify_paths(official, required)
    print(f"  PRESENT : {len(present)}/{len(required)}")
    print(f"  MISSING : {len(missing)}")
    print(f"  EMPTY   : {len(empty)}")
    # Persist full missing/empty/present lists to CSV for the report.
    slug = form.lower().replace("-", "")
    for label, rows in (("missing", missing), ("empty", empty), ("present", present)):
        out = Path(f"audit_{slug}_{label}.csv")
        with out.open("w", encoding="utf-8") as f:
            f.write("path\n")
            for p in rows:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"  {label:8}: {len(rows):3d} -> {out}")
    Path(f"audit_{slug}_generated.json").write_text(
        json.dumps(official, indent=2, default=str), encoding="utf-8")
    print(f"  Generated JSON written to audit_{slug}_generated.json")


def _classify_paths(official: dict, required: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Split required paths into missing / empty / present for one JSON.

    Args:
        official: The generated CBDT JSON document.
        required: Deduplicated required leaf field paths.

    Returns:
        ``(missing, empty, present)`` path lists, in required order.
    """
    missing: list[str] = []
    empty: list[str] = []
    present: list[str] = []
    for path in required:
        val = _get_path(official, path)
        if val is None:
            missing.append(path)
        elif _is_empty(val):
            empty.append(path)
        else:
            present.append(path)
    return missing, empty, present


def audit_with_variants(form: str, drafts: list[ReturnDraft]) -> None:
    """Audit a form across multiple draft variants, unioning present paths.

    Some schema paths are MUTUALLY EXCLUSIVE in a single draft (e.g.
    Section 80EE and 80EEA loans — validator ITR1-R123 forbids both).
    To exercise every required path, the audit builds one draft per
    variant, generates each, and unions the present-path sets. A path
    is reported MISSING only when it is absent/empty across ALL
    variants; a path is PRESENT when at least one variant emits it.

    Args:
        form: The ITR form label (``"ITR-1"`` or ``"ITR-4"``).
        drafts: One maximally-populated draft per variant.
    """
    print(f"\n{'=' * 70}\n{form} end-to-end coverage audit\n{'=' * 70}")
    required = _load_required_fields(form)
    seen: set[str] = set()
    required = [r for r in required if not (r in seen or seen.add(r))]
    union_present: set[str] = set()
    union_empty: set[str] = set()
    generated_json: dict = {}
    for index, draft in enumerate(drafts):
        label = "default" if len(drafts) == 1 else f"variant {index + 1}"
        try:
            official, summary = generate_cbdt_json(draft)
        except FilingGatewayV2Error as exc:
            print(f"  [{label}] generate_cbdt_json FAILED: {exc.message}")
            for err in exc.errors[:6]:
                print(f"    - {err[:160]}")
            continue
        _, _, present = _classify_paths(official, required)
        union_present.update(present)
        # Empty-in-this-variant counts only against this variant; a path
        # present elsewhere is overall present, so union_empty is the
        # complement of union_present among non-missing paths.
        generated_json = official
        print(f"  [{label}] OK — {len(present)} present paths")
    missing = [p for p in required if p not in union_present]
    empty: list[str] = []
    present = [p for p in required if p in union_present]
    # A path present in one variant but missing (None) in all others is
    # reported EMPTY if at least one variant emitted an empty container
    # for it; otherwise MISSING. For simplicity, anything not present is
    # reported MISSING (the single-draft path already distinguishes).
    print(f"  PRESENT : {len(present)}/{len(required)}")
    print(f"  MISSING : {len(missing)}")
    print(f"  EMPTY   : {len(empty)}")
    slug = form.lower().replace("-", "")
    for label, rows in (("missing", missing), ("empty", empty), ("present", present)):
        out = Path(f"audit_{slug}_{label}.csv")
        with out.open("w", encoding="utf-8") as f:
            f.write("path\n")
            for p in rows:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"  {label:8}: {len(rows):3d} -> {out}")
    if generated_json:
        Path(f"audit_{slug}_generated.json").write_text(
            json.dumps(generated_json, indent=2, default=str), encoding="utf-8")
        print(f"  Generated JSON written to audit_{slug}_generated.json")


def main() -> None:
    # ITR-1 audits two mutually-exclusive loan variants (80EEA default +
    # 80EE senior) and unions their present-path sets so Schedule 80EE,
    # Schedule 80EEB, and the senior 80D policy arrays are all exercised.
    audit_with_variants("ITR-1", [
        build_full_itr1_draft(loan_variant="80EEA"),
        build_full_itr1_draft(loan_variant="80EE"),
    ])
    # ITR-4 audits three presumptive-scheme variants (44AD default +
    # 44ADA professional + 44AE goods carriage) and unions their
    # present-path sets so ScheduleBP.NatOfBus44AD[], .NatOfBus44ADA[],
    # .NatOfBus44AE[], .GoodsDtlsUs44AE[], .TurnoverGrsRcptForGSTIN[],
    # and TaxExmpIntIncDtls.OthersInc.OthersIncDtls[] are all exercised.
    # The 44AD variant also carries a GSTIN turnover row and an
    # exempt-income entry; the 44ADA variant carries a GSTIN turnover row;
    # the 44AE variant carries the VehicleRecord that drives the
    # GoodsDtlsUs44AE[] row.
    audit_with_variants("ITR-4", [
        build_full_itr4_draft(scheme="44AD"),
        build_full_itr4_draft(scheme="44ADA"),
        build_full_itr4_draft(scheme="44AE"),
        # 80EE-loan + senior-citizen 80D variant (44AD base). The 80EE
        # and 80EEA loans are mutually exclusive, and the senior 80D
        # policy arrays are only emitted when the assessee is a senior
        # citizen with senior policy buckets — both inherited from
        # build_full_itr1_draft(loan_variant="80EE"). This exercises
        # ITR4.Schedule80EE.* (11 paths) and the ITR4 senior-80D
        # Sec80DSelfFamSrCtznHIDtls / Sec80DParentsSrCtznHIDtls arrays
        # (8 paths) that the three scheme variants above do not carry.
        build_full_itr4_draft(scheme="44AD", loan_variant="80EE"),
    ])


if __name__ == "__main__":
    main()
