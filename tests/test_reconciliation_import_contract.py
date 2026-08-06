"""Synthetic regression tests for AIS/TIS/26AS reconciliation."""

from typing import Any

from ais_extractor.reconciliation import reconcile
from app.engine.schedules.restricted_112a import compute_restricted_112a


def test_ais_capital_gain_details_survive_as_transaction_evidence() -> None:
    """Real SFT-18(Pur) detail rows are parsed with AMC wrapping detection."""
    ais: dict[str, Any] = {
        "metadata": {"financial_year": "2025-26", "download_id": "SYNTHETIC"},
        "income_heads": {
            "Capital Gains": {
                "entries": [{
                    "sr_no": 1,
                    "category": "purchase of securities and units of mutual funds",
                    "information_code": "SFT-18(Pur)",
                    "information_source": "Synthetic Depository",
                    "institution_pan": "AAAAA1234A",
                    "amount": 24000,
                    "detail_header": [
                        "SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)",
                        "HOLDER FLAG", "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS",
                    ],
                    "details": [
                        {"sr_no": 1, "data": {
                            "col_0": "1", "col_1": "Q4(Jan-Mar)",
                            "col_2": "12345678", "col_3": "HDFC Asset Management",
                            "col_4": "Company Limited(H)", "col_5": "First",
                            "col_6": "12,000", "col_7": "12,000",
                        }},
                        {"sr_no": 2, "data": {
                            "col_0": "2", "col_1": "Q2(Jul-Sep)",
                            "col_2": "12345678", "col_3": "HDFC Asset Management",
                            "col_4": "Company Limited(H)", "col_5": "First",
                            "col_6": "12,000", "col_7": "0",
                        }},
                    ],
                }],
            },
        },
    }

    result = reconcile(ais, {}, {})
    evidence = result["capital_gain_evidence"]

    # 2 detail rows × (purchase + sale for row 1, purchase only for row 2) = 3
    purchases = [e for e in evidence if e["side"] == "PURCHASE"]
    sales = [e for e in evidence if e["side"] == "SALE"]
    assert len(purchases) == 2
    assert len(sales) == 1
    assert sales[0]["amount"] == 12000.0

    # AMC name wrapping detected
    assert "HDFC" in evidence[0]["security_name"]
    assert evidence[0]["account_id"] == "12345678"
    assert evidence[0]["parser_confidence"] == "HIGH"


def test_capital_gain_detail_control_mismatch_is_explicit() -> None:
    """Detail evidence total vs TIS accepted total produces cross-foot discrepancy."""
    ais: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 1,
            "category": "purchase of securities and units of mutual funds",
            "information_code": "SFT-18(Pur)",
            "information_source": "Synthetic Registrar",
            "amount": 10000,
            "detail_header": ["SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)", "HOLDER FLAG", "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS"],
            "details": [{"sr_no": 1, "data": {
                "col_0": "1", "col_1": "Q4(Jan-Mar)", "col_2": "123456",
                "col_3": "Synthetic Fund(S)", "col_4": "First", "col_5": "9,000", "col_6": "0", "col_7": "Active",
            }}],
        }]}}
    }
    tis: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "category": "purchase of securities and units of mutual funds",
            "accepted_by_taxpayer": 10000,
            "details": [{"sr_no": 1, "information_source": "Synthetic Registrar", "accepted_by_taxpayer": "10000", "part": "SFT"}],
        }]}}
    }

    result = reconcile(ais, tis, {})

    assert len(result["capital_gain_evidence"]) == 1
    assert result["capital_gain_evidence"][0]["amount"] == 9000.0
    assert result["capital_gain_control_discrepancies"] == [{
        "category": "purchase of securities and units of mutual funds",
        "side": "PURCHASE",
        "detail_total": 9000.0,
        "ais_control_total": 10000.0,
        "tis_accepted_total": 10000.0,
        "difference": -1000.0,
    }]


