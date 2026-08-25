# Bugfix Requirements Document: ITR Computation Compliance Verification

## Introduction

The ITR computation engine has achieved excellent architectural design (9.8/10 computation flow, 10/10 separation of concerns, 10/10 JSON mapping design, 9.5/10 maintainability) but requires comprehensive verification and compliance checking before production deployment. The system correctly follows the flow: ITR1Input → compute_itr1() → ITR1Result → build_itr1_json() → Official ITR JSON, with proper separation between computation, storage, and serialization layers.

However, exhaustive testing has revealed compliance gaps in edge-case tax rule scenarios where the system's calculations do not reconcile exactly with the official ITR utility. These gaps must be identified and resolved to ensure 100% compliance across comprehensive test cases before the system can be considered production-ready.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN CBDT rounding rules are applied at computation stages THEN the system produces results that differ from official ITR utility calculations

1.2 WHEN 87A rebate interacts with 112A tax calculations THEN the system fails to apply correct eligibility limits and interaction rules

1.3 WHEN marginal relief calculations are performed for surcharge scenarios THEN the system produces incorrect relief amounts compared to official utility

1.4 WHEN agricultural income is used for rate computation in ITR-1 eligibility THEN the system incorrectly determines form eligibility

1.5 WHEN clubbing provisions are applied to income sources THEN the system fails to map provisions correctly to the computation engine

1.6 WHEN Schedule EI (exempt income) entries are processed THEN the system has incomplete mapping causing missing exempt income categories

1.7 WHEN relief u/s 89 tax computation is calculated THEN the system produces incorrect interaction with regular tax computation

1.8 WHEN relief u/s 90/90A/91 is applied THEN the system lacks proper support verification mechanisms

1.9 WHEN ITR-1 eligibility checks are performed THEN the system fails validation for edge cases with multiple income sources

1.10 WHEN tax paid challan reconciliation is executed THEN the system produces incorrect matching against TDS/advance tax entries

1.11 WHEN refund amount calculation is performed THEN the system shows discrepancies compared to official ITR utility computation

### Expected Behavior (Correct)

2.1 WHEN CBDT rounding rules are applied at computation stages THEN the system SHALL apply rounding at every prescribed stage exactly as per CBDT notifications

2.2 WHEN 87A rebate interacts with 112A tax calculations THEN the system SHALL correctly apply eligibility limits and interaction rules as per Income Tax Act provisions

2.3 WHEN marginal relief calculations are performed for surcharge scenarios THEN the system SHALL compute relief amounts that match official ITR utility exactly

2.4 WHEN agricultural income is used for rate computation in ITR-1 eligibility THEN the system SHALL correctly determine form eligibility based on agricultural income thresholds

2.5 WHEN clubbing provisions are applied to income sources THEN the system SHALL map all clubbing provisions correctly to the computation engine

2.6 WHEN Schedule EI (exempt income) entries are processed THEN the system SHALL have complete mapping for all exempt income categories per ITR schema

2.7 WHEN relief u/s 89 tax computation is calculated THEN the system SHALL compute correct interaction with regular tax computation

2.8 WHEN relief u/s 90/90A/91 is applied THEN the system SHALL provide proper support verification for international tax relief

2.9 WHEN ITR-1 eligibility checks are performed THEN the system SHALL validate correctly for all edge cases with multiple income sources

2.10 WHEN tax paid challan reconciliation is executed THEN the system SHALL produce correct matching against TDS/advance tax entries

2.11 WHEN refund amount calculation is performed THEN the system SHALL show exact reconciliation with official ITR utility computation

### Unchanged Behavior (Regression Prevention)

3.1 WHEN standard salary income computation is performed THEN the system SHALL CONTINUE TO calculate gross total income correctly for straightforward cases

3.2 WHEN house property income without complex scenarios is calculated THEN the system SHALL CONTINUE TO apply standard deductions and net annual value calculations

3.3 WHEN other sources income from savings accounts is processed THEN the system SHALL CONTINUE TO handle TDS and exemptions correctly

3.4 WHEN Chapter VI-A deductions under sections 80C, 80D are claimed THEN the system SHALL CONTINUE TO apply limits and validations correctly

3.5 WHEN basic tax computation without rebate or relief is performed THEN the system SHALL CONTINUE TO calculate tax liability accurately

3.6 WHEN standard TDS entries are processed THEN the system SHALL CONTINUE TO match and reconcile correctly with Form 16/16A

3.7 WHEN JSON serialization for ITR submission is executed THEN the system SHALL CONTINUE TO maintain correct field mapping and structure

3.8 WHEN computation flow through all layers is executed THEN the system SHALL CONTINUE TO maintain proper separation of concerns

3.9 WHEN basic ITR-1 eligibility for simple cases is checked THEN the system SHALL CONTINUE TO validate eligibility correctly

3.10 WHEN standard cess and surcharge calculations are performed THEN the system SHALL CONTINUE TO apply rates and thresholds correctly