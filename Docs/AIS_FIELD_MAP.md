# AIS → ITR Field Map (Verified against 63 client AIS+TIS pairs)

## Reconciliation Results
- 34/63 clients: AIS totals == TIS totals ✅
- 29/63 clients: AIS totals != TIS totals ❌

## Root Causes of Mismatches

### 1. Salary Double-Counting (B1 + B7)
- **AIS has**: B1 TDS-192 (TDS on salary) + B7 TDS-Ann.II-SAL (Annexure II salary break-up)
- **TIS shows**: only the Annexure II figure (B7)
- **Fix**: For salary income, use B7 TDS-Ann.II-SAL amount. Use B1 TDS-192 only for the TDS tab (tax credit).

### 2. Inactive Detail Rows
- Some AIS entries have detail rows with STATUS = "Inactive"
- The extractor sums ALL rows including Inactive → over-counts
- **Fix**: Always filter `status == 'Active'` when summing detail rows.

### 3. Dividend (B1 TDS-194 + B2 SFT-015)
- B1 TDS-194 = TDS deducted on dividend (deductor's view)
- B2 SFT-015 = Dividend income paid (company's view)
- These can overlap but are from different sources
- **TIS shows**: the accepted dividend total
- **Fix**: Use B2 SFT-015 as the dividend income source. Use B1 TDS-194 only for the TDS tab.

## Complete AIS Code → ITR Schedule Map

### Salary Head
| AIS Code | Section | AIS Fields | ITR Schedule | Notes |
|---|---|---|---|---|
| TDS-192 | B1 | QUARTER, DATE OF PAYMENT, AMOUNT PAID, TDS DEDUCTED, TDS DEPOSITED, STATUS | TDS tab (tax credit) | Do NOT use for salary income (use B7) |
| TDS-Ann.II-SAL | B7 | EMPLOYMENT START/END, GROSS SALARY 17(1), PERQUISITES 17(2), PROFITS 17(3), GROSS SALARY | Salary tab (employer entries) | This is the authoritative salary figure |

### Capital Gains Head
| AIS Code | Section | AIS Fields | ITR Schedule | Notes |
|---|---|---|---|---|
| SFT-17-LES(M) | B2 | DATE OF SALE, SECURITY NAME, SECURITY CLASS, DEBIT/CREDIT TYPE, ASSET TYPE, QUANTITY, SALE PRICE, SALES CONSIDERATION, STT, COST OF ACQUISITION, UNIT FMV, FAIR MARKET VALUE, INDEXED COST | Schedule 112A (LTCG) or A2 (STCG) | Sale of listed equity. Has named fields. |
| SFT-18-EMF(M) | B2 | (same as above + AMC NAME) | Schedule 112A (LTCG) or A2 (STCG) | Sale of equity-oriented MF. Has named fields. |
| SFT-18-OTU(M) | B2 | (same as above) | Schedule 112A or A2 | Sale of other units. |
| SFT-18(Pur) | B2 | QUARTER, CLIENT ID, AMC NAME, HOLDER FLAG, TOTAL PURCHASE AMOUNT, TOTAL SALES VALUE | Capital Gains (purchase evidence) | Purchase — NOT a disposal. col_* only. |
| SFT-17(Pur) | B2 | QUARTER, CLIENT ID, HOLDER FLAG, MARKET PURCHASE, MARKET SALES | Capital Gains (purchase evidence) | Purchase — NOT a disposal. col_* only. |
| SFT-012 | B2 | PROPERTY ADDRESS, TRANSACTION DATE, TRANSACTION AMOUNT, STAMP DUTY | A1/B1 (immovable property) | Sale. col_* only. |
| SFT-012(P) | B2 | (purchase of immovable property) | Capital Gains (purchase evidence) | Purchase — NOT a disposal. |
| TDS-194IA | B1 | ACKNOWLEDGEMENT NUMBER, PROPERTY ADDRESS, DATE, AMOUNT PAID, TDS DEPOSITED | TDS tab + CG (immovable) | Real estate TDS. |
| TDS-194S | B1 | QUARTER, DATE, AMOUNT PAID, TDS DEDUCTED | TDS tab + CG (VDA) | Crypto/VDA. |

### Other Sources Head
| AIS Code | Section | AIS Fields | ITR Schedule | Notes |
|---|---|---|---|---|
| SFT-015 | B2 | REPORTED ON, DIVIDEND AMOUNT, STATUS | Other Sources (dividend) | col_* only. |
| SFT-016(SB) | B2 | REPORTED ON, ACCOUNT NUMBER, ACCOUNT TYPE, INTEREST AMOUNT | Other Sources (savings interest) | col_* only. |
| SFT-016(TD) | B2 | (same) | Other Sources (term deposit interest) | col_* only. |
| SFT-016(RD) | B2 | (same) | Other Sources (recurring deposit interest) | col_* only. |
| TDS-194 | B1 | QUARTER, DATE, AMOUNT PAID, TDS DEDUCTED | TDS tab | Dividend TDS. |
| TDS-194A | B1 | QUARTER, DATE, AMOUNT PAID, TDS DEDUCTED | TDS tab | Interest TDS. |
| TDS-194K | B1 | QUARTER, DATE, AMOUNT RECEIVED, TAX COLLECTED | TDS tab | MF dividend TDS. |

### Business Head
| AIS Code | Section | AIS Fields | ITR Schedule | Notes |
|---|---|---|---|---|
| TDS-194C | B1 | QUARTER, DATE, AMOUNT PAID, TDS DEDUCTED | TDS tab + Business | Contract receipts. |
| TDS-194H | B1 | (same) | TDS tab + Business | Commission. |
| TDS-194R | B1 | (same) | TDS tab + Business | Perquisites. |
| TDS-194T | B1 | (same) | TDS tab + Business | Partner receipts. |
| TDS-194N | B1 | (same) | TDS tab + Business | Cash withdrawals. |
| EXC-GSTR1(P) | B7 | GSTIN, SUPPLIER NAME, RETURN PERIOD, PURCHASE FROM SUPPLIER | Business (GST purchases) | col_* only. |
| EXC-GSTR3B | B7 | GSTIN, RETURN PERIOD, TOTAL TURNOVER, TAXABLE TURNOVER | Business (GST turnover) | col_* only. |

## TIS Reconciliation (Authoritative Source)
TIS shows ONE figure per category (the accepted-by-taxpayer amount).
When AIS and TIS differ:
- Salary: TIS = B7 Annexure II (not B1 + B7)
- Interest: TIS = sum of B2 SFT-016 Active rows (not B1 TDS-194A)
- Dividend: TIS = sum of B2 SFT-015 Active rows (may include B1 TDS-194)
- Capital Gains Sale: TIS = sum of B2 sale code amounts
- Capital Gains Purchase: TIS = sum of B2 purchase code amounts

## Key Rules for the Frontend Import
1. **Salary income**: Use B7 TDS-Ann.II-SAL only (NOT B1 TDS-192)
2. **TDS tab**: Use B1 TDS-* entries (all sections)
3. **Interest income**: Use B2 SFT-016 only (dedup against B1 TDS-194A)
4. **Dividend income**: Use B2 SFT-015 only (dedup against B1 TDS-194)
5. **Capital Gains sales**: Use B2 SFT-17-LES(M), SFT-18-EMF(M), SFT-18-OTU(M), SFT-012
6. **Capital Gains purchases**: Use B2 SFT-17(Pur), SFT-18(Pur) — evidence only, NOT disposals
7. **Business**: Use B1 TDS-194C/194H/194R/194T/194N + B7 EXC-GSTR*
8. **Always filter**: STATUS == 'Active' when summing detail rows
9. **Date format**: Convert DD/MM/YYYY → YYYY-MM-DD for the backend
10. **assetType mapping**: MF → 'EQUITY_ORIENTED_MUTUAL_FUND', Equity → 'LISTED_EQUITY'
11. **STT flags**: Set for LISTED_EQUITY (AIS SFT-17-LES is exchange-traded)
12. **aisHoldingPeriod**: Set from AIS asset_type (e.g. "Long term")
