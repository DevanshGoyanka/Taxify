"""Canonical restricted Section 112A transaction models for ITR-1 and ITR-4."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CapitalGainRecordKind(str, Enum):
    """Role of a row in the canonical capital-gains workspace."""

    EVIDENCE = "EVIDENCE"
    TRANSACTION = "TRANSACTION"


class CapitalGainEvidenceSide(str, Enum):
    """Economic side represented by an imported evidence row."""

    PURCHASE = "PURCHASE"
    SALE = "SALE"
    UNKNOWN = "UNKNOWN"


class Section112AAssetType(str, Enum):
    """Asset classes eligible for the restricted Section 112A workflow."""

    LISTED_EQUITY = "LISTED_EQUITY"
    EQUITY_ORIENTED_MUTUAL_FUND = "EQUITY_ORIENTED_MUTUAL_FUND"
    BUSINESS_TRUST_UNIT = "BUSINESS_TRUST_UNIT"


class Section112ATransaction(BaseModel):
    """Canonical, extensible evidence model for one Section 112A disposal.

    Optional evidence fields intentionally remain optional at model parsing time.
    The restricted computation service reports missing or inconsistent evidence as
    structured issues, allowing callers to retain incomplete imported rows.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transaction_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("transaction_id", "transactionId", "id")
    )
    record_kind: CapitalGainRecordKind = Field(
        default=CapitalGainRecordKind.TRANSACTION,
        validation_alias=AliasChoices("record_kind", "recordKind"),
    )
    evidence_side: Optional[CapitalGainEvidenceSide] = Field(
        default=None,
        validation_alias=AliasChoices("evidence_side", "evidenceSide"),
    )
    asset_type: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("asset_type", "assetType")
    )
    description: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("description", "assetDescription", "shareName")
    )
    acquisition_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices(
            "acquisition_date",
            "acquisitionDate",
            "purchaseDate",
            "dateOfAcquisition",
        ),
    )
    transfer_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices(
            "transfer_date",
            "transferDate",
            "saleDate",
            "dateOfTransfer",
        ),
    )
    sale_value: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("sale_value", "saleValue", "saleCost", "fullValueOfConsideration")
    )
    actual_cost: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("actual_cost", "actualCost", "purchaseCost", "costOfAcquisition")
    )
    transfer_expenses: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("transfer_expenses", "transferExpenses", "expenses")
    )
    stt_paid_on_acquisition: Optional[bool] = Field(
        default=None, validation_alias=AliasChoices("stt_paid_on_acquisition", "sttPaidOnAcquisition", "sttAcquisition")
    )
    stt_paid_on_transfer: Optional[bool] = Field(
        default=None, validation_alias=AliasChoices("stt_paid_on_transfer", "sttPaidOnTransfer", "sttTransfer")
    )
    recognized_exchange: Optional[bool] = Field(
        default=None, validation_alias=AliasChoices("recognized_exchange", "recognizedExchange", "soldOnRecognizedExchange")
    )
    exchange_name: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("exchange_name", "exchangeName")
    )
    isin: Optional[str] = Field(default=None, validation_alias=AliasChoices("isin", "isinCode"))
    quantity: Optional[Decimal] = Field(default=None)
    ais_holding_period: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ais_holding_period", "aisHoldingPeriod"),
    )
    stt_amount: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("stt_amount", "sttAmount")
    )
    fmv_31_jan_2018: Optional[Decimal] = Field(
        default=None, validation_alias=AliasChoices("fmv_31_jan_2018", "fmv31Jan2018", "fmvAsOn31Jan2018", "fmvJan2018")
    )
    raw_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)


class Section112AIssueCode(str, Enum):
    """Stable machine-readable issue codes for restricted computation."""

    INVALID_TRANSACTION = "INVALID_TRANSACTION"
    MISSING_ACQUISITION_DATE = "MISSING_ACQUISITION_DATE"
    MISSING_TRANSFER_DATE = "MISSING_TRANSFER_DATE"
    INVALID_DATE_ORDER = "INVALID_DATE_ORDER"
    UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"
    MISSING_SALE_VALUE = "MISSING_SALE_VALUE"
    INVALID_SALE_VALUE = "INVALID_SALE_VALUE"
    MISSING_ACTUAL_COST = "MISSING_ACTUAL_COST"
    INVALID_ACTUAL_COST = "INVALID_ACTUAL_COST"
    MISSING_FMV_31_JAN_2018 = "MISSING_FMV_31_JAN_2018"
    INVALID_FMV_31_JAN_2018 = "INVALID_FMV_31_JAN_2018"
    INVALID_TRANSFER_EXPENSES = "INVALID_TRANSFER_EXPENSES"
    MISSING_STT_ACQUISITION = "MISSING_STT_ACQUISITION"
    MISSING_STT_TRANSFER = "MISSING_STT_TRANSFER"
    MISSING_RECOGNIZED_EXCHANGE = "MISSING_RECOGNIZED_EXCHANGE"
    NOT_LONG_TERM = "NOT_LONG_TERM"
    SECTION_112A_LOSS = "SECTION_112A_LOSS"
    AGGREGATE_LIMIT_EXCEEDED = "AGGREGATE_LIMIT_EXCEEDED"
