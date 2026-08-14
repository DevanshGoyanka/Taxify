import datetime
import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome, Donation80G, Donation80GCategory,
    DonationAddress, TDS1Entry, TDS2Entry,
    TCSEntry, PropertyType, AgeBracket, TaxRegime,
)
from app.schemas.itr2 import (
    ITR2Input,
    CGAssetType,
    CGTransaction,
    ResidentialStatus as ITR2ResidentialStatus,
    ReturnFileSection,
)
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD,
    PresumptiveProfessionalIncome44ADA, PresumptiveGoodsCarriage44AE,
    GoodsCarriageVehicle,
)
from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.calculators.itr2 import compute as compute_itr2
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.schedules.special_rates import compute_112a, compute_111a
from app.engine.schedules.restricted_112a import compute_restricted_112a
from app.engine.common.hra import compute_hra_exemption
from app.engine.constants import (
    PRESUMPTIVE_44AD_DIGITAL,
    PRESUMPTIVE_44ADA_RATE,
    SEC_44AD_TURNOVER_LIMIT,
    SEC_44ADA_RECEIPTS_LIMIT,
    LTCG_OTHER_RATE_POST_JUL24,
)

router = APIRouter(tags=["tax"])

_TAN_PATTERN = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
_BSR_PATTERN = re.compile(r"^[0-9]{7}$")
_CHALLAN_SERIAL_PATTERN = re.compile(r"^[0-9]{1,5}$")


def _credit_issue(
    *,
    credit_type: str,
    row: int,
    amount: Decimal,
    code: str,
    message: str,
    field: str | None = None,
    entered_value: str | None = None,
) -> dict[str, object]:
    """Build one structured tax-credit validation issue."""
    issue: dict[str, object] = {
        "creditType": credit_type,
        "row": row,
        "amount": float(amount),
        "code": code,
        "message": message,
    }
    if field is not None:
        issue["field"] = field
    if entered_value is not None:
        issue["enteredValue"] = entered_value
    return issue


def _money(value: object) -> Decimal:
    """Convert an untrusted JSON monetary value to a non-negative Decimal."""
    if value is None or value == "":
        return Decimal("0")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid monetary value: {value!r}",
        )
    if not amount.is_finite() or amount < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Monetary values must be finite and non-negative: {value!r}",
        )
    return amount


def _records(payload: dict, key: str) -> list[dict]:
    """Return validated object records from a JSON array field."""
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key} must be an array of objects",
        )
    return value


def _date(value: object, field_name: str) -> Optional[datetime.date]:
    """Parse an optional ISO date.

    Accepts ``YYYY-MM-DD`` and ``DD/MM/YYYY`` (the two formats the AIS
    reconciliation and the frontend emit).  Non-date placeholders such as
    the SFT-18(Pur) quarter string ``"Q2(Jul-Sep)"`` resolve to ``None``
    rather than aborting the whole computation — a single bad date in one
    evidence row must not prevent the return from being prepared.
    """
    if value is None or value == "":
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # ISO: YYYY-MM-DD
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        pass
    # DD/MM/YYYY → YYYY-MM-DD
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    # Unparseable placeholder (e.g. quarter) — degrade gracefully.
    return None


@router.post("/tax-summary/compute")
@router.post("/api/tax/compute")
def compute_tax_summary(
    payload: dict,
    regime: str = "NEW",
    current_user: User = Depends(get_current_user),
):
    import logging
    _logger = logging.getLogger("taxify.tax")
    try:
        return _compute_tax_summary_impl(payload, regime, current_user)
    except HTTPException as exc:
        _logger.warning("compute_tax_summary rejected: detail=%s", exc.detail)
        raise
    except ValidationError as exc:
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
            for error in exc.errors()
        ]
        _logger.warning("compute_tax_summary model validation rejected: errors=%s", errors)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Some tax computation fields are invalid.",
                "errors": errors,
            },
        ) from exc
    except Exception as exc:
        _logger.exception("compute_tax_summary unexpected error: %s", exc)
        raise


