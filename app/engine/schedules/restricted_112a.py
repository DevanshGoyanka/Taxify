"""Restricted Section 112A portfolio computation for ITR-1 and ITR-4."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from pydantic import ValidationError

from app.schemas.capital_gains import (
    CapitalGainEvidenceSide,
    CapitalGainRecordKind,
    Section112AAssetType,
    Section112AIssueCode,
    Section112ATransaction,
)

_RESTRICTED_LIMIT = Decimal("125000")
_GRANDFATHERING_DATE = date(2018, 1, 31)
_ASSET_ALIASES = {
    "EQUITY": Section112AAssetType.LISTED_EQUITY,
    "LISTED_EQUITY": Section112AAssetType.LISTED_EQUITY,
    "LISTED_EQUITY_SHARE": Section112AAssetType.LISTED_EQUITY,
    "MUTUAL_FUND": Section112AAssetType.EQUITY_ORIENTED_MUTUAL_FUND,
    "EQUITY_MUTUAL_FUND": Section112AAssetType.EQUITY_ORIENTED_MUTUAL_FUND,
    "EQUITY_ORIENTED_MUTUAL_FUND": Section112AAssetType.EQUITY_ORIENTED_MUTUAL_FUND,
    "BUSINESS_TRUST": Section112AAssetType.BUSINESS_TRUST_UNIT,
    "BUSINESS_TRUST_UNIT": Section112AAssetType.BUSINESS_TRUST_UNIT,
}



@dataclass(frozen=True)
class Section112AIssue:
    """One structured evidence or eligibility failure."""

    code: Section112AIssueCode
    message: str
    row: int | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible issue representation."""
        data = asdict(self)
        data["code"] = self.code.value
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class Section112ATransactionResult:
    """Computed facts for one complete, eligible Section 112A transaction."""

    row: int
    asset_type: Section112AAssetType
    holding_period_days: int
    holding_period_months: int
    sale_value: Decimal
    actual_cost: Decimal
    deemed_cost: Decimal
    transfer_expenses: Decimal
    gain: Decimal
    grandfathering_applied: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible transaction result."""
        data = asdict(self)
        data["asset_type"] = self.asset_type.value
        for key in ("sale_value", "actual_cost", "deemed_cost", "transfer_expenses", "gain"):
            data[key] = float(data[key])
        return data


@dataclass(frozen=True)
class Section112APortfolioResult:
    """Aggregate restricted Section 112A computation and form eligibility."""

    status: str
    transactions: tuple[Section112ATransactionResult, ...] = ()
    issues: tuple[Section112AIssue, ...] = ()
    evidence_count: int = 0
    evidence_purchase_total: Decimal = Decimal("0")
    evidence_sale_total: Decimal = Decimal("0")
    gross_gain: Decimal = Decimal("0")
    full_value_of_consideration: Decimal = Decimal("0")
    cost_of_acquisition: Decimal = Decimal("0")
    transfer_expenses: Decimal = Decimal("0")
    eligibility: dict[str, bool] = field(default_factory=lambda: {"ITR-1": True, "ITR-4": True})

    @property
    def is_valid(self) -> bool:
        """Return whether tax computation may consume this portfolio."""
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        """Return the public capital-gains summary contract."""
        return {
            "status": self.status,
            "gross112AGain": float(self.gross_gain),
            "fullValueOfConsideration": float(self.full_value_of_consideration),
            "costOfAcquisition": float(self.cost_of_acquisition),
            "transferExpenses": float(self.transfer_expenses),
            "transactionCount": len(self.transactions),
            "evidenceCount": self.evidence_count,
            "evidencePurchaseTotal": float(self.evidence_purchase_total),
            "evidenceSaleTotal": float(self.evidence_sale_total),
            "evidenceCompatibility": "POTENTIALLY_SECTION_112A",
            "transactions": [item.to_dict() for item in self.transactions],
            "issues": [issue.to_dict() for issue in self.issues],
            "eligibility": self.eligibility,
        }


def _issue(code: Section112AIssueCode, message: str, row: int, field_name: str | None = None) -> Section112AIssue:
    return Section112AIssue(code=code, message=message, row=row, field=field_name)


def compute_restricted_112a(raw_transactions: Iterable[dict[str, Any]]) -> Section112APortfolioResult:
    """Validate and compute canonical transactions under restricted Section 112A.

    Args:
        raw_transactions: Raw JSON object rows. Incomplete source evidence is not
            mutated or discarded; failures are returned as structured issues.

    Returns:
        Portfolio computation suitable for ITR-1/ITR-4 projection.
    """
    computed: list[Section112ATransactionResult] = []
    issues: list[Section112AIssue] = []
    evidence_count = 0
    evidence_purchase_total = Decimal("0")
    evidence_sale_total = Decimal("0")

    for row_number, raw in enumerate(raw_transactions, start=1):
        # Imported AIS/SFT purchase- and sale-side records are evidence, not
        # completed disposals. Older saved drafts predate `recordKind`, so the
        # import marker is also recognized for backward compatibility.
        record_kind = str(raw.get("recordKind") or raw.get("record_kind") or "").upper()
        evidence_side = str(
            raw.get("evidenceSide") or raw.get("evidence_side") or ""
        ).upper()
        if not evidence_side:
            category = str(raw.get("importCategory") or "").lower()
            evidence_side = (
                "PURCHASE" if "purchase" in category
                else "SALE" if "sale" in category
                else "UNKNOWN"
            )

        def has_value(*keys: str) -> bool:
            """Return whether at least one alias contains a non-empty, non-zero value.

            A monetary value of 0 is treated as ABSENT so that a purchase-only
            row (saleValue=0, actualCost=500000) is not misread as a completed
            sale of ₹0 — which would fabricate a ₹5,00,000 capital loss.
            """
            for key in keys:
                value = raw.get(key)
                if value is None or value == "":
                    continue
                if isinstance(value, (int, float, Decimal)) and value == 0:
                    continue
                return True
            return False

        def _positive_amount(*keys: str) -> Decimal:
            """Return the first positive monetary value among aliases, else 0."""
            for key in keys:
                value = raw.get(key)
                if value is None or value == "":
                    continue
                try:
                    parsed = Decimal(str(value))
                except (ValueError, TypeError):
                    continue
                if parsed.is_finite() and parsed > 0:
                    return parsed
            return Decimal("0")

        # A sale-side AIS row becomes a completed taxable disposal once the user
        # supplies the missing purchase facts. Older drafts may still carry
        # recordKind=EVIDENCE, so completion is detected from canonical facts
        # rather than relying only on the frontend to rewrite the marker.
        ais_holding_period = str(
            raw.get("aisHoldingPeriod") or raw.get("ais_holding_period") or ""
        ).strip().upper()
        has_ais_long_term_classification = ais_holding_period.startswith("LONG")
        # A completed sale requires a POSITIVE sale value.  A zero/missing
        # saleValue with a positive actualCost is a purchase-only evidence row,
        # not a disposal — treating it as a ₹0 sale fabricates a fake loss.
        sale_amount = _positive_amount("sale_value", "saleValue", "saleCost", "fullValueOfConsideration")
        cost_amount = _positive_amount("actual_cost", "actualCost", "purchaseCost", "costOfAcquisition")
        has_positive_sale = sale_amount > 0
        is_completed_sale = (
            evidence_side == CapitalGainEvidenceSide.SALE.value
            and has_positive_sale
            and (
                has_value("acquisition_date", "acquisitionDate", "purchaseDate", "dateOfAcquisition")
                or has_ais_long_term_classification
            )
            and has_value("transfer_date", "transferDate", "saleDate", "dateOfTransfer")
            and cost_amount > 0
        )
        # A manually-entered purchase-only row (no saleValue, positive cost) is
        # evidence of a holding, not a completed disposal.  Treat it as evidence
        # so it never produces a fabricated gain/loss.  This fixes the bug where
        # a client with a ₹5,00,000 purchase and no sale was reported as having
        # ₹4,99,975 LTCG 112A (the cost being read as a sale).
        is_purchase_only_evidence = (
            not is_completed_sale
            and cost_amount > 0
            and not has_positive_sale
        )
        is_imported_evidence = (
            not is_completed_sale
            and (
                record_kind == CapitalGainRecordKind.EVIDENCE.value
                or str(raw.get("importStatus") or "").upper() == "INCOMPLETE"
                or is_purchase_only_evidence
            )
        )
        if is_imported_evidence:
            evidence_count += 1
            source_amount_raw = raw.get("importedGrossAmount")
            if source_amount_raw is None:
                if evidence_side == "PURCHASE" or is_purchase_only_evidence:
                    source_amount_raw = raw.get("actualCost", raw.get("purchaseCost", 0))
                else:
                    source_amount_raw = raw.get("saleValue", raw.get("saleCost", 0))
            try:
                source_amount = Decimal(str(source_amount_raw or 0))
            except (ValueError, TypeError):
                source_amount = Decimal("0")
            if source_amount.is_finite() and source_amount > 0:
                if evidence_side == "PURCHASE" or is_purchase_only_evidence:
                    evidence_purchase_total += source_amount
                elif evidence_side == "SALE":
                    evidence_sale_total += source_amount
            continue

        normalized_raw = dict(raw)
        for date_key in (
            "acquisition_date", "acquisitionDate", "purchaseDate", "dateOfAcquisition",
            "transfer_date", "transferDate", "saleDate", "dateOfTransfer",
        ):
            if normalized_raw.get(date_key) == "":
                normalized_raw[date_key] = None
        try:
            transaction = Section112ATransaction.model_validate({
                **normalized_raw,
                "raw_payload": raw,
            })
        except ValidationError as exc:
            issues.append(_issue(Section112AIssueCode.INVALID_TRANSACTION, "; ".join(error["msg"] for error in exc.errors()), row_number))
            continue

        asset = _ASSET_ALIASES.get(str(transaction.asset_type or "").strip().upper())
        if asset is None:
            issues.append(_issue(Section112AIssueCode.UNSUPPORTED_ASSET, "Only listed equity, equity-oriented mutual funds, and business-trust units are supported.", row_number, "assetType"))
        has_ais_long_term_classification = str(
            transaction.ais_holding_period or ""
        ).strip().upper().startswith("LONG")
        if transaction.acquisition_date is None and not has_ais_long_term_classification:
            issues.append(_issue(Section112AIssueCode.MISSING_ACQUISITION_DATE, "Acquisition date is required when AIS does not explicitly classify the disposal as long-term.", row_number, "purchaseDate"))
        if transaction.transfer_date is None:
            issues.append(_issue(Section112AIssueCode.MISSING_TRANSFER_DATE, "Transfer date is required.", row_number, "saleDate"))
        if transaction.sale_value is None or transaction.sale_value == 0:
            issues.append(_issue(Section112AIssueCode.MISSING_SALE_VALUE, "Full value of consideration is required.", row_number, "saleValue"))
        elif not transaction.sale_value.is_finite() or transaction.sale_value < 0:
            issues.append(_issue(Section112AIssueCode.INVALID_SALE_VALUE, "Sale value must be finite and non-negative.", row_number, "saleValue"))
        if transaction.actual_cost is None:
            issues.append(_issue(Section112AIssueCode.MISSING_ACTUAL_COST, "Actual cost is required.", row_number, "actualCost"))
        elif not transaction.actual_cost.is_finite() or transaction.actual_cost < 0:
            issues.append(_issue(Section112AIssueCode.INVALID_ACTUAL_COST, "Actual cost must be finite and non-negative.", row_number, "actualCost"))
        expenses = transaction.transfer_expenses if transaction.transfer_expenses is not None else Decimal("0")
        if not expenses.is_finite() or expenses < 0:
            issues.append(_issue(Section112AIssueCode.INVALID_TRANSFER_EXPENSES, "Transfer expenses must be finite and non-negative.", row_number, "transferExpenses"))
        if (
            asset is Section112AAssetType.LISTED_EQUITY
            and transaction.stt_paid_on_acquisition is not True
        ):
            issues.append(_issue(Section112AIssueCode.MISSING_STT_ACQUISITION, "STT paid on acquisition must be confirmed for a listed-equity Section 112A transaction.", row_number, "sttPaidOnAcquisition"))
        # For listed equity the transaction must carry explicit exchange/STT
        # confirmations. Imported equity-oriented fund and business-trust sale
        # records already identify an eligible exchange-traded disposal, so a
        # missing UI confirmation must not suppress an otherwise computable gain.
        if (
            asset is Section112AAssetType.LISTED_EQUITY
            and transaction.stt_paid_on_transfer is not True
        ):
            issues.append(_issue(Section112AIssueCode.MISSING_STT_TRANSFER, "STT paid on transfer must be confirmed for a listed-equity Section 112A transaction.", row_number, "sttPaidOnTransfer"))
        if (
            asset is Section112AAssetType.LISTED_EQUITY
            and transaction.recognized_exchange is not True
        ):
            issues.append(_issue(Section112AIssueCode.MISSING_RECOGNIZED_EXCHANGE, "Transfer on a recognized stock exchange must be confirmed for a listed-equity Section 112A transaction.", row_number, "recognizedExchange"))
        if (
            transaction.acquisition_date is not None
            and transaction.acquisition_date <= _GRANDFATHERING_DATE
            and transaction.fmv_31_jan_2018 is None
        ):
            issues.append(_issue(Section112AIssueCode.MISSING_FMV_31_JAN_2018, "FMV as on 31-Jan-2018 is required to compute the grandfathered cost for this acquisition.", row_number, "fmv31Jan2018"))
        elif transaction.fmv_31_jan_2018 is not None and (
            not transaction.fmv_31_jan_2018.is_finite()
            or transaction.fmv_31_jan_2018 < 0
        ):
            issues.append(_issue(Section112AIssueCode.INVALID_FMV_31_JAN_2018, "FMV as on 31-Jan-2018 must be finite and non-negative.", row_number, "fmv31Jan2018"))

        dates_valid = transaction.acquisition_date is not None and transaction.transfer_date is not None
        if dates_valid and transaction.transfer_date <= transaction.acquisition_date:
            issues.append(_issue(Section112AIssueCode.INVALID_DATE_ORDER, "Transfer date must be after acquisition date.", row_number, "saleDate"))
        row_has_issue = any(issue.row == row_number for issue in issues)
        if row_has_issue:
            continue

        assert asset is not None and transaction.transfer_date is not None
        assert transaction.sale_value is not None and transaction.actual_cost is not None
        if transaction.acquisition_date is not None:
            holding_days = (transaction.transfer_date - transaction.acquisition_date).days
            anniversary_year = transaction.acquisition_date.year + 1
            try:
                twelve_month_anniversary = transaction.acquisition_date.replace(
                    year=anniversary_year
                )
            except ValueError:
                twelve_month_anniversary = transaction.acquisition_date.replace(
                    year=anniversary_year,
                    day=28,
                )
            if transaction.transfer_date <= twelve_month_anniversary:
                issues.append(_issue(Section112AIssueCode.NOT_LONG_TERM, "Transaction is not long-term (holding period must exceed 12 calendar months).", row_number, "purchaseDate"))
                continue
            holding_months = (holding_days * 12) // 365
        else:
            # AIS SFT-18 disposal rows explicitly report the asset as long-term
            # but do not disclose acquisition dates. Preserve that source fact
            # rather than fabricating a date merely to calculate a duration.
            holding_days = 0
            holding_months = 13

        deemed_cost = transaction.actual_cost
        grandfathered = (
            transaction.acquisition_date is not None
            and transaction.acquisition_date <= _GRANDFATHERING_DATE
        )
        if grandfathered:
            # Presence and validity were established before this row reached
            # computation, so grandfathering can never silently fall back to
            # actual cost for an old acquisition.
            assert transaction.fmv_31_jan_2018 is not None
            fmv = transaction.fmv_31_jan_2018
            deemed_cost = max(transaction.actual_cost, min(fmv, transaction.sale_value))
        gain = transaction.sale_value - deemed_cost - expenses
        computed.append(Section112ATransactionResult(
            row=row_number, asset_type=asset, holding_period_days=holding_days,
            holding_period_months=holding_months,
            sale_value=transaction.sale_value, actual_cost=transaction.actual_cost,
            deemed_cost=deemed_cost, transfer_expenses=expenses, gain=gain,
            grandfathering_applied=grandfathered,
        ))
        if gain < 0:
            issues.append(_issue(Section112AIssueCode.SECTION_112A_LOSS, "This transaction results in a long-term capital loss under Section 112A. Capital gains/losses must be reported in ITR-2 or ITR-3, as applicable.", row_number))

    gross_gain = sum((item.gain for item in computed), Decimal("0"))
    if gross_gain > _RESTRICTED_LIMIT:
        issues.append(Section112AIssue(Section112AIssueCode.AGGREGATE_LIMIT_EXCEEDED, "Aggregate gross Section 112A gain exceeds Rs 1,25,000; ITR-1/ITR-4 is not eligible."))
    eligible = not issues
    if issues:
        status = "BLOCKED"
    elif computed:
        status = "VALID"
    elif evidence_count:
        status = "EVIDENCE_ONLY"
    else:
        status = "EMPTY"
    return Section112APortfolioResult(
        status=status,
        transactions=tuple(computed),
        issues=tuple(issues),
        evidence_count=evidence_count,
        evidence_purchase_total=evidence_purchase_total,
        evidence_sale_total=evidence_sale_total,
        gross_gain=gross_gain,
        full_value_of_consideration=sum((item.sale_value for item in computed), Decimal("0")),
        # The restricted ITR-1/ITR-4 official schedule exposes one aggregate
        # deduction field (TotCstAcqisn), while its validation cross-foot is
        # sale consideration minus that field equals LongCap112A.  Carry both
        # deemed acquisition cost and transfer expenditure into that projected
        # deduction so the official artifact reconciles to the computed gain.
        cost_of_acquisition=sum(
            (item.deemed_cost + item.transfer_expenses for item in computed),
            Decimal("0"),
        ),
        transfer_expenses=sum((item.transfer_expenses for item in computed), Decimal("0")),
        eligibility={
            "ITR-1": eligible,
            "ITR-4": eligible,
        },
    )


# ---------------------------------------------------------------------------
# Canonical alias — the single unified 112A entrypoint for ITR-1/ITR-4.
# ---------------------------------------------------------------------------
# ``compute_112a`` is the canonical name for all ITR-1/ITR-4 112A
# computation.  It is the same function as ``compute_restricted_112a`` —
# the two names express intent ("compute 112A" vs "restricted portfolio")
# but guarantee a single implementation.  The ITR-2/ITR-3 per-scrip path
# in ``app.engine.schedules.capital_gains`` is a *different*
# responsibility (full Schedule CG with grandfathering, indexation, and
# per-scrip detail) and must not be invoked from the ITR-1/4 pipeline.
compute_112a = compute_restricted_112a
