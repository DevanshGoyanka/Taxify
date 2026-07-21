# EXACT REMAINING ITEMS TO IMPLEMENT PER CBDT RULES (AY 2026-27)

================================================================================
## ITR-1 (SAHAJ) - ITEMS REMAINING
================================================================================

### 1. SCHEDULE DETAILS NOT FULLY IMPLEMENTED

| Item | Rule No | Description | Priority |
|------|---------|-------------|----------|
| Schedule 10(13A) | 263-269 | HRA computation details | HIGH |
| Schedule EA10_13A | N/A | Exempt allowances detailed | MEDIUM |
| TaxReturnPreparer | N/A | TRP details section | LOW |

### 2. VALIDATION RULES NOT IMPLEMENTED (~50 rules)

| Rule No | Description | Priority |
|---------|-------------|----------|
| 19 | Name mismatch with PAN database | MEDIUM |
| 31-42 | Exempt income dropdown uniqueness | HIGH |
| 44-46 | HP annual value computations | HIGH |
| 66-73 | Exempt allowances limits | HIGH |
| 78-87 | 80G detailed validations | HIGH |
| 107 | IFSC code validation (RBI) | MEDIUM |
| 144, 118 | 80GGA/80GGC PAN validations | HIGH |
| 213-214 | Aadhaar matching | LOW |
| 220-245 | Detailed schedule field matching | HIGH |
| 261-263 | HRA exemption computation | HIGH |
| 295-300 | Co-ownership validations | HIGH |
| 302-319 | Exempt income dropdowns | MEDIUM |
| 325-326 | IFSC for non-cash donations | MEDIUM |
| 331-334 | Representative details | MEDIUM |

### 3. SPECIFIC FIELD-LEVEL GAPS

1. **AadhaarCardNo** - Field not in schema
2. **SeventhProvisio139** fields - Not implemented
3. **ReceiptNo** - For revised returns
4. **NoticeNo/NoticeDateUnderSec** - For 148 notices
5. **Detailed 80G/80GGA donee PAN validation** - Need cross-check
6. **IFSC Code Validation** - Against RBI database
7. **HRA Schedule Details** - Exact computation per rules 261-263

---

================================================================================
## ITR-2 - ITEMS REMAINING
================================================================================

### 1. SCHEDULES NOT FULLY IMPLEMENTED

| Schedule | Status | Gap |
|----------|--------|-----|
| Schedule FSI | PARTIAL | Country-wise income mapping |
| Schedule FA | PARTIAL | Foreign asset details |
| Schedule SPI | PARTIAL | Clubbing details |
| Schedule 5A | NOT FOUND | Portuguese Civil Code |
| Schedule ESOP | NOT FOUND | Employee stock options |
| Schedule PTI | PARTIAL | Pass-through income |

### 2. VALIDATION RULES (~80+ rules)

From CBDT ITR-2 rules:

| Category | Description | Priority |
|----------|-------------|----------|
| Schedule 112A | Detailed column computations (6,7,9,11,13,14) | HIGH |
| Schedule 115AD | Column computations | HIGH |
| Schedule VDA | VDA income details | HIGH |
| Schedule FSI | Country-income mapping | MEDIUM |
| Schedule FA | Asset-details validation | MEDIUM |
| Schedule SI | Special rate income | MEDIUM |
| Schedule EI | Exempt income dropdowns | MEDIUM |

### 3. FIELD-LEVEL GAPS

1. **Schedule FSI** - Need detailed country-wise income
2. **Schedule TR1** - Need tax relief computation
3. **Schedule FA** - Foreign asset declarations
4. **Schedule 5A** - Not implemented
5. **Schedule ESOP** - Not implemented
6. **Detailed 112A columns** - Need full column mapping

---

================================================================================
## ITR-3 - ITEMS REMAINING
================================================================================

### 1. SCHEDULES NOT FULLY IMPLEMENTED