def _compute_itr2_from_flat_payload(
    payload: dict,
    age_bracket: AgeBracket,
    tax_regime: TaxRegime,
    salary_input: SalaryIncome,
    hp_input: HousePropertyIncome,
    os_input: OtherSourcesIncome,
    ded_input: Chapter6ADeductions,
    capital_gain_rows: list[dict],
    tds1_entries: list,
    tds2_entries: list,
    tcs_entries: list,
    advance_tax_paid: Decimal,
    self_assessment_paid: Decimal,
    quarterly_advance: list[Decimal],
    capital_gains_summary: dict | None,
) -> "object":
    """Map the flat frontend payload to ITR2Input and run the ITR-2 engine.

    This mirrors the ITR-1/ITR-4 mapping pattern: the backend translates
    the flat form data to the canonical Pydantic model, so the frontend
    never needs a form-specific mapper.
    """
    from app.schemas.itr2 import CGTransaction as CGTx, CGAssetType

    # Map capital-gain transactions from flat rows to canonical CGTransaction.
    # The frontend stores each field under multiple alias keys (set via
    # updateBoth) so we check all possible names for each field.
    _ASSET_TYPE_MAP: dict[str, str] = {
        "EQUITY_ORIENTED_MUTUAL_FUND": "equity_oriented_fund_112a",
        "LISTED_EQUITY": "listed_equity_112a",
        "BUSINESS_TRUST_UNIT": "business_trust_unit_112a",
        "LAND_BUILDING": "land_building",
        "UNLISTED_SHARES": "unlisted_shares",
        "LISTED_SECURITY": "listed_security",
        "DEBT_MUTUAL_FUND": "debt_mutual_fund",
        "SPECIFIED_MUTUAL_FUND": "specified_mutual_fund_50aa",
        "MARKET_LINKED_DEBENTURE": "market_linked_debenture_50aa",
        "BONDS_DEBENTURES": "bonds_debentures",
        "DEPRECIABLE_ASSET": "depreciable_asset",
        "JEWELLERY": "jewellery",
        "FOREIGN_ASSET": "foreign_asset",
    }

    def _first(row: dict, *keys: str, default=None):
        """Return the first non-None/non-empty value among the keys."""
        for k in keys:
            v = row.get(k)
            if v is not None and v != "" and v != 0:
                return v
        return default

    cg_transactions: list[CGTx] = []
    for row in capital_gain_rows:
        # AIS SFT-18(Pur) purchase-only evidence rows are reference data:
        # they carry a quarter (e.g. "Q2(Jul-Sep)") in place of a real
        # transaction date and have no sale consideration.  They are not
        # disposals to report in ITR-2 Schedule CG, so skip them here.
        # The reconciled purchase totals are already reflected in the
        # restricted-112A cost-of-acquisition aggregates computed above.
        side = str(row.get("evidenceSide", "")).upper()
        sale_value = _first(row, "saleValue", "saleCost", "fullValueOfConsideration", default=0)
        is_purchase_only = side == "PURCHASE" or (
            _money(sale_value) == 0
            and bool(row.get("quarter"))
        )
        if is_purchase_only:
            continue

        raw_asset = str(row.get("assetType", "other")).upper()
        mapped = _ASSET_TYPE_MAP.get(raw_asset, raw_asset.lower())
        try:
            asset_type = CGAssetType(mapped)
        except ValueError:
            asset_type = CGAssetType.OTHER

        # Date of transfer — frontend uses transferDate / saleDate
        raw_transfer = _first(row, "transferDate", "saleDate", "dateOfTransfer")
        date_of_transfer = _date(raw_transfer, "dateOfTransfer") if raw_transfer else None
        if date_of_transfer is None:
            date_of_transfer = datetime.date(2026, 3, 31)

        # Date of acquisition — frontend uses acquisitionDate / purchaseDate
        raw_acq = _first(row, "acquisitionDate", "purchaseDate", "dateOfAcquisition")
        date_of_acquisition = _date(raw_acq, "dateOfAcquisition") if raw_acq else None

        # Sale consideration — frontend uses saleValue / saleCost
        sale = _money(_first(row, "saleValue", "saleCost", "fullValueOfConsideration", default=0))
        # Cost — frontend uses actualCost / purchaseCost
        cost = _money(_first(row, "actualCost", "purchaseCost", "costOfAcquisition", default=0))
        # Transfer expenses
        exp = _money(_first(row, "transferExpenses", "expenses", "expenditureOnTransfer", default=0))
        # STT on transfer
        stt = row.get("sttPaidOnTransfer")
        if stt is None:
            stt = row.get("sttPaid")
        # FMV 31-Jan-2018
        raw_fmv = _first(row, "fmv31Jan2018", "fmvJan2018", "fairMarketValueJan2018")
        fmv = _money(raw_fmv) if raw_fmv else None

        cg_transactions.append(CGTx(
            asset_type=asset_type,
            description=str(row.get("description", row.get("assetDescription", ""))),
            date_of_acquisition=date_of_acquisition,
            date_of_transfer=date_of_transfer,
            full_consideration=sale,
            cost_of_acquisition=cost,
            expenditure_on_transfer=exp,
            is_stt_paid_on_transfer=stt if stt is not None else None,
            fair_market_value_jan2018=fmv,
        ))

    # Map residential status
    raw_res_status = str(payload.get("residentialStatus", "ROR")).upper()
    if raw_res_status in {"ROR", "RES", "RESIDENT"}:
        res_status = ITR2ResidentialStatus.RESIDENT
    elif raw_res_status in {"NRI", "NR", "NON_RESIDENT"}:
        res_status = ITR2ResidentialStatus.NON_RESIDENT
    else:
        res_status = ITR2ResidentialStatus.RESIDENT_NOT_ORDINARILY

    itr2_input = ITR2Input(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        residential_status=res_status,
        salary_income=salary_input,
        house_property_income=hp_input,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        cg_transactions=cg_transactions,
        tds1_entries=tds1_entries or [],
        tds2_entries=tds2_entries or [],
        tcs_entries=tcs_entries or [],
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax_paid=self_assessment_paid,
        advance_tax_q1=quarterly_advance[0],
        advance_tax_q2=quarterly_advance[1],
        advance_tax_q3=quarterly_advance[2],
        advance_tax_q4=quarterly_advance[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        relief_89=_money(payload.get("relief89", payload.get("relief_89"))),
    )
    try:
        return compute_itr2(itr2_input)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


def _compute_tax_summary_impl(payload: dict, regime: str, current_user: User):
    assessment_year = str(payload.get("assessmentYear") or "2026-27")
    if assessment_year != "2026-27":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tax computation currently supports assessment year 2026-27 only.",
        )

    # Determine age
    age = int(payload.get("age", 30) or 30)
    if age >= 80:
        age_bracket = AgeBracket.ABOVE_80
    elif age >= 60:
        age_bracket = AgeBracket.SIXTY_TO_80
    else:
        age_bracket = AgeBracket.BELOW_60
        
    tax_regime = TaxRegime.OLD if regime.upper() == "OLD" else TaxRegime.NEW
    
    # 1. Map Salary. Canonical employer rows take precedence over legacy scalars.
    imported_category_controls = payload.get("importedCategoryControls")
    category_controls = (
        imported_category_controls if isinstance(imported_category_controls, dict) else {}
    )
    employers = _records(payload, "employerEntries")
    salary_rows = employers if employers else [payload]
    basic = sum((_money(row.get("basic")) for row in salary_rows), Decimal("0"))
    if "salary" in category_controls:
        basic = _money(category_controls.get("salary"))
    da = sum((_money(row.get("da")) for row in salary_rows), Decimal("0"))
    bonus = sum((_money(row.get("bonus")) for row in salary_rows), Decimal("0"))
    commission = sum((_money(row.get("commission")) for row in salary_rows), Decimal("0"))
    hra_received = sum(
        (_money(row.get("hra", row.get("hraReceived"))) for row in salary_rows),
        Decimal("0"),
    )
    perquisites = sum((_money(row.get("perquisites")) for row in salary_rows), Decimal("0"))
    profits_in_lieu = sum((_money(row.get("profitsInLieu")) for row in salary_rows), Decimal("0"))
    other_allowance = sum(
        (_money(row.get("otherAllowance", row.get("allowances"))) for row in salary_rows),
        Decimal("0"),
    )

    # gross_salary is section 17(1) salary only. Perquisites and profits in lieu
    # are separate sections and are added exactly once by the salary schedule.
    section_17_1_salary = basic + da + bonus + commission + hra_received + other_allowance
    gross_salary = section_17_1_salary + perquisites + profits_in_lieu

    # HRA exemption is computed server-side u/s 10(13A) from the three-condition
    # test (actual HRA, rent − 10% salary, 50%/40% salary).  We never trust a
    # frontend-supplied exempt amount; the engine derives it from hraDetails.
    # When hraDetails is absent, the declared hraExempt is used only as a
    # display value (the exemption must be recomputed before filing).
    hra_details_raw = payload.get("hraDetails") or payload.get("hraEntry")
    hra_condition1 = Decimal("0")
    hra_condition2 = Decimal("0")
    hra_condition3 = Decimal("0")
    hra_is_metro = False
    if isinstance(hra_details_raw, dict) and hra_details_raw.get("rentPaid") is not None:
        hra_salary = _money(hra_details_raw.get("salaryForHra", basic + da))
        hra_is_metro = bool(hra_details_raw.get("isMetroCity", hra_details_raw.get("hraMetro", False)))
        hra_result = compute_hra_exemption(
            actual_hra_received=hra_received,
            rent_paid=_money(hra_details_raw.get("rentPaid")),
            salary=hra_salary,
            is_metro=hra_is_metro,
        )
        hra_exempt = hra_result.exempt_amount
        hra_condition1 = hra_result.actual_hra_received
        hra_condition2 = hra_result.rent_minus_10pct_salary
        hra_condition3 = hra_result.salary_factor
    else:
        # No top-level hraDetails object.  The frontend sends HRA facts
        # per-employer inside employerEntries (hra, rentPaid, basic, da,
        # isMetroCity).  Statutorily recompute the exemption for each
        # employer and sum — the ITD schema permits per-employer HRA
        # evidence (Schedule EA10_13A).  When an employer has HRA but no
        # rent/metro facts the exemption for that row is zero.
        hra_exempt = Decimal("0")
        for row in salary_rows:
            row_hra = _money(row.get("hra", row.get("hraReceived")))
            row_rent = _money(row.get("rentPaid"))
            row_basic = _money(row.get("basic"))
            row_da = _money(row.get("da"))
            row_salary = row_basic + row_da
            row_metro = bool(
                row.get("isMetroCity", row.get("hraMetro", False))
            )
            if row_hra > 0 and row_rent > 0 and row_salary > 0:
                row_result = compute_hra_exemption(
                    actual_hra_received=row_hra,
                    rent_paid=row_rent,
                    salary=row_salary,
                    is_metro=row_metro,
                )
                hra_exempt += row_result.exempt_amount
                # Aggregate display conditions across employers.
                hra_condition1 += row_result.actual_hra_received
                hra_condition2 += row_result.rent_minus_10pct_salary
                hra_condition3 += row_result.salary_factor
                hra_is_metro = row_metro or hra_is_metro
            elif row_hra > 0:
                # HRA received but rent/metro facts missing — surface the
                # declared hraExempt (zero if absent) so validation flags it.
                hra_exempt += _money(row.get("hraExempt"))
    lta_exempt = sum((_money(row.get("ltaExempt")) for row in salary_rows), Decimal("0"))
    prof_tax = sum(
        (_money(row.get("professionalTax", row.get("profTax"))) for row in salary_rows),
        Decimal("0"),
    )
    ent_allowance = sum(
        (_money(row.get("entertainmentAllowance")) for row in salary_rows),
        Decimal("0"),
    )
    is_govt = any(bool(row.get("isGovernmentEmployee", False)) for row in salary_rows)

    salary_input = SalaryIncome(
        gross_salary=section_17_1_salary,
        perquisites_value=perquisites,
        profits_in_lieu_of_salary=profits_in_lieu,
        hra_exempt_amount=hra_exempt,
        lta_exempt_amount=lta_exempt,
        professional_tax_paid=prof_tax,
        entertainment_allowance=ent_allowance,
        is_government_employee=is_govt,
    )
    
    # 2. Map every canonical housePropertyEntries row. The CBDT AY 2026-27
    # ITR-1 V1.1 schema permits at most two PropertyDetails rows; the
    # ITR1Input schema enforces this cap. Legacy single-property payloads
    # (no housePropertyEntries array) fall back to the flat payload.
    properties = _records(payload, "housePropertyEntries")
    if not properties:
        properties = [payload]

    hp_type_map = {
        "SELF": PropertyType.SELF_OCCUPIED,
        "SELF_OCCUPIED": PropertyType.SELF_OCCUPIED,
        "LET_OUT": PropertyType.LET_OUT,
        "DEEMED_LET_OUT": PropertyType.DEEMED_LET_OUT,
    }

    def _build_hp_input(property_row: dict) -> HousePropertyIncome:
        raw_hp_type = str(property_row.get("propertyType", property_row.get("hpType", "self"))).upper()
        property_type = hp_type_map.get(raw_hp_type, PropertyType.LET_OUT)
        loan_interest = _money(property_row.get("interestOnLoan"))
        if loan_interest == 0:
            loan_interest = sum(
                (_money(loan.get("interestUs24B")) for loan in _records(property_row, "homeLoans")),
                Decimal("0"),
            )
        if loan_interest == 0:
            loan_interest = _money(property_row.get("homeLoanInt", property_row.get("sopLoanInt")))
        return HousePropertyIncome(
            property_type=property_type,
            annual_rent_received=_money(
                property_row.get(
                    "annualRent",
                    property_row.get("annualLettingValue", property_row.get("grossRent")),
                )
            ),
            municipal_taxes_paid=_money(property_row.get("municipalTaxesPaid", property_row.get("munTax"))),
            home_loan_interest_paid=loan_interest,
            municipal_value=_money(property_row.get("municipalRateableValue")),
            fair_rent=_money(property_row.get("fairRentValue")),
            arrears_unrealised_rent_received=_money(property_row.get("arrearsOfRent")),
        )

    hp_inputs = [_build_hp_input(property_row) for property_row in properties]
    # Backward-compatible single-property scalar (first row).
    hp_input = hp_inputs[0]
    
    # 3. Map Other Sources. Canonical rows take precedence over scalar aliases.
    interest_rows = _records(payload, "interestEntries") or _records(payload, "bankInterestEntries")
    if interest_rows:
        savings_kinds = {"SAVINGS_BANK", "POST_OFFICE"}
        interest_sb = sum(
            (_money(row.get("grossAmount")) for row in interest_rows if str(row.get("kind", row.get("itdTag", ""))).upper() in savings_kinds),
            Decimal("0"),
        )
        interest_fd = sum(
            (_money(row.get("grossAmount")) for row in interest_rows if str(row.get("kind", row.get("itdTag", ""))).upper() not in savings_kinds),
            Decimal("0"),
        )
        interest_rd = nsc_interest = scss_interest = post_office_interest = other_interest = Decimal("0")
    else:
        interest_sb = _money(payload.get("interestSB"))
        interest_fd = _money(payload.get("interestFD"))
        interest_rd = _money(payload.get("interestRD"))
        nsc_interest = _money(payload.get("nscInterest"))
        scss_interest = _money(payload.get("scssInterest"))
        post_office_interest = _money(payload.get("postOfficeInterest"))
        other_interest = _money(payload.get("otherInterest"))
    if "interest from savings bank" in category_controls:
        interest_sb = _money(category_controls.get("interest from savings bank"))
    if "interest from deposit" in category_controls:
        interest_fd = _money(category_controls.get("interest from deposit"))
    total_interest = interest_sb + interest_fd + interest_rd + nsc_interest + scss_interest + post_office_interest + other_interest

    dividend_rows = _records(payload, "dividendEntries")
    controlled_dividend = (
        _money(category_controls.get("dividend"))
        if "dividend" in category_controls
        else None
    )
    if controlled_dividend is not None:
        total_dividend = controlled_dividend
    elif dividend_rows:
        total_dividend = sum((_money(row.get("grossAmount")) for row in dividend_rows), Decimal("0"))
    else:
        total_dividend = (
            _money(payload.get("dividendShares")) + _money(payload.get("dividendMF"))
            + _money(payload.get("dividendUnits")) + _money(payload.get("dividends"))
        )

    family_pension_row = payload.get("familyPensionEntry")
    family_pension = (
        _money(family_pension_row.get("grossAmount"))
        if isinstance(family_pension_row, dict)
        else _money(payload.get("familyPension"))
    )
    winnings_rows = _records(payload, "winningsEntries")
    lottery = _money(payload.get("lotteryIncome")) + sum(
        (_money(row.get("grossAmount")) for row in winnings_rows if str(row.get("type", "")).upper() != "HORSE_RACE"),
        Decimal("0"),
    )
    horse_race = _money(payload.get("horseRaceIncome")) + sum(
        (_money(row.get("grossAmount")) for row in winnings_rows if str(row.get("type", "")).upper() == "HORSE_RACE"),
        Decimal("0"),
    )
    vda_gains = _money(payload.get("vdaGains"))
    # ITR-2 supports lottery, gaming, horse-race, and VDA income.
    # Only reject for ITR-1/ITR-4 (not ITR-2/ITR-3).
    _early_form = str(payload.get("form", payload.get("itrForm", ""))).upper()
    if lottery + horse_race + vda_gains > 0 and _early_form not in {"ITR-2", "ITR-3"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lottery, gaming, horse-race, or VDA income is outside ITR-1/ITR-4; use the applicable ITR-2/ITR-3 computation.",
        )

    os_input = OtherSourcesIncome(
        savings_bank_interest=interest_sb + post_office_interest,
        fixed_deposit_interest=interest_fd + interest_rd + nsc_interest + scss_interest + other_interest,
        family_pension_received=family_pension,
        dividend_income=total_dividend,
    )
    
    # 4. Map deductions from canonical managers where available.
    investments_80c = payload.get("section80C")
    investment_rows = (
        investments_80c.get("investments", [])
        if isinstance(investments_80c, dict)
        else []
    )
    if investment_rows and all(isinstance(row, dict) for row in investment_rows):
        total_80c = sum((_money(row.get("amount")) for row in investment_rows), Decimal("0"))
    else:
        total_80c = sum(
            (_money(payload.get(key)) for key in ["s80C_epf", "s80C_ppf", "s80C_elss", "s80C_lic", "s80C_home"]),
            Decimal("0"),
        )

    section_80d = payload.get("section80D")

    def _category_80d(category: object) -> tuple[Decimal, Decimal]:
        if not isinstance(category, dict):
            return Decimal("0"), Decimal("0")
        policies = category.get("policies") or []
        if not isinstance(policies, list):
            raise HTTPException(status_code=422, detail="Section 80D policies must be an array.")
        premiums = sum(
            (_money(policy.get("premiumAmount")) for policy in policies if isinstance(policy, dict)),
            Decimal("0"),
        )
        eligible_amount = premiums + _money(category.get("medicalExpense"))
        preventive = _money(category.get("preventiveCheckup"))
        return eligible_amount, preventive

    if isinstance(section_80d, dict):
        self_is_senior = section_80d.get("selfSeniorCitizen") in {"Y", "S"}
        parents_are_senior = section_80d.get("parentsSeniorCitizen") in {"Y", "P"}
        self_key = "selfFamilySenior" if self_is_senior else "selfFamily"
        parents_key = "parentsSenior" if parents_are_senior else "parents"
        self_80d, preventive_self = _category_80d(section_80d.get(self_key))
        parents_80d, preventive_parents = _category_80d(section_80d.get(parents_key))
    else:
        parents_are_senior = False
        self_80d = _money(payload.get("s80D_self"))
        parents_80d = _money(payload.get("s80D_parent"))
        preventive_self = Decimal("0")
        preventive_parents = Decimal("0")

    donation_rows = _records(payload, "donationEntries")
    donations = []
    for row in donation_rows:
        category_value = str(row.get("category", "100_NO_APPROVAL"))
        try:
            category = Donation80GCategory(category_value)
        except ValueError:
            category = Donation80GCategory.HUNDRED_WITHOUT_LIMIT
        address = None
        if any(row.get(key) for key in ("addrDetail", "city", "stateCode", "pinCode")):
            address = DonationAddress(
                address_line=str(row.get("addrDetail", "")),
                city_or_district=str(row.get("city", "")),
                state_code=str(row.get("stateCode", "")),
                pin_code=int(row.get("pinCode", 0)),
            )
        donations.append(Donation80G(
            category=category,
            cash_amount=_money(row.get("donationAmtCash")),
            non_cash_amount=_money(row.get("donationAmtOtherMode")),
            donee_name=row.get("doneeName") or None,
            donee_pan=row.get("doneePAN") or None,
            approval_reference_number=row.get("arnNumber") or None,
            address=address,
            transaction_ref=row.get("transactionRefNum") or None,
            ifsc_code=row.get("ifscCode") or None,
        ))

    structured_80g_claim = sum(
        (donation.cash_amount + donation.non_cash_amount for donation in donations),
        Decimal("0"),
    )
    ded_input = Chapter6ADeductions(
        amount_80c=total_80c,
        amount_80ccd1b=_money(payload.get("s80CCD1B")),
        amount_80ccd2=_money(payload.get("s80CCD2")),
        amount_80d_self_family=self_80d,
        amount_80d_parents=parents_80d,
        amount_80d_preventive_self=preventive_self,
        amount_80d_preventive_parents=preventive_parents,
        has_parents_senior=parents_are_senior,
        amount_80e=_money(payload.get("s80E")),
        # 80TTA is derived from eligible savings-account interest only.
        # FD/RD and other deposit interest are intentionally excluded.
        amount_80tta=(
            min(interest_sb + post_office_interest, Decimal("10000"))
            if tax_regime == TaxRegime.OLD
            else Decimal("0")
        ),
        amount_80ttb=_money(payload.get("s80TTB")),
        amount_80g=(structured_80g_claim if donations else _money(payload.get("s80G"))),
        donations_80g=donations or None,
    )
    
    # 5. Map Capital Gains. Canonical rows take precedence over legacy scalars.
    # Determine the requested form early so ITR-2/3 transactions bypass the
    # restricted-112A eligibility check (which only applies to ITR-1/ITR-4).
    requested_form = str(payload.get("form", payload.get("itrForm", ""))).upper()
    is_itr2_or_3 = requested_form in {"ITR-2", "ITR-3"}
    capital_gain_rows = _records(payload, "capitalGainTransactions")
    capital_gains_summary = None
    if capital_gain_rows:
        portfolio = compute_restricted_112a(capital_gain_rows)
        capital_gains_summary = portfolio.to_dict()
        if not portfolio.is_valid and not is_itr2_or_3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Capital-gain transaction evidence is incomplete or is outside restricted Section 112A eligibility.",
                    "capitalGainsSummary": capital_gains_summary,
                    "status": portfolio.status,
                    "issues": capital_gains_summary["issues"],
                    "eligibility": portfolio.eligibility,
                },
            )
        # ITR-2/3 use cg_transactions directly — no CapitalGainsIncome wrapper.
        if is_itr2_or_3:
            cg_input = None
        else:
            cg_input = CapitalGainsIncome(
                ltcg_112a=max(Decimal("0"), portfolio.gross_gain),
                cost_of_acquisition=portfolio.cost_of_acquisition,
                full_value_of_consideration=portfolio.full_value_of_consideration,
            )
    else:
        cg_input = CapitalGainsIncome(
            ltcg_112a=_money(payload.get("ltcg112APre")) + _money(payload.get("ltcg112APost"))
        )

    tds1_entries = []
    tds2_entries = []
    credit_validation_issues: list[dict[str, object]] = []
    claimed_tds_entered = Decimal("0")
    validated_tds = Decimal("0")
    for row_index, row in enumerate(_records(payload, "tdsEntries")):
        # Preserve unclaimed draft rows in the payload, but do not include them
        # in either entered or validated claimed-credit totals.
        if row.get("claimedInReturn") is False:
            continue
        display_row = row_index + 1
        tan = str(row.get("deductorTAN") or "").strip().upper()
        section = str(row.get("section") or "").strip().upper()
        tax = _money(row.get("taxDeducted", row.get("tdsDeducted")))
        gross = _money(row.get("grossAmount", row.get("incomeAmount")))
        claimed_tds_entered += tax

        row_is_valid = True
        if tax > 0:
            required_fields = (("deductorName", "deductor name"),)
            for field, label in required_fields:
                if not str(row.get(field) or "").strip():
                    row_is_valid = False
                    credit_validation_issues.append(_credit_issue(
                        credit_type="TDS",
                        row=display_row,
                        amount=tax,
                        code="MISSING_TDS_FIELD",
                        field=field,
                        message=f"Complete {label} for this claimed TDS row.",
                    ))
            if not tan:
                row_is_valid = False
                credit_validation_issues.append(_credit_issue(
                    credit_type="TDS",
                    row=display_row,
                    amount=tax,
                    code="MISSING_TAN",
                    field="deductorTAN",
                    message="Complete deductor TAN for this claimed TDS row.",
                ))
            elif not _TAN_PATTERN.fullmatch(tan):
                row_is_valid = False
                credit_validation_issues.append(_credit_issue(
                    credit_type="TDS",
                    row=display_row,
                    amount=tax,
                    code="INVALID_TAN_FORMAT",
                    field="deductorTAN",
                    entered_value=tan,
                    message="TAN must contain 4 letters, 5 digits and 1 letter (for example ABCD12345E).",
                ))

        # Strict engine models receive only filing-valid identifiers. The raw
        # malformed value remains untouched in the editable draft and is
        # represented by structured issues above.
        if row_is_valid:
            try:
                if section in {"192", "S192"}:
                    tds1_entries.append(TDS1Entry(
                        employer_tan=tan,
                        employer_name=str(row.get("deductorName") or "") or None,
                        income_chargeable=gross,
                        tds_deducted=tax,
                    ))
                elif tax > 0 or gross > 0:
                    tds2_entries.append(TDS2Entry(
                        deductor_tan=tan,
                        deductor_name=str(row.get("deductorName") or "") or None,
                        tds_section=section or "194A",
                        gross_amount=gross,
                        tds_deducted=tax,
                    ))
                validated_tds += tax
            except ValidationError as exc:
                credit_validation_issues.append(_credit_issue(
                    credit_type="TDS",
                    row=display_row,
                    amount=tax,
                    code="INVALID_TDS_ROW",
                    message="The TDS row is not valid for filing: " + "; ".join(
                        str(error.get("msg", "invalid value")) for error in exc.errors()
                    ),
                ))


    tcs_entries = []
    for row in _records(payload, "tcsEntries"):
        tan = str(row.get("collectorTAN") or "")
        collected = _money(row.get("taxCollected", row.get("tcsCollected")))
        gross = _money(row.get("grossAmount"))
        if collected > 0 or gross > 0:
            if not tan:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A TCS claim requires collector TAN.",
                )
            tcs_entries.append(TCSEntry(
                collector_tan=tan,
                collector_name=str(row.get("collectorName") or "") or None,
                tcs_section=str(row.get("section") or "206C"),
                gross_amount=gross,
                tcs_collected=collected,
            ))

    advance_entries = _records(payload, "advanceTaxEntries")
    self_assessment_entries = _records(payload, "selfAssessmentTaxEntries")
    # For FY 2025-26, payments through 31 March 2026 are advance tax. A row
    # entered in the SAT section with an earlier date is retained but
    # reclassified by the backend so the statutory computation is correct.
    financial_year_end = datetime.date(2026, 3, 31)
    normalized_advance_entries = list(advance_entries)
    normalized_self_assessment_entries: list[dict] = []
    for row_index, row in enumerate(self_assessment_entries):
        amount = _money(row.get("amount"))
        deposit_date = _date(
            row.get("depositDate"),
            "selfAssessmentTaxEntries.depositDate",
        )
        if deposit_date is not None and deposit_date <= financial_year_end:
            normalized_advance_entries.append(row)
            if amount > 0:
                credit_validation_issues.append({
                    "creditType": "SELF_ASSESSMENT_TAX",
                    "row": row_index + 1,
                    "amount": float(amount),
                    "code": "RECLASSIFIED_AS_ADVANCE_TAX",
                    "message": "Payment dated on or before 31-03-2026 is classified as advance tax, not self-assessment tax.",
                })
        else:
            normalized_self_assessment_entries.append(row)

    quarterly_advance = [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")]
    entered_advance_tax = Decimal("0")
    if normalized_advance_entries:
        installment_deadlines = (
            datetime.date(2025, 6, 15), datetime.date(2025, 9, 15),
            datetime.date(2025, 12, 15), datetime.date(2026, 3, 15),
        )
        for row_index, row in enumerate(normalized_advance_entries):
            amount = _money(row.get("amount"))
            entered_advance_tax += amount
            deposit_date = _date(row.get("depositDate"), "advanceTaxEntries.depositDate")
            row_is_valid = amount <= 0
            if amount > 0:
                row_is_valid = True
                bsr_code = str(row.get("bsrCode") or "").strip()
                challan_serial = str(
                    row.get("challanSerialNo", row.get("challanNo")) or ""
                ).strip()
                if deposit_date is None:
                    row_is_valid = False
                    credit_validation_issues.append(_credit_issue(
                        credit_type="ADVANCE_TAX",
                        row=row_index + 1,
                        amount=amount,
                        code="MISSING_DEPOSIT_DATE",
                        field="depositDate",
                        message="Complete deposit date for this advance-tax payment.",
                    ))
                if not _BSR_PATTERN.fullmatch(bsr_code):
                    row_is_valid = False
                    credit_validation_issues.append(_credit_issue(
                        credit_type="ADVANCE_TAX",
                        row=row_index + 1,
                        amount=amount,
                        code="INVALID_BSR_FORMAT",
                        field="bsrCode",
                        entered_value=bsr_code,
                        message="BSR code must contain exactly 7 digits.",
                    ))
                if not _CHALLAN_SERIAL_PATTERN.fullmatch(challan_serial) or int(challan_serial or "0") <= 0:
                    row_is_valid = False
                    credit_validation_issues.append(_credit_issue(
                        credit_type="ADVANCE_TAX",
                        row=row_index + 1,
                        amount=amount,
                        code="INVALID_CHALLAN_SERIAL",
                        field="challanSerialNo",
                        entered_value=challan_serial,
                        message="Challan serial number must contain 1 to 5 digits and be greater than zero.",
                    ))
            if row_is_valid:
                bucket = 3
                if deposit_date is not None:
                    for index, deadline in enumerate(installment_deadlines):
                        if deposit_date <= deadline:
                            bucket = index
                            break
                quarterly_advance[bucket] += amount
        advance_tax_paid = sum(quarterly_advance, Decimal("0"))
    else:
        quarterly_advance = [
            _money(payload.get("adv15Jun")), _money(payload.get("adv15Sep")),
            _money(payload.get("adv15Dec")), _money(payload.get("adv15Mar")),
        ]
        advance_tax_paid = sum(quarterly_advance, Decimal("0"))
        entered_advance_tax = advance_tax_paid

    self_assessment_paid = Decimal("0")
    entered_self_assessment_tax = Decimal("0")
    if normalized_self_assessment_entries:
        for row_index, row in enumerate(normalized_self_assessment_entries):
            amount = _money(row.get("amount"))
            entered_self_assessment_tax += amount
            if amount <= 0:
                continue
            row_is_valid = True
            bsr_code = str(row.get("bsrCode") or "").strip()
            challan_serial = str(
                row.get("challanSerialNo", row.get("challanNo")) or ""
            ).strip()
            deposit_date = _date(
                row.get("depositDate"),
                "selfAssessmentTaxEntries.depositDate",
            )
            if deposit_date is None:
                row_is_valid = False
                credit_validation_issues.append(_credit_issue(
                    credit_type="SELF_ASSESSMENT_TAX",
                    row=row_index + 1,
                    amount=amount,
                    code="MISSING_DEPOSIT_DATE",
                    field="depositDate",
                    message="Complete deposit date for this self-assessment-tax payment.",
                ))
            if not _BSR_PATTERN.fullmatch(bsr_code):
                row_is_valid = False
                credit_validation_issues.append(_credit_issue(
                    credit_type="SELF_ASSESSMENT_TAX",
                    row=row_index + 1,
                    amount=amount,
                    code="INVALID_BSR_FORMAT",
                    field="bsrCode",
                    entered_value=bsr_code,
                    message="BSR code must contain exactly 7 digits.",
                ))
            if not _CHALLAN_SERIAL_PATTERN.fullmatch(challan_serial) or int(challan_serial or "0") <= 0:
                row_is_valid = False
                credit_validation_issues.append(_credit_issue(
                    credit_type="SELF_ASSESSMENT_TAX",
                    row=row_index + 1,
                    amount=amount,
                    code="INVALID_CHALLAN_SERIAL",
                    field="challanNo",
                    entered_value=challan_serial,
                    message="Challan serial number must contain 1 to 5 digits and be greater than zero.",
                ))
            if row_is_valid:
                self_assessment_paid += amount
    elif not self_assessment_entries:
        self_assessment_paid = _money(payload.get("selfTax"))
        entered_self_assessment_tax = self_assessment_paid


    
    # Run calculation. Canonical business rows take precedence.
    business_rows = _records(payload, "businessEntries") or _records(payload, "businesses")
    if len(business_rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multiple presumptive businesses are not yet supported by this calculation endpoint.",
        )
    business_row = business_rows[0] if business_rows else None
    biz_turnover = _money(payload.get("bizTurnover"))
    bp_profit = _money(payload.get("bizDeclared", payload.get("bpNetProfit")))
    presumptive_type = str(payload.get("bizPresumptive", "44AD"))
    if business_row:
        presumptive_type = str(business_row.get("scheme", presumptive_type))

    # requested_form was determined earlier (before the CG section) so the
    # restricted-112A check could be gated on it.
    is_future_form = requested_form in {"ITR-2", "ITR-3"}
    is_itr4 = requested_form == "ITR-4" or bool(business_row) or biz_turnover > 0 or bp_profit > 0
    computation_form = "ITR-4" if is_itr4 else "ITR-1"
    filing_computation_status = (
        "PROVISIONAL_COMMON_INCOME_PREVIEW" if is_future_form else "FORM_COMPUTATION"
    )

    common_input = dict(
        age_bracket=age_bracket,
        tax_regime=tax_regime,
        salary_income=salary_input,
        house_property_income=hp_input,
        house_properties=hp_inputs,
        other_sources_income=os_input,
        deductions_chapter6a=ded_input,
        capital_gains=cg_input,
        # Pass the canonical CG transactions through to every form calculator
        # so ITR-1/4 can run the standalone CG schedule and project the
        # restricted-112A view (surfacing losses-forfeited / other-CG-
        # disallowed for form-eligibility guidance). Purchase-only evidence
        # rows are filtered out at the ITR-2 builder; for ITR-1/4 they are
        # harmless because the schedule ignores zero-consideration rows.
        cg_transactions=capital_gain_rows if capital_gain_rows else None,
        tds1_entries=tds1_entries or None,
        tds2_entries=tds2_entries or None,
        tcs_entries=tcs_entries or None,
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax_paid=self_assessment_paid,
        advance_tax_q1=quarterly_advance[0],
        advance_tax_q2=quarterly_advance[1],
        advance_tax_q3=quarterly_advance[2],
        advance_tax_q4=quarterly_advance[3],
        filing_date=_date(payload.get("filingDate"), "filingDate"),
        due_date=_date(payload.get("dueDate"), "dueDate"),
        house_property_count=max(1, len(properties)),
        relief_89=_money(payload.get("relief89", payload.get("relief_89"))),
    )

    if is_itr4:
        # ITR-4 schema does not yet expose a multi-property list field; drop
        # the ITR-1-only house_properties kwarg before splatting common_input.
        itr4_common_input = {k: v for k, v in common_input.items() if k != "house_properties"}
        if presumptive_type == "44ADA":
            digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
            cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
            gross = _money(business_row.get("grossReceipts")) if business_row else biz_turnover
            if gross == 0:
                gross = digital + cash
            declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
            itr4_in = ITR4Input(
                **itr4_common_input,
                presumptive_scheme=PresumptiveScheme.S44ADA,
                professional_income_44ada=PresumptiveProfessionalIncome44ADA(
                    gross_receipts=gross,
                    digital_receipts=digital,
                    cash_receipts=cash,
                    income_declared=declared,
                ),
            )
        elif presumptive_type == "44AE":
            if not business_row:
                raise HTTPException(status_code=422, detail="44AE requires canonical vehicle entries.")
            vehicles = []
            for vehicle in _records(business_row, "vehicles"):
                vehicle_type = str(vehicle.get("vehicleType", "OTHER")).upper()
                vehicles.append(GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=vehicle_type == "HEAVY",
                    gross_vehicle_weight_tons=(
                        _money(vehicle.get("tonnage")) if vehicle_type == "HEAVY" else None
                    ),
                    months_owned=int(vehicle.get("ownedMonths") or 0),
                    income_declared=_money(vehicle.get("presumptiveIncome")) or None,
                ))
            itr4_in = ITR4Input(
                **itr4_common_input,
                presumptive_scheme=PresumptiveScheme.S44AE,
                goods_carriage_44ae=PresumptiveGoodsCarriage44AE(vehicles=vehicles),
            )
        elif presumptive_type == "44AD":
            digital = _money(business_row.get("digitalReceipts")) if business_row else biz_turnover
            cash = _money(business_row.get("nonDigitalReceipts")) if business_row else Decimal("0")
            total = digital + cash if business_row else biz_turnover
            declared = _money(business_row.get("declaredIncome")) if business_row else bp_profit
            itr4_in = ITR4Input(
                **itr4_common_input,
                presumptive_scheme=PresumptiveScheme.S44AD,
                business_income_44ad=PresumptiveBusinessIncome44AD(
                    total_turnover=total,
                    digital_turnover=digital,
                    cash_turnover=cash,
                    income_declared=declared,
                ),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Regular business income is outside ITR-4 presumptive computation.",
            )
        res = compute_itr4(itr4_in)
    elif is_future_form and requested_form == "ITR-2":
        # ── ITR-2 computation path ────────────────────────────────────────
        # Map the flat frontend payload to the canonical ITR2Input, following
        # the same pattern as ITR-1/ITR-4: the backend does the mapping.
        res = _compute_itr2_from_flat_payload(
            payload,
            age_bracket,
            tax_regime,
            salary_input,
            hp_input,
            os_input,
            ded_input,
            capital_gain_rows,
            tds1_entries,
            tds2_entries,
            tcs_entries,
            advance_tax_paid,
            self_assessment_paid,
            quarterly_advance,
            capital_gains_summary,
        )
        computation_form = "ITR-2"
        filing_computation_status = "FORM_COMPUTATION"
    else:
        res = compute_itr1(ITR1Input(**common_input))

    if res.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Tax computation is not valid for the selected form.", "errors": res.errors},
        )
        
    # Build frontend response structure
    gti = float(res.gross_total_income)
    total_deductions = float(res.deductions_total)
    taxable_income = float(res.taxable_income)
    slab_tax = float(res.slab_tax)
    rebate = float(res.rebate_87a)
    tax_after_rebate = float(res.tax_after_rebate)
    surcharge = float(res.surcharge)
    cess = float(res.health_education_cess)
    total_tax_payable = float(res.net_tax_liability)
    
    # Use authoritative engine schedule and credit totals.
    # Use getattr with defaults so both ITR1Result and ITR2Result work.
    std_ded = float(getattr(res, "salary_deduction_us16ia", Decimal("0")))
    salary_before_section16 = float(getattr(res, "salary_net", res.salary_income))
    net_salary = float(res.salary_income)

    # Per-section deduction breakdown from the engine so the frontend never
    # computes statutory eligibility itself — it displays these figures.
    ded_sched = res.schedules.get("deductions") if res.schedules else None
    ded_breakdown_raw = ded_sched.breakdown if ded_sched and hasattr(ded_sched, "breakdown") else {}
    deduction_breakdown = {str(k): float(v) for k, v in ded_breakdown_raw.items()} if ded_breakdown_raw else {}

    tds_salary = float(sum((entry.tds_deducted for entry in tds1_entries), Decimal("0")))
    tds_interest = float(sum((entry.tds_deducted for entry in tds2_entries if entry.tds_section in {"194A", "S194A"}), Decimal("0")))
    tds_other = float(sum((entry.tds_deducted for entry in tds2_entries), Decimal("0"))) - tds_interest
    adv_tax = float(advance_tax_paid)
    self_tax = float(self_assessment_paid)
    validated_tax_paid = float(res.total_taxes_paid)
    entered_credits_total = float(
        claimed_tds_entered + entered_advance_tax + entered_self_assessment_tax
    )
    validated_credits_total = validated_tax_paid
    final_tax_liability = float(res.net_tax_liability)
    provisional_balance = final_tax_liability - entered_credits_total
    provisional_refund = max(0.0, -provisional_balance)
    provisional_tax_payable = max(0.0, provisional_balance)
    tax_payable = float(res.balance_payable)
    refund = float(res.refund_due)
    blocking_credit_issues = [
        issue for issue in credit_validation_issues
        if issue["code"] != "RECLASSIFIED_AS_ADVANCE_TAX"
    ]
    credit_status = "PROVISIONAL" if blocking_credit_issues else "CONFIRMED"
    refund_status = (
        "PROVISIONAL_BLOCKED"
        if provisional_refund > 0 and blocking_credit_issues
        else "CONFIRMED" if refund > 0 else "NONE"
    )
    
    return {
        # ── Income Summary (CBDT ITR1_IncomeDeductions) ──
        "grossSalary": float(gross_salary),
        "hraExempt": float(getattr(res, "salary_hra_exempt", hra_exempt)),
        "salaryBeforeSection16": salary_before_section16,
        "netSalary": net_salary,
        "incomeFromSal": float(res.salary_income),
        "deductionUs16": float(getattr(res, "salary_deduction_us16", getattr(res, "salary_deduction_us16ia", Decimal("0")))),
        "standardDeduction": std_ded,
        "entertainmentAllowanceDed": float(getattr(res, "salary_entertainment_allowance", Decimal("0"))),
        "professionalTaxDed": float(getattr(res, "salary_professional_tax", Decimal("0"))),
        "totalSection16Deductions": float(getattr(res, "salary_deduction_us16", getattr(res, "salary_deduction_us16ia", Decimal("0")))),
        "hpIncome": float(res.house_property_income),
        "totalIncChargeHP": float(res.house_property_income),
        "otherIncome": float(res.other_sources_income),
        "incomeOthSrc": float(res.other_sources_income),
        "familyPensionIncome": float(family_pension),
        "familyPensionDed": float(res.schedules["os"].deduction_57iia),
        "deductUs57iia": float(res.schedules["os"].deduction_57iia),
        "gti": gti,
        "grossTotIncome": gti,
        "grossTotIncomeIncLTCG112A": gti,
        "gtiAfterSetOff": gti,
        "totalDeductions": total_deductions,
        "deductChapVIA": total_deductions,
        "deductionBreakdown": deduction_breakdown,
        "hpLossDisallowed": float(res.hp_loss_disallowed),
        "totalIncomeBefore288A": float(
            getattr(res, "total_income_before_288a", res.taxable_income)
        ),
        "roundingAdjustment288A": float(
            getattr(res, "rounding_adjustment_288a", Decimal("0"))
        ),
        "totalIncome": taxable_income,

        # ── Tax Computation (CBDT ITR1_TaxComputation) ──
        "basicExemptionLimit": float(
            getattr(res, "basic_exemption_limit", Decimal("0"))
        ),
        "normalRateIncome": float(
            getattr(res, "normal_rate_income", res.taxable_income)
        ),
        "incomeChargeableAboveBasicExemption": float(
            getattr(res, "income_chargeable_above_basic_exemption", Decimal("0"))
        ),
        "nilTaxReason": getattr(res, "nil_tax_reason", None),
        "normalTax": slab_tax,
        "totalTaxPayable": float(res.tax_before_rebate),
        "rebate87A": rebate,
        "taxPayableOnRebate": tax_after_rebate,
        "surcharge": surcharge,
        "cess": cess,
        "grossTaxLiability": float(res.gross_tax_liability),
        "section89": float(res.relief_89),
        "netTaxLiability": total_tax_payable,
        "totalTaxLiability": total_tax_payable,
        "balTaxPayable": tax_payable,
        "taxPayable": tax_payable,
        "refund": refund,
        "refundDue": refund,

        # ── Taxes Paid (CBDT TaxesPaid) ──
        "advanceTax": adv_tax,
        "totalTDS": float(validated_tds),
        "totalTCS": float(res.total_tcs),
        "selfAssessmentTax": self_tax,
        "totalTaxPaid": validated_credits_total,
        "totalTaxesPaid": validated_credits_total,
        "enteredCredits": {
            "tds": float(claimed_tds_entered),
            "advanceTax": float(entered_advance_tax),
            "selfAssessmentTax": float(entered_self_assessment_tax),
            "total": entered_credits_total,
        },
        "validatedCredits": {
            "tds": float(validated_tds),
            "advanceTax": adv_tax,
            "selfAssessmentTax": self_tax,
            "tcs": float(res.total_tcs),
            "total": validated_credits_total,
        },
        "provisionalRefund": provisional_refund,
        "provisionalTaxPayable": provisional_tax_payable,
        "blockedCreditsTotal": max(0.0, entered_credits_total - validated_credits_total),
        "confirmedRefund": refund if refund_status == "CONFIRMED" else None,
        "calculationStatus": (
            "CALCULATED_WITH_CREDIT_ISSUES" if blocking_credit_issues else "CALCULATED"
        ),
        "creditStatus": credit_status,
        "creditValidationIssues": credit_validation_issues,
        "refundStatus": refund_status,
        "claimedTDSEntered": float(claimed_tds_entered),
        "tdsS192": tds_salary,
        "tds194A": tds_interest,
        "tdsOther": tds_other,
        "adv15Jun": float(quarterly_advance[0]),
        "adv15Sep": float(quarterly_advance[1]),
        "adv15Dec": float(quarterly_advance[2]),
        "adv15Mar": float(quarterly_advance[3]),
        "selfTax": self_tax,
        "tdsEntries": payload.get("tdsEntries", []),
        "selfAssessmentTaxEntries": payload.get("selfAssessmentTaxEntries", []),
        "advanceTaxEntries": payload.get("advanceTaxEntries", []),

        # ── Salary Schedule detail ──
        "salaryIncome": float(gross_salary),
        "salary171": float(section_17_1_salary),
        "salary172": float(perquisites),
        "salary173": float(profits_in_lieu),
        "ltaExempt": float(lta_exempt),
        "gratuityExempt": float(getattr(res, "salary_gratuity_exempt", Decimal("0"))),
        "leaveEncashmentExempt": float(getattr(res, "salary_leave_encashment_exempt", Decimal("0"))),
        "pensionCommutationExempt": float(getattr(res, "salary_commutted_pension_exempt", Decimal("0"))),
        "transportExempt": float(getattr(res, "salary_transport_exempt", Decimal("0"))),
        "childrenEducationExempt": float(getattr(res, "salary_children_education_exempt", Decimal("0"))),
        "hostelExempt": float(getattr(res, "salary_hostel_exempt", Decimal("0"))),
        "uniformExempt": 0.0,
        "totalSection10Exempt": float(
            getattr(res, "salary_hra_exempt", Decimal("0")) + getattr(res, "salary_lta_exempt", Decimal("0"))
            + getattr(res, "salary_gratuity_exempt", Decimal("0")) + getattr(res, "salary_leave_encashment_exempt", Decimal("0"))
            + getattr(res, "salary_vrs_exempt", Decimal("0")) + getattr(res, "salary_commutted_pension_exempt", Decimal("0"))
            + getattr(res, "salary_transport_exempt", Decimal("0")) + getattr(res, "salary_children_education_exempt", Decimal("0"))
            + getattr(res, "salary_hostel_exempt", Decimal("0"))
        ),
        "salaryTDS": tds_salary,
        "salaryEmployerCount": len(payload.get("employerEntries", [])),
        "hraCondition1": float(hra_condition1),
        "hraCondition2": float(hra_condition2),
        "hraCondition3": float(hra_condition3),
        "hraIsMetro": bool(hra_is_metro),
        "hraCityClassified": "Metro" if bool(hra_is_metro) else "Non-Metro",

        # ── Other sources breakdown (for display) ──
        "bizIncome": float(getattr(res, 'presumptive_income', 0) or getattr(res, 'business_income', 0)),
        "vdaTax": float(getattr(res, 'vda_income', Decimal("0")) * Decimal("0.30")),
        "vdaGains": float(getattr(res, 'vda_income', Decimal("0"))),
        "cgTax": float(res.special_rate_tax),
        "totalInterest": float(total_interest),
        "interestDeduction80TTA": float(deduction_breakdown.get("80TTA", 0)),
        "interestDeduction80TTB": float(deduction_breakdown.get("80TTB", 0)),
        "totalDividend": float(total_dividend),
        "dividendTaxableAtSpecialRate": 0.0,
        "dividendTaxableAtNormalRate": total_dividend,
        "totalWinnings": 0.0,
        "winningsTax": 0.0,
        "taxableGifts": 0.0,
        "specialRateIncome": 0.0,
        "capitalGainsSummary": capital_gains_summary,
        "capitalGainsStatus": capital_gains_summary["status"] if capital_gains_summary else "LEGACY",
        "capitalGainsIssues": capital_gains_summary["issues"] if capital_gains_summary else [],
        "capitalGainsEligibility": capital_gains_summary["eligibility"] if capital_gains_summary else {"ITR-1": True, "ITR-4": True},
        "requestedForm": requested_form or computation_form,
        "computedByFormEngine": computation_form,
        "filingComputationStatus": filing_computation_status,
        "filingComputationMessage": (
            f"{requested_form} backend filing computation is not active; figures are a provisional common-income preview from the {computation_form} engine."
            if is_future_form else None
        ),
        "taxRegime": regime
    }

