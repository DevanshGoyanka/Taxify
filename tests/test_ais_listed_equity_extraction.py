"""Regression tests for row-level AIS listed-equity extraction."""

from ais_extractor.extractor import (
    _parse_equity_mutual_fund_sale_rows,
    _parse_listed_equity_sale_rows,
)


def test_parse_listed_equity_sale_row_with_wrapped_cells() -> None:
    """Wrapped security and categorical cells are reconstructed losslessly."""
    text = """1
10/03/2026
EDELWEISS FINANCIAL SERVICES LIMITED - NEW EQUITY
SHARES(INE532F01054)
Listed
Equity Share
Market
Off
market
Long
term
25.00
104.17
2,604
2,695.75
280.85
7,021.25
0
Active
"""

    headers, rows = _parse_listed_equity_sale_rows(text)

    assert len(headers) == 15
    assert len(rows) == 1
    data = rows[0].data
    assert data["transfer_date"] == "10/03/2026"
    assert data["security_name"] == "EDELWEISS FINANCIAL SERVICES LIMITED - NEW EQUITY SHARES"
    assert data["isin"] == "INE532F01054"
    assert data["security_class"] == "Listed Equity Share"
    assert data["debit_type"] == "Market"
    assert data["credit_type"] == "Off Market"
    assert data["asset_type"] == "Long term"
    assert data["quantity"] == "25.00"
    assert data["sales_consideration"] == "2,604"
    assert data["cost_of_acquisition"] == "2,695.75"
    assert data["fair_market_value"] == "7,021.25"


def test_parse_equity_mutual_fund_disposal_with_stt() -> None:
    """SFT-18 mutual-fund rows preserve tax fields and wrapped ISINs."""
    text = """STATUS
1
Bandhan 
AMC 
Limited(G
)
30/03/2026
Unit of 
Equity 
Oriented 
Mutual 
Fund
Bandhan 
Financial 
Services 
Fund-
Regular 
Plan-
Growth(I
NF194KB
1GE6)
AMC 
(redemption
)
AMC 
(purchase)
Long 
term
1,169.15
12.83
15,000
0.15
16,044.20
0
0
0
Active
"""

    headers, rows = _parse_equity_mutual_fund_sale_rows(text)

    assert len(headers) == 17
    assert len(rows) == 1
    data = rows[0].data
    assert data["amc_name"] == "BandhanAMCLimited(G)"
    assert data["transfer_date"] == "30/03/2026"
    assert data["security_name"] == "Bandhan Financial Services Fund-Regular Plan-Growth"
    assert data["isin"] == "INF194KB1GE6"
    assert data["asset_type"] == "Long term"
    assert data["quantity"] == "1,169.15"
    assert data["sales_consideration"] == "15,000"
    assert data["stt"] == "0.15"
    assert data["cost_of_acquisition"] == "16,044.20"