def test_tis_capital_gain_rows_remain_controls_not_transactions() -> None:
    """TIS accepted rows cannot invent dates, lots, cost, or taxable gains."""
    tis: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "category": "purchase of securities and units of mutual funds",
            "accepted_by_taxpayer": 25000,
            "details": [{
                "sr_no": 7,
                "information_source": "Synthetic Registrar",
                "accepted_by_taxpayer": "25000",
                "part": "SFT",
            }],
        }]}}
    }

    result = reconcile({}, tis, {})

    assert result["capital_gain_evidence"] == []
    assert len(result["capital_gain_controls"]) == 2
    assert result["capital_gain_controls"][0]["source_document"] == "TIS"
    assert result["capital_gain_controls"][0]["granularity"] == "REPORTING_SOURCE_AGGREGATE"
    assert result["capital_gain_controls"][1]["granularity"] == "CATEGORY_CONTROL"


def test_capital_gain_cross_foot_uses_tis_category_total_not_overlapping_details() -> None:
    """The system-deduplicated TIS accepted total is the authoritative control."""
    ais: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 1,
            "category": "purchase of securities and units of mutual funds",
            "information_code": "SFT-18(Pur)",
            "information_source": "Synthetic Depository",
            "amount": 10000,
            "detail_header": ["SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)", "HOLDER FLAG", "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS"],
            "details": [{"sr_no": 1, "data": {
                "col_0": "1", "col_1": "Q4(Jan-Mar)", "col_2": "99999",
                "col_3": "Synthetic Fund(S)", "col_4": "First", "col_5": "10,000", "col_6": "0", "col_7": "Active",
            }}],
        }]}}
    }
    tis: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "category": "purchase of securities and units of mutual funds",
            "accepted_by_taxpayer": 10000,
            "details": [
                {"sr_no": 1, "information_source": "Synthetic Depository", "accepted_by_taxpayer": "10000", "part": "SFT"},
                {"sr_no": 2, "information_source": "Overlapping Source", "accepted_by_taxpayer": "1000", "part": "SFT"},
            ],
        }]}}
    }

    result = reconcile(ais, tis, {})

    assert result["capital_gain_control_discrepancies"] == []
    category_controls = [
        control for control in result["capital_gain_controls"]
        if control["source_document"] == "TIS" and control["granularity"] == "CATEGORY_CONTROL"
    ]
    assert category_controls[0]["amount"] == 10000.0


def test_detail_rows_emit_purchase_and_sale_sides() -> None:
    """SFT-18(Pur) rows with non-zero TOTAL SALES VALUE emit both sides."""
    ais: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 1,
            "category": "purchase of securities and units of mutual funds",
            "information_code": "SFT-18(Pur)",
            "information_source": "Synthetic Registrar",
            "amount": 25000,
            "detail_header": ["SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)", "HOLDER FLAG", "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS"],
            "details": [
                {"sr_no": 1, "data": {
                    "col_0": "1", "col_1": "Q4(Jan-Mar)", "col_2": "111111",
                    "col_3": "Test AMC(T)", "col_4": "First", "col_5": "10,000", "col_6": "0", "col_7": "Active",
                }},
                {"sr_no": 2, "data": {
                    "col_0": "2", "col_1": "Q2(Jul-Sep)", "col_2": "222222",
                    "col_3": "Test AMC(T)", "col_4": "First", "col_5": "5,000", "col_6": "15,000", "col_7": "Active",
                }},
            ],
        }]}}
    }

    result = reconcile(ais, {}, {})
    evidence = result["capital_gain_evidence"]

    purchases = [e for e in evidence if e["side"] == "PURCHASE"]
    sales = [e for e in evidence if e["side"] == "SALE"]
    assert len(purchases) == 2
    assert len(sales) == 1
    assert sales[0]["amount"] == 15000.0
    assert sales[0]["account_id"] == "222222"


def test_summary_only_entries_emit_as_aggregate() -> None:
    """SFT-17-LES(M) entries without details emit summary as aggregate evidence."""
    ais: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 1,
            "category": "sale of securities and units of mutual fund",
            "information_code": "SFT-17-LES(M)",
            "information_source": "Synthetic Depository",
            "amount": 648038,
            "detail_header": [],
            "details": [],
        }]}}
    }

    result = reconcile(ais, {}, {})
    evidence = result["capital_gain_evidence"]

    assert len(evidence) == 1
    assert evidence[0]["side"] == "SALE"
    assert evidence[0]["amount"] == 648038.0
    assert evidence[0]["detail_sr_no"] is None