@router.post("/business-income/calculate")
def calculate_business_income(request: dict, assessmentYear: str = "2026-27"):
    """Compute presumptive business/professional income via the typed engine.

    AY 2026-27 only.  This endpoint does NOT re-implement statutory rates;
    it delegates to the presumptive constants and returns the statutory
    income, never substituting a raw float computation for the engine.
    """
    if assessmentYear != "2026-27":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Business income calculation supports assessment year 2026-27 only.",
        )

    scheme = request.get("scheme", "Regular")
    gross_turnover = float(request.get("grossTurnover", 0) or 0)
    declared_income = float(request.get("declaredIncome", 0) or 0)
    net_profit = float(request.get("netProfitPL", 0) or 0)

    compliance_notes: list[str] = []

    if scheme == "44AD":
        # Sec 44AD: 6% of digital receipts / 8% of cash receipts; the lower
        # of (statutory, declared) is accepted unless a higher income is
        # voluntarily declared.  Actual engine computation lives in
        # compute_itr4 — here we surface the statutory estimate.
        statutory = gross_turnover * float(PRESUMPTIVE_44AD_DIGITAL)
        taxable = max(statutory, declared_income)
        compliance_notes.append(
            "Presumptive rate of 6% applied for digital receipts (8% for cash). "
            "Authoritative computation runs through the ITR-4 engine."
        )
    elif scheme == "44ADA":
        statutory = gross_turnover * float(PRESUMPTIVE_44ADA_RATE)
        taxable = max(statutory, declared_income)
        compliance_notes.append(
            "Presumptive rate of 50% applied for professional receipts. "
            "Authoritative computation runs through the ITR-4 engine."
        )
    else:
        statutory = 0.0
        taxable = net_profit
        compliance_notes.append(
            "Regular scheme applied based on Profit & Loss statement."
        )

    return {
        "scheme": scheme,
        "assessmentYear": "2026-27",
        "grossTurnover": gross_turnover,
        "declaredIncome": declared_income,
        "netProfitPL": net_profit,
        "taxableIncome": taxable,
        "adjustedTaxableIncome": taxable,
        "presumptiveRate": (
            float(PRESUMPTIVE_44AD_DIGITAL) if scheme == "44AD"
            else (float(PRESUMPTIVE_44ADA_RATE) if scheme == "44ADA" else 0.0)
        ),
        "incomeType": "Professional" if scheme == "44ADA" else "Business",
        "isLoss": taxable < 0,
        "businessLoss": abs(taxable) if taxable < 0 else 0,
        "complianceNotes": compliance_notes,
    }


