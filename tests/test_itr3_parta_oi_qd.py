"""Focused tests for exact PARTA_OI and PARTA_QD mappings."""

from __future__ import annotations

from decimal import Decimal

import pytest
from jsonschema import Draft4Validator

from app.engine.itd.itr3 import _parta_oi, _parta_qd
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr3 import ITR3Input, ITR3PartAQD, ITR3PartAOI, ITR3TradingQDRow


def test_parta_qd_maps_official_nested_quantitdet() -> None:
    """Trading quantitative details use the exact CBDT nesting."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_qd=ITR3PartAQD(TradingConcern=[ITR3TradingQDRow(
            ItemName="Rice",
            UnitOfMeasure="101",
            OpeningStock=Decimal("1"),
            PurchaseQty=Decimal("2"),
            SaleQty=Decimal("3"),
            ClgStock=Decimal("0"),
            AnyShortExces=Decimal("0"),
        )]),
    )
    assert _parta_qd(typed) == {"TradingConcern": {"QuantitDet": [{
        "ItemName": "Rice", "UnitOfMeasure": "101", "OpeningStock": 1,
        "PurchaseQty": 2, "SaleQty": 3, "ClgStock": 0, "AnyShortExces": 0,
    }]}}


def test_parta_oi_uses_typed_decimal_boundary_conversion() -> None:
    """PARTA_OI monetary Decimals become official integer rupees."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_oi=ITR3PartAOI(ProfDeviatDueAcctMeth=Decimal("12.00")),
    )
    assert _parta_oi(typed)["ProfDeviatDueAcctMeth"] == 12


def _parta_oi_validator() -> Draft4Validator:
    """Build a self-contained validator for the referenced OI definition."""
    full_schema = get_itr3_schema_validator().schema
    schema = dict(full_schema["definitions"]["PARTA_OI"])
    schema["definitions"] = full_schema["definitions"]
    return Draft4Validator(schema)


def test_parta_oi_amount_groups_are_distinctly_typed_not_a_shared_dict() -> None:
    """Schedule 9 fix: sections 36/37/40/40A/43B(x2)/excise-outstanding each
    had been given the SAME generic OIAmountGroup class, which carried the
    union of every group's own field names (~48 fields). Dumping any one
    group therefore emitted every other group's fields too, unconditionally
    failing the official schema's additionalProperties:false constraint for
    every group except (coincidentally) section 36. Confirm each group now
    accepts only its own official fields and rejects a sibling group's."""
    from app.schemas.itr3 import AmtDisallUs37Group, AmtDisallUs36Group, AmtDisallUs40Group

    # A field genuinely belonging to section 36 must be rejected by section 37's group.
    with pytest.raises(Exception):
        AmtDisallUs37Group(StkInsurPrem=100)
    with pytest.raises(Exception):
        AmtDisallUs40Group(BusOrProfessnExp=100)
    with pytest.raises(Exception):
        AmtDisallUs36Group(TotAmtDisallUs37=100)


def test_parta_oi_full_schema_valid_with_distinct_per_block_data() -> None:
    """Every PARTA_OI sub-block populated with real, block-specific data
    validates against the complete official definition -- the exact scenario
    that failed for 6 of 7 blocks (and even the 7th, section 36, once its
    own leftover cross-block fields were included) before this fix."""
    from app.schemas.itr3 import (
        OIStockValuation, OINoCredit, AmtDisallUs36Group, AmtDisallUs37Group,
        AmtDisallUs40Group, AmtDisallUs40AGroup, OIAmt43BGroup, OIAmtUs43B,
        OIExciseCustomsVATOutstandingGroup, OIExciseCustomsVATOutstanding,
    )

    oi = ITR3PartAOI(
        MethodOfAcct="MERC", ChangeInAcctMethFlg="N",
        ProfDeviatDueAcctMeth=Decimal("-5000"), DecProOrIncLossUs145_2=Decimal("2000"),
        MethodOfValClgStk=OIStockValuation(
            ValRawMaterial="2", ValFinishedGoods="1", ChngStockValMetFlg="Y",
            EffectOnPL=Decimal("1500"), DecProOrIncLossUs145_A=Decimal("500"),
        ),
        NoCredToPLAmt=OINoCredit(
            Section28Items=Decimal("1000"), ProformaCreditsDue=Decimal("2000"),
            PrevYrEscalClaim=Decimal("3000"), OthItemInc=Decimal("4000"),
            CapReceipt=Decimal("5000"), TotNoCredToPLAmt=Decimal("15000"),
        ),
        AmtDisallUs36=AmtDisallUs36Group(StkInsurPrem=Decimal("1000"), TotAmtDisallUs36=Decimal("1000")),
        AmtDisallUs37=AmtDisallUs37Group(CapitalNatureExp=Decimal("2000"), TotAmtDisallUs37=Decimal("2000")),
        AmtDisallUs40=AmtDisallUs40Group(WTAmt=Decimal("3000"), TotAmtDisallUs40=Decimal("3000")),
        AmtDisallUs40A=AmtDisallUs40AGroup(AmtGT20kCash=Decimal("4000"), TotAmtDisallUs40A=Decimal("4000")),
        AmtDisallUs43BPyNowAll=OIAmt43BGroup(AmtUs43B=OIAmtUs43B(TaxDutyCesAmt=Decimal("5000"), TotAmtUs43b=Decimal("5000"))),
        AmtDisall43B=OIAmt43BGroup(AmtUs43B=OIAmtUs43B(LeaveEncashPayable=Decimal("6000"), TotAmtUs43b=Decimal("6000"))),
        AmtExciseCustomsVATOutstanding=OIExciseCustomsVATOutstandingGroup(
            ExciseCustomsVAT=OIExciseCustomsVATOutstanding(CentralGoodServiceTax=Decimal("7000"), TotExciseCustomsVAT=Decimal("7000"))
        ),
        DeemedProfUs33ABs=Decimal("8000"), ProfTaxAmtUs41=Decimal("9000"),
        PriorAmtIncCrDrPL=Decimal("-1000"), AmountOfExpDisAllwUs14A=Decimal("10000"),
        InterestDisAllowUs23SMEAct=Decimal("500"), ScheduleTPSAFlg="N",
    )
    typed = ITR3Input(age_bracket="below_60", tax_regime="new", parta_oi=oi)
    payload = _parta_oi(typed)

    # Each group carries only its own fields -- no cross-block pollution.
    assert set(payload["AmtDisallUs37"].keys()) == {
        "CapitalNatureExp", "PersonalExp", "BusOrProfessnExp", "PoliticPartyExp",
        "LawVoilatPenalExp", "OthPenalFineExp", "OffenceExp", "ContigentLiability",
        "OthAmtNotAllowUs37", "TotAmtDisallUs37",
    }
    assert payload["AmtDisallUs36"]["StkInsurPrem"] == 1000
    assert payload["AmtDisallUs43BPyNowAll"]["AmtUs43B"]["TaxDutyCesAmt"] == 5000
    assert payload["AmtExciseCustomsVATOutstanding"]["ExciseCustomsVAT"]["CentralGoodServiceTax"] == 7000
    assert payload["MethodOfValClgStk"]["ValRawMaterial"] == "2"
    assert payload["ProfDeviatDueAcctMeth"] == -5000

    errors = list(_parta_oi_validator().iter_errors(payload))
    assert errors == []


def _parta_qd_validator() -> Draft4Validator:
    """Build a self-contained validator for the referenced QD definition."""
    full_schema = get_itr3_schema_validator().schema
    schema = dict(full_schema["definitions"]["PARTA_QD"])
    schema["definitions"] = full_schema["definitions"]
    return Draft4Validator(schema)

def test_parta_qd_mapping_is_schema_valid() -> None:
    """A fully populated QD branch validates against the official definition."""
    typed = ITR3Input(
        age_bracket="below_60",
        tax_regime="new",
        parta_qd=ITR3PartAQD(TradingConcern=[ITR3TradingQDRow(
            ItemName="Rice", UnitOfMeasure="101", OpeningStock=1,
            PurchaseQty=2, SaleQty=3, ClgStock=0, AnyShortExces=0,
        )]),
    )
    document = _parta_qd(typed)
    errors = list(_parta_qd_validator().iter_errors(document))
    assert errors == []



def test_parta_qd_rejects_unknown_unit_code() -> None:
    """Typed QD input rejects an unofficial unit code at construction time --
    UnitOfMeasure is now a Literal of the exact official 23-value enum, so
    this fails closed immediately rather than only being caught later by
    schema validation."""
    with pytest.raises(Exception):
        ITR3TradingQDRow(
            ItemName="Rice", UnitOfMeasure="000", OpeningStock=1,
            PurchaseQty=2, SaleQty=3, ClgStock=0, AnyShortExces=0,
        )


def test_parta_qd_manufacturing_concern_requires_both_raw_material_and_finished_product() -> None:
    """Schedule 10 fix: the official schema requires ManfactrConcern to carry
    BOTH RawMaterial and FinishrByProd whenever it is present at all -- a
    return with only one side's rows previously reached the JSON missing the
    other required key entirely, failing official schema validation."""
    from app.schemas.itr3 import ITR3RawMaterialQDRow, ITR3FinishedProductQDRow

    raw_only = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        parta_qd=ITR3PartAQD(RawMaterial=[ITR3RawMaterialQDRow(
            ItemName="Steel", UnitOfMeasure="102", OpeningStock=10, PurchaseQty=5,
            SaleQty=0, ClgStock=12, AnyShortExces=0,
        )]),
    )
    with pytest.raises(ValueError, match="FinishrByProd"):
        _parta_qd(raw_only)

    finished_only = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        parta_qd=ITR3PartAQD(FinishrByProd=[ITR3FinishedProductQDRow(
            ItemName="Bolts", UnitOfMeasure="107", OpeningStock=100, PurchaseQty=0,
            SaleQty=50, ClgStock=50, AnyShortExces=0,
        )]),
    )
    with pytest.raises(ValueError, match="RawMaterial"):
        _parta_qd(finished_only)

    both = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        parta_qd=ITR3PartAQD(
            RawMaterial=[ITR3RawMaterialQDRow(ItemName="Steel", UnitOfMeasure="102", OpeningStock=10, PurchaseQty=5, SaleQty=0, ClgStock=12, AnyShortExces=0)],
            FinishrByProd=[ITR3FinishedProductQDRow(ItemName="Bolts", UnitOfMeasure="107", OpeningStock=100, PurchaseQty=0, SaleQty=50, ClgStock=50, AnyShortExces=0)],
        ),
    )
    payload = _parta_qd(both)
    assert "RawMaterial" in payload["ManfactrConcern"]
    assert "FinishrByProd" in payload["ManfactrConcern"]
    errors = list(_parta_qd_validator().iter_errors(payload))
    assert errors == []