def test_amc_wrapping_detection() -> None:
    """AMC names wrapping into col_4 are correctly detected."""
    ais: dict[str, Any] = {
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 1,
            "category": "purchase of securities and units of mutual funds",
            "information_code": "SFT-18(Pur)",
            "information_source": "Synthetic",
            "amount": 5000,
            "detail_header": ["SR. NO.", "QUARTER", "CLIENT ID", "AMC NAME (CODE)", "HOLDER FLAG", "TOTAL PURCHASE AMOUNT", "TOTAL SALES VALUE", "STATUS"],
            "details": [{"sr_no": 1, "data": {
                "col_0": "1", "col_1": "Q4(Jan-Mar)", "col_2": "99999",
                "col_3": "ICICI Prudential Mutual", "col_4": "Fund(P)",
                "col_5": "First", "col_6": "5,000", "col_7": "0",
            }}],
        }]}}
    }

    result = reconcile(ais, {}, {})
    evidence = result["capital_gain_evidence"]

    assert "ICICI Prudential Mutual Fund(P)" in evidence[0]["security_name"]
    assert evidence[0]["account_id"] == "99999"
    assert evidence[0]["amount"] == 5000.0

def test_salary_sources_merge_by_controlled_name_and_preserve_real_tan() -> None:
    """Equivalent salary rows must reconcile once and retain the 26AS TAN."""
    ais: dict[str, Any] = {
        "income_heads": {
            "Salary": {
                "entries": [{
                    "category": "salary",
                    "information_source": "salary received Example Technology Private Limited",
                    "amount": "1964956",
                    "information_code": "S192",
                    "information_description": "Salary",
                }],
            },
        },
    }
    tis: dict[str, Any] = {
        "income_heads": {
            "Salary": {
                "entries": [{
                    "category": "salary",
                    "details": [{
                        "information_source": "salary Example Technology Private Limited",
                        "accepted_by_taxpayer": "1964959",
                        "part": "S192",
                        "information_description": "Salary",
                    }],
                }],
            },
        },
    }
    as26: dict[str, Any] = {
        "parts": {
            "I": {
                "empty": False,
                "rows": [{
                    "Name of Deductor": "EXAMPLE TECHNOLOGY PRIVATE LIMITED",
                    "TAN of Deductor": "ABCD12345E",
                    "Total Amount Paid/Credited": "1964959",
                    "Total Tax Deducted": "123953",
                    "_details": [{"Section": "192"}],
                }],
            },
        },
    }

    result = reconcile(ais, tis, as26)
    entries = result["income_heads"]["Salary"]["entries"]

    assert len(entries) == 1
    assert entries[0]["final_amount"] == 1964959.0
    assert entries[0]["as26_tds"] == 123953.0
    assert entries[0]["as26_tcs"] == 0.0
    assert entries[0]["tan"] == "ABCD12345E"
    assert entries[0]["selected_source"] == "TIS"
    assert entries[0]["selection_reason"] == "TIS_ACCEPTED_INCOME"
    assert entries[0]["credit_type"] == "TDS"
    assert entries[0]["credit_selected_source"] == "26AS"
    assert entries[0]["credit_selection_reason"] == "26AS_TAX_CREDIT"
    assert entries[0]["present_in"] == {"tis": True, "ais": True, "as26": True}
    assert result["summary"]["total_final_income"] == 1964959.0


def test_single_source_entry_is_preserved_in_income_heads_and_unmatched_metadata() -> None:
    """A single-source row remains importable while being flagged for review."""
    ais: dict[str, Any] = {
        "income_heads": {
            "Capital Gains": {
                "entries": [{
                    "category": "purchase of securities and units of mutual funds",
                    "information_source": "Synthetic Fund Registrar (AAAAA1234A.AB123)",
                    "amount": "50000",
                    "information_code": "SFT-18",
                    "information_description": "Purchase of mutual fund units",
                    "institution_pan": "AAAAA1234A",
                }],
            },
        },
    }

    result = reconcile(ais, {}, {})
    entries = result["income_heads"]["Capital Gains"]["entries"]

    assert len(entries) == 1
    assert entries[0]["final_amount"] == 50000.0
    assert entries[0]["present_in"] == {"tis": False, "ais": True, "as26": False}
    assert len(result["unmatched"]["ais_only"]) == 1