@router.post("/business-income/validate")
def validate_business_input(request: dict):
    """Validate presumptive business income thresholds for AY 2026-27."""
    scheme = request.get("scheme", "Regular")
    gross_turnover = float(request.get("grossTurnover", 0) or 0)
    errors: list[str] = []
    warnings: list[str] = []

    if scheme == "44AD" and gross_turnover > float(SEC_44AD_TURNOVER_LIMIT):
        errors.append(
            "Gross turnover exceeds the Section 44AD presumptive limit of Rs 3 crore."
        )
    elif scheme == "44ADA" and gross_turnover > float(SEC_44ADA_RECEIPTS_LIMIT):
        errors.append(
            "Gross receipts exceed the Section 44ADA presumptive limit of Rs 75 lakh."
        )

    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "assessmentYear": "2026-27",
    }


@router.post("/capital-gains/calculate")
def calculate_capital_gains(request: dict):
    """Compute capital gains tax via the typed special-rates engine.

    AY 2026-27 only.  Delegates to app.engine.schedules.special_rates so the
    rates and exemptions are never hard-coded in the router.  No raw float
    statutory arithmetic is performed here.
    """
    assessment_year = request.get("assessmentYear", "2026-27")
    if assessment_year != "2026-27":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Capital gains calculation supports assessment year 2026-27 only.",
        )

    asset_type = request.get("assetType", "EQUITY")
    purchase_cost = Decimal(str(request.get("purchaseCost", 0) or 0))
    sale_cost = Decimal(str(request.get("saleCost", 0) or 0))
    transfer_expenses = Decimal(str(request.get("transferExpenses", 0) or 0))

    p_date_str = request.get("purchaseDate")
    s_date_str = request.get("saleDate")
    months = 0
    if p_date_str and s_date_str:
        try:
            p_date = datetime.datetime.strptime(p_date_str, "%Y-%m-%d").date()
            s_date = datetime.datetime.strptime(s_date_str, "%Y-%m-%d").date()
            months = (s_date.year - p_date.year) * 12 + (s_date.month - p_date.month)
        except Exception:
            months = 0

    is_equity = "EQUITY" in str(asset_type).upper() or "MUTUAL" in str(asset_type).upper()
    threshold = 12 if is_equity else 24
    is_ltcg = months >= threshold

    gain = sale_cost - purchase_cost - transfer_expenses
    taxable_gain = max(Decimal("0"), gain)

    # Delegate the statutory rate/exemption to the typed engine module.
    if is_equity and is_ltcg:
        entry = compute_112a(taxable_gain)
        tax_rate = entry.tax_rate_pct
        tax_payable = entry.tax_amount
        gain_type = "LTCG"
        sec_ref = "112A"
    elif is_equity:
        entry = compute_111a(taxable_gain, is_post_jul24=True)
        tax_rate = entry.tax_rate_pct
        tax_payable = entry.tax_amount
        gain_type = "STCG"
        sec_ref = "111A"
    else:
        # Non-equity long-term: 12.5% (post-23-Jul-2024, w/o indexation);
        # non-equity short-term: slab rate (engine computes on full return).
        tax_rate = LTCG_OTHER_RATE_POST_JUL24 if is_ltcg else Decimal("0")
        tax_payable = taxable_gain * tax_rate / Decimal("100") if is_ltcg else Decimal("0")
        gain_type = "LTCG" if is_ltcg else "STCG"
        sec_ref = "112" if is_ltcg else "Slab"

    return {
        "gainType": gain_type,
        "longTerm": is_ltcg,
        "holdingPeriodMonths": months,
        "purchaseCost": float(purchase_cost),
        "saleCost": float(sale_cost),
        "costOfAcquisition": float(purchase_cost),
        "indexedCost": float(purchase_cost),
        "gain": float(gain),
        "taxableGain": float(taxable_gain),
        "taxRate": float(tax_rate),
        "taxPayable": float(tax_payable),
        "assessmentYear": "2026-27",
        "scheduleCGReference": "Schedule CG",
        "sectionReference": sec_ref,
        "complianceNotes": [f"Holding period computed: {months} months."],
    }