| Schedule | Status | Gap |
|----------|--------|-----|
| PartA_OI | NOT FOUND | Other Information |
| PartA_QD | NOT FOUND | Quantitative Details |
| ScheduleBP | PARTIAL | Business income computation |
| ScheduleDCG | NOT FOUND | Deemed capital gains u/s 50 |
| ScheduleESR | NOT FOUND | Scientific research |
| ScheduleIF | PARTIAL | Firm income details |
| ScheduleUD | NOT FOUND | Unabsorbed depreciation |
| ScheduleGST | NOT FOUND | GSTIN-wise turnover |
| Schedule10AA | PARTIAL | SEZ deduction details |

### 2. VALIDATION RULES

| Rule Category | Description | Priority |
|--------------|-------------|----------|
| PartA_BS | Balance sheet validations | HIGH |
| PartA_PL | P&L validations | HIGH |
| PartA_OI | Other info validations | MEDIUM |
| PartA_QD | Quantitative details | MEDIUM |
| ScheduleGST | GST schedule | HIGH |
| Depreciation | Block-wise validations | HIGH |
| ICDS | ICDS adjustments | MEDIUM |

### 3. FIELD-LEVEL GAPS

1. **PartA_OI** - Business information details
2. **PartA_QD** - For audit cases u/s 44AB
3. **ScheduleGST** - GSTIN-wise turnover
4. **ScheduleDCG** - Deemed capital gains
5. **ScheduleESR** - Scientific research expenditure
6. **ScheduleUD** - Unabsorbed depreciation
7. **Detailed depreciation blocks** - Need full WDV computation

---

================================================================================
## ITR-4 (SUGAM) - ITEMS REMAINING
================================================================================

### 1. VALIDATION RULES (~40 rules)

From CBDT ITR-4 rules:

| Rule No | Description | Priority |
|---------|-------------|----------|
| Various | 44AD turnover limits | HIGH |
| Various | 44ADA receipts limits | HIGH |
| Various | 44AE vehicle validation | HIGH |
| HP | Co-ownership validations | HIGH |
| 80G | Detailed PAN validation | MEDIUM |
| EI | Exempt income dropdowns | MEDIUM |

### 2. FIELD-LEVEL GAPS

1. **Schedule BP** - Presumptive business computation details
2. **GST Schedule** - Not implemented
3. **Detailed 44AD/44ADA computations** - Need turnover splits
4. **44AE vehicle validation** - Max 10 vehicles

---

================================================================================
## SUMMARY - EXACT ITEMS TO IMPLEMENT
================================================================================

### HIGH PRIORITY

1. **ITR-1:**
   - Schedule 10(13A) HRA detailed computation
   - Exempt income dropdown uniqueness validations
   - Co-ownership HP validations
   - 80G detailed PAN validations
   - Field matching validations (220-245)

2. **ITR-2:**
   - Schedule 112A detailed columns
   - Schedule FA (Foreign Assets)
   - Schedule FSI (Foreign Salary Income)
   - Schedule TR1 (Tax Relief)
   - Schedule 5A (Portuguese Civil Code)
   - Schedule ESOP

3. **ITTR-3:**
   - PartA_OI (Other Information)
   - PartA_QD (Quantitative Details)
   - ScheduleGST (GST turnover)
   - ScheduleDCG (Deemed CG)
   - ScheduleESR (Scientific Research)
   - ScheduleUD (Unabsorbed Depreciation)

4. **ITR-4:**
   - Detailed 44AD/44ADA validations
   - GST schedule integration
   - 44AE vehicle limit validation

### MEDIUM PRIORITY

1. Aadhaar-PAN linking validation
2. IFSC code validation (RBI database)
3. Name matching with PAN database
4. Representative assessee details
5. Detailed exempt income dropdowns

### LOW PRIORITY

1. TaxReturnPreparer section
2. Form 10E for relief u/s 89(1)
3. Notification-based validations

---

*Generated: July 20 2026*