def test_tis_accepted_dividend_total_controls_overlapping_detail_evidence() -> None:
    """TDS evidence must not inflate the system-deduplicated TIS dividend total."""
    tis: dict[str, Any] = {
        "income_heads": {
            "Income from Other Sources": {
                "entries": [{
                    "category": "dividend",
                    "accepted_by_taxpayer": 514,
                    "details": [
                        {
                            "information_source": "Synthetic Company One (AAAAA1111A.AB100)",
                            "institution_pan": "AAAAA1111A",
                            "accepted_by_taxpayer": "500",
                            "part": "SFT",
                            "information_description": "Dividend income",
                        },
                        {
                            "information_source": "Synthetic Company Two (BBBBB2222B.AB200)",
                            "institution_pan": "BBBBB2222B",
                            "accepted_by_taxpayer": "14",
                            "part": "SFT",
                            "information_description": "Dividend income",
                        },
                        {
                            "information_source": "Synthetic Company Two (WXYZ12345Q)",
                            "accepted_by_taxpayer": "14",
                            "part": "TDS/TCS",
                            "information_description": "Dividend received (Section 194)",
                        },
                    ],
                }],
            },
        },
    }
    as26: dict[str, Any] = {
        "parts": {
            "I": {
                "empty": False,
                "rows": [{
                    "Name of Deductor": "SYNTHETIC COMPANY TWO",
                    "TAN of Deductor": "WXYZ12345Q",
                    "Total Amount Paid/Credited": "14",
                    "Total Tax Deducted": "0",
                    "_details": [{"Section": "194"}],
                }],
            },
        },
    }

    result = reconcile({}, tis, as26)
    entries = result["income_heads"]["Income from Other Sources"]["entries"]

    assert sum(entry["amounts"]["tis"] for entry in entries) == 528.0
    assert result["category_controls"]["dividend"] == 514.0
    assert result["category_control_discrepancies"] == [{
        "category": "dividend",
        "tis_accepted_total": 514.0,
        "tis_detail_total": 528.0,
        "difference": 14.0,
    }]
    assert result["income_heads"]["Income from Other Sources"]["total_final"] == 514.0
    assert result["summary"]["total_final_income"] == 514.0
    assert len(entries) >= 2


def test_distinct_fund_purchases_are_not_collapsed_by_rta_pan() -> None:
    """Reporting-entity PAN is provenance, not mutual-fund transaction identity."""
    details = [
        {
            "information_source": f"Synthetic Registrar - Fund {index} (AAAAA1234A.AB100)",
            "institution_pan": "AAAAA1234A",
            "accepted_by_taxpayer": str(amount),
            "part": "SFT",
            "information_description": "Purchase of mutual fund units",
        }
        for index, amount in enumerate((10000, 10000, 8000, 4000, 4000, 4000, 4000), start=1)
    ]
    tis: dict[str, Any] = {
        "income_heads": {
            "Capital Gains": {
                "entries": [{
                    "category": "purchase of securities and units of mutual funds",
                    "accepted_by_taxpayer": 44000,
                    "details": details,
                }],
            },
        },
    }

    result = reconcile({}, tis, {})
    entries = result["income_heads"]["Capital Gains"]["entries"]

    assert len(entries) == 7
    assert sorted(entry["final_amount"] for entry in entries) == [4000, 4000, 4000, 4000, 8000, 10000, 10000]


def test_form26as_tcs_is_separate_from_tds_and_does_not_invent_income() -> None:
    """Part VI controls TCS credit but cannot become income without AIS/TIS."""
    as26: dict[str, Any] = {
        "parts": {
            "VI": {
                "empty": False,
                "rows": [{
                    "Name of Collector": "SYNTHETIC COLLECTOR LIMITED",
                    "TAN of Collector": "WXYZ12345Q",
                    "Total Amount Paid/Debited": "250000",
                    "Total Tax Collected": "2500",
                    "_details": [{"Section": "206C"}],
                }],
            },
        },
    }

    result = reconcile({}, {}, as26)
    entries = next(iter(result["income_heads"].values()))["entries"]

    assert len(entries) == 1
    assert entries[0]["final_amount"] == 0.0
    assert entries[0]["amounts"]["as26"] == 250000.0
    assert entries[0]["as26_tds"] == 0.0
    assert entries[0]["as26_tcs"] == 2500.0
    assert entries[0]["credit_type"] == "TCS"
    assert entries[0]["credit_selected_source"] == "26AS"
    assert entries[0]["selection_reason"] == "26AS_CREDIT_EVIDENCE_ONLY"