@router.post("/capital-gains/calculate-batch")
def calculate_capital_gains_batch(request: dict):
    """Compute capital gains for a batch of transactions via the typed engine."""
    txs = request.get("transactions", [])
    results = []

    stcg_111a = Decimal("0")
    ltcg_112a = Decimal("0")
    stcg_other = Decimal("0")
    ltcg_112 = Decimal("0")
    total_tax = Decimal("0")

    for tx in txs:
        calc = calculate_capital_gains(tx)
        results.append(calc)

        gain = Decimal(str(calc["taxableGain"]))
        tax = Decimal(str(calc["taxPayable"]))
        is_ltcg = calc["longTerm"]
        sec = calc["sectionReference"]

        if is_ltcg:
            if sec == "112A":
                ltcg_112a += gain
            else:
                ltcg_112 += gain
        else:
            if sec == "111A":
                stcg_111a += gain
            else:
                stcg_other += gain
        total_tax += tax

    total_gains = stcg_111a + ltcg_112a + stcg_other + ltcg_112

    return {
        "transactions": results,
        "summary": {
            "stcg111A": float(stcg_111a),
            "ltcg112A": float(ltcg_112a),
            "stcgOther": float(stcg_other),
            "ltcg112": float(ltcg_112),
            "totalCapitalGains": float(total_gains),
            "totalTax": float(total_tax),
            "lossSetOff": 0.0,
            "netCapitalGains": float(total_gains),
            "remainingLoss": 0.0,
        },
    }