def test_listed_equity_sale_details_preserve_ais_tax_fields() -> None:
    """SFT-17 listed-equity sale rows retain all explicit AIS values."""
    headers = [
        "SR. NO.", "DATE OF SALE/TRANSFER", "SECURITY NAME (SECURITY CODE)",
        "SECURITY CLASS", "DEBIT TYPE", "CREDIT TYPE", "ASSET TYPE",
        "QUANTITY", "SALE PRICE PER UNIT", "SALES CONSIDERATION",
        "COST OF ACQUISITION", "UNIT FMV", "FAIR MARKET VALUE",
        "INDEXED COST OF ACQUISITION", "STATUS",
    ]
    values = [
        "1", "10/03/2026", "TEST LIMITED(INE532F01054)",
        "Listed Equity Share", "Market", "Market", "Short term", "25.00",
        "104.17", "2,604", "2,695.75", "280.85", "7,021.25", "0", "Active",
    ]
    ais: dict[str, Any] = {
        "metadata": {"financial_year": "2025-26", "download_id": "SYNTHETIC"},
        "income_heads": {"Capital Gains": {"entries": [{
            "sr_no": 5,
            "category": "sale of securities and units of mutual fund",
            "information_code": "SFT-17-LES(M)",
            "information_source": "Synthetic Depository",
            "amount": 2604,
            "detail_header": headers,
            "details": [{"sr_no": 1, "data": {
                f"col_{index}": value for index, value in enumerate(values)
            }}],
        }]}},
    }

    evidence = reconcile(ais, {}, {})["capital_gain_evidence"]

    assert len(evidence) == 1
    sale = evidence[0]
    assert sale["granularity"] == "TRANSACTION_DETAIL"
    assert sale["transaction_date"] == "10/03/2026"
    assert sale["security_name"] == "TEST LIMITED"
    assert sale["security_identifier"] == "INE532F01054"
    assert sale["security_class"] == "Listed Equity Share"
    assert sale["quantity"] == 25.0
    assert sale["amount"] == 2604.0
    assert sale["acquisition_cost"] == 2695.75
    assert sale["sale_price_per_unit"] == 104.17
    assert sale["unit_fmv"] == 280.85
    assert sale["fair_market_value"] == 7021.25
    assert sale["debit_type"] == "Market"
    assert sale["credit_type"] == "Market"
    assert sale["asset_type"] == "Short term"
    assert sale["stt_paid_on_transfer"] is None
    assert sale["recognized_exchange"] is None
    assert sale["acquired_before_31_jan_2018"] is None


def test_all_available_source_pair_discrepancies_are_reported() -> None:
    """Reconciliation must report every mismatching source pair."""
    ais: dict[str, Any] = {
        "income_heads": {
            "Salary": {"entries": [{
                "category": "salary",
                "information_source": "salary received Synthetic Employer",
                "amount": "1000000",
                "information_code": "192",
            }]},
        },
    }
    tis: dict[str, Any] = {
        "income_heads": {
            "Salary": {"entries": [{
                "category": "salary",
                "accepted_by_taxpayer": 1100000,
                "details": [{
                    "information_source": "salary Synthetic Employer",
                    "accepted_by_taxpayer": "1100000",
                    "part": "192",
                    "information_description": "Salary received Section 192",
                }],
            }]},
        },
    }
    as26: dict[str, Any] = {
        "parts": {"I": {"empty": False, "rows": [{
            "Name of Deductor": "SYNTHETIC EMPLOYER",
            "TAN of Deductor": "ABCD12345E",
            "Total Amount Paid/Credited": "900000",
            "Total Tax Deducted": "50000",
            "_details": [{"Section": "192"}],
        }]}},
    }

    entry = reconcile(ais, tis, as26)["income_heads"]["Salary"]["entries"][0]

    assert entry["has_discrepancy"] is True
    assert "TIS=1,100,000.00 vs AIS=1,000,000.00" in entry["discrepancy_detail"]
    assert "TIS=1,100,000.00 vs 26AS=900,000.00" in entry["discrepancy_detail"]
    assert "AIS=1,000,000.00 vs 26AS=900,000.00" in entry["discrepancy_detail"]
