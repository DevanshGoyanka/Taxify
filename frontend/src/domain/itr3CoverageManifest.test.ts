import { describe, expect, it } from 'vitest'
import { ITR3_COVERAGE_MANIFEST, ITR3_OFFICIAL_PATH_COUNT } from './itr3CoverageManifest'

const DISPOSITIONS = new Set(['dedicated-input', 'generic-input', 'computed', 'backend-computed', 'imported', 'metadata', 'backend-only', 'missing'])

describe('official ITR-3 frontend coverage manifest', () => {
  it('covers all official PARTA_QD paths with explicit source ownership', () => {
    const qd = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'PARTA_QD');
    expect(qd).toHaveLength(28);
    expect(qd.every((entry) => entry.disposition !== 'missing')).toBe(true);
    expect(qd.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true);
    expect(qd.filter((entry) => !entry.array && !entry.object).every((entry) => entry.disposition === 'dedicated-input')).toBe(true);
  });

  it('contains every official recursive path exactly once', () => {
    expect(ITR3_OFFICIAL_PATH_COUNT).toBe(2936)
    expect(ITR3_COVERAGE_MANIFEST).toHaveLength(2936)
    const paths = ITR3_COVERAGE_MANIFEST.map((entry) => entry.path)
    expect(new Set(paths).size).toBe(paths.length)
    for (const entry of ITR3_COVERAGE_MANIFEST) {
      expect(entry.path).toContain(`${entry.schedule}.`)
      expect(DISPOSITIONS.has(entry.disposition)).toBe(true)
      expect(Array.isArray(entry.enumValues)).toBe(true)
    }
  })

  it('covers all 176 official PARTA_PL paths with no unsupported gaps', () => {
    const pl = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'PARTA_PL')
    expect(pl).toHaveLength(176)
    expect(pl.some((entry) => entry.disposition === 'missing')).toBe(false)
    expect(pl.filter((entry) => entry.disposition === 'dedicated-input')).toHaveLength(144)
    expect(pl.filter((entry) => entry.disposition === 'computed')).toHaveLength(23)
    expect(pl.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(pl.filter((entry) => ['PBIDTA', 'PBT', 'ProfitAfterTax', 'TotCreditsToPL'].includes(entry.fieldName)).every((entry) => entry.disposition === 'computed')).toBe(true)
  })

  it('protects PARTA_PL computed rows from the dedicated editor', () => {
    const pl = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'PARTA_PL')
    expect(pl.filter((entry) => entry.disposition === 'computed').every((entry) => !entry.array && !entry.object)).toBe(true)
  })

  it('classifies all 132 official Schedule FA paths across ten categories', () => {
    const fa = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleFA')
    expect(fa).toHaveLength(132)
    expect(fa.every((entry) => entry.disposition !== 'missing')).toBe(true)
    expect(fa.filter((entry) => entry.disposition === 'backend-only')).toHaveLength(10)
    expect(fa.filter((entry) => entry.disposition === 'backend-computed').length).toBeGreaterThan(0)
    expect(fa.filter((entry) => entry.disposition === 'dedicated-input').length).toBeGreaterThan(0)
    for (const category of ['DetailsForiegnBank', 'DtlsForeignCustodialAcc', 'DtlsForeignEquityDebtInterest', 'DtlsForeignCashValueInsurance', 'DetailsFinancialInterest', 'DetailsImmovableProperty', 'DetailsOfAccntsHvngSigningAuth', 'DetailsOfTrustOutIndiaTrustee', 'DetailsOfOthSourcesIncOutsideIndia', 'DetailsOthAssets']) {
      expect(fa.some((entry) => entry.path === `ScheduleFA.${category}`)).toBe(true)
    }
    expect(fa.filter((entry) => entry.fieldName === 'CountryName').every((entry) => entry.disposition === 'backend-computed')).toBe(true)
    expect(fa.filter((entry) => ['IncTaxSch', 'IncTaxSchNo', 'IncOfferedSch', 'IncOfferedSchNo'].includes(entry.fieldName)).every((entry) => entry.disposition === 'backend-computed')).toBe(true)
  })
  it('classifies mandatory Part A and Verification paths explicitly', () => {
    for (const schedule of ['PartA_GEN1', 'PartA_GEN2']) {
      const entries = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === schedule)
      expect(entries.length).toBeGreaterThan(0)
      expect(entries.every((entry) => entry.disposition !== 'missing')).toBe(true)
      expect(entries.filter((entry) => !entry.array && !entry.object).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    }
    const verification = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'Verification')
    expect(verification).toHaveLength(6)
    expect(verification.filter((entry) => ['Verification.Capacity', 'Verification.Date', 'Verification.Place'].includes(entry.path)).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    expect(verification.filter((entry) => !['Verification.Capacity', 'Verification.Date', 'Verification.Place'].includes(entry.path)).every((entry) => entry.disposition === 'backend-only')).toBe(true)
  })

  it('covers every Schedule CG path with explicit ownership and protects computed outputs', () => {
    const cg = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleCGFor23')
    expect(cg).toHaveLength(390)
    expect(cg.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(cg.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    for (const terminal of ['TotalSTCG', 'TotalLTCG', 'TotScheduleCGFor23', 'SumOfCGIncm', 'CapgainonAssets', 'ExemptionGrandTotal']) {
      expect(cg.filter((entry) => entry.fieldName === terminal).every((entry) => entry.disposition === 'computed')).toBe(true)
    }
    expect(cg.filter((entry) => entry.path.startsWith('ScheduleCGFor23.AccruOrRecOfCG.')).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
  })

  it('covers every official Schedule S and Schedule HP path with explicit ownership', () => {
    for (const [schedule, expectedLength] of [['ScheduleS', 51], ['ScheduleHP', 47]] as const) {
      const entries = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === schedule)
      expect(entries).toHaveLength(expectedLength)
      expect(entries.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
      expect(entries.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
      expect(entries.some((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    }
    const protectedTerminals = ['TotalGrossSalary', 'NetSalary', 'TotIncUnderHeadSalaries', 'GrossAnnualValue', 'NetAnnualValue', 'StandardDeduction30Pct', 'TotalIncomeChargeableUnHP']
    for (const terminal of protectedTerminals) {
      expect(ITR3_COVERAGE_MANIFEST.filter((entry) => entry.fieldName === terminal).every((entry) => entry.disposition === 'computed')).toBe(true)
    }
  })
  it('covers every official Schedule ESOP path and protects computed outputs', () => {
    const esop = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleESOP')
    expect(esop).toHaveLength(60)
    expect(esop.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(esop.filter((entry) => entry.required && entry.disposition === 'missing')).toHaveLength(0)
    expect(esop.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(esop.filter((entry) => entry.disposition === 'computed').length).toBeGreaterThan(0)
    expect(esop.filter((entry) => entry.disposition === 'imported').length).toBeGreaterThan(0)
    for (const terminal of ['TaxPayableCurrentAY', 'BalanceTaxCF', 'TotalTaxAttributedAmt']) {
      expect(esop.filter((entry) => entry.fieldName === terminal).every((entry) => entry.disposition === 'computed')).toBe(true)
    }
    for (const terminal of ['PanofStartUp', 'DPIITRegNo', 'SecurityType', 'CeasedEmployee', 'DateOfCeasing']) {
      expect(esop.filter((entry) => entry.fieldName === terminal).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    }
    expect(esop.filter((entry) => entry.fieldName === 'TaxDeferredBFEarlierAY').every((entry) => entry.disposition === 'imported')).toBe(true)
  })

  it('covers all 30 mandatory Schedule ESR paths and protects statutory outputs', () => {
    const esr = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleESR')
    expect(esr).toHaveLength(30)
    expect(esr.every((entry) => entry.required)).toBe(true)
    expect(esr.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(esr.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(esr.filter((entry) => entry.fieldName === 'AmtDebPL').every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    expect(esr.filter((entry) => ['AmtUs35Allowable', 'ExcessAmtOverDebPL'].includes(entry.fieldName)).every((entry) => entry.disposition === 'computed')).toBe(true)
    expect(esr.filter((entry) => entry.fieldName === 'AmtUs35Allowable').length).toBe(10)
    expect(esr.filter((entry) => entry.fieldName === 'ExcessAmtOverDebPL').length).toBe(10)
  })
  it('covers both official Schedule 112A and Schedule 115AD paths with explicit ownership', () => {
    for (const schedule of ['Schedule112A', 'Schedule115AD']) {
      const entries = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === schedule)
      expect(entries).toHaveLength(23)
      expect(entries.filter((entry) => entry.required)).toHaveLength(20)
      expect(entries.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
      expect(entries.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
      expect(entries.filter((entry) => entry.disposition === 'dedicated-input').map((entry) => entry.fieldName)).toEqual(expect.arrayContaining(['ShareOnOrBefore', 'ISINCode', 'ShareUnitName', 'NumSharesUnits', 'SalePricePerShareUnit', 'TotSaleValue', 'CostAcqWithoutIndx', 'FairMktValuePerShareunit', 'ExpExclCnctTransfer']))
      expect(entries.filter((entry) => entry.disposition === 'computed').map((entry) => entry.fieldName)).toEqual(expect.arrayContaining(['AcquisitionCost', 'LTCGBeforelower6and11', 'TotFairMktValueCapAst', 'TotalDeductions', 'Balance']))
    }
  })
  it('covers every official Schedule 80-IC path and protects computed deduction values', () => {
    const schedule = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'Schedule80_IC')
    expect(schedule).toHaveLength(27)
    expect(schedule.filter((entry) => entry.required)).toHaveLength(19)
    expect(schedule.every((entry) => entry.disposition !== 'missing')).toBe(true)
    expect(schedule.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(schedule.filter((entry) => ['DeductAmountSec80', 'TotDeductInNorthEast', 'TotSchedule80_IC'].includes(entry.fieldName)).every((entry) => entry.disposition === 'computed')).toBe(true)
    expect(schedule.filter((entry) => ['Sch80SectionCode', 'Sch80LocOrDescCode'].includes(entry.fieldName)).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
  })
  it('covers every official Schedule DCG path as protected computed output', () => {
    const dcg = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleDCG')
    expect(dcg).toHaveLength(13)
    expect(dcg.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(dcg.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(dcg.filter((entry) => !entry.array && !entry.object).every((entry) => entry.disposition === 'computed')).toBe(true)
    expect(dcg.filter((entry) => entry.required).length).toBeGreaterThan(0)
  })

  it('covers every official Schedule VDA path with editable facts and protected gains', () => {
    const vda = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleVDA')
    expect(vda).toHaveLength(9)
    expect(vda.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(vda.find((entry) => entry.fieldName === 'ScheduleVDADtls')?.disposition).toBe('backend-only')
    expect(vda.filter((entry) => ['DateofAcquisition', 'DateofTransfer', 'AcquisitionCost', 'ConsidReceived', 'HeadUndIncTaxed'].includes(entry.fieldName)).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    expect(vda.filter((entry) => ['IncomeFromVDA', 'TotIncBusiness', 'TotIncCapGain'].includes(entry.fieldName)).every((entry) => entry.disposition === 'computed')).toBe(true)
  })

  it('covers every official Schedule IF path with identity inputs and protected allocations', () => {
    const schedule = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleIF')
    expect(schedule).toHaveLength(14)
    expect(schedule.filter((entry) => entry.required)).toHaveLength(7)
    expect(schedule.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    expect(schedule.find((entry) => entry.path === 'ScheduleIF.PartnerFirmDetails')?.disposition).toBe('backend-only')
    expect(schedule.filter((entry) => entry.path.includes('PartnerFirmDetails[].') && !entry.array && !entry.object && entry.fieldName !== 'ProfitShareAmt').every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    expect(schedule.filter((entry) => ['ProfitShareAmt', 'TotalProfitShareAmt', 'TotalIntrstAmtDueOrRecv', 'TotalRemunernAmtDueOrRecv', 'TotalFirmCapBalOn31Mar'].includes(entry.fieldName)).every((entry) => entry.disposition === 'computed')).toBe(true)
  })
  it('closes optional Schedule GST, ICDS, SPI, and TPSA paths with protected outputs', () => {
    for (const schedule of ['ScheduleGST', 'ScheduleICDS', 'ScheduleSPI', 'ScheduleTPSA']) {
      const entries = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === schedule)
      expect(entries.length).toBeGreaterThan(0)
      expect(entries.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
      expect(entries.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    }
    const icds = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleICDS')
    expect(icds.filter((entry) => ['IncreaseInProfit', 'DecreaseInProfit'].includes(entry.fieldName)).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
    expect(icds.filter((entry) => entry.fieldName === 'NetEffect').every((entry) => entry.disposition === 'computed')).toBe(true)
    const tpsa = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleTPSA')
    expect(tpsa.filter((entry) => ['TotalAdditionalTax', 'NetTaxPayable', 'TotalAmountDeposited'].includes(entry.fieldName)).every((entry) => entry.disposition === 'backend-computed')).toBe(true)
  })

  it('protects computed and backend-only paths from editable classification', () => {
    const computed = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.disposition === 'computed')
    expect(computed.length).toBeGreaterThan(0)
    expect(computed.some((entry) => entry.path === 'PartB-TI.TotalIncome')).toBe(true)
    expect(ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'Form_ITR3').every((entry) => entry.disposition === 'backend-only')).toBe(true)
  })
  it('classifies all 77 Schedule VIA paths by ownership', () => {
    const via = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleVIA')
    expect(via).toHaveLength(77)
    expect(via.filter((entry) => entry.disposition === 'dedicated-input')).toHaveLength(38)
    expect(via.filter((entry) => entry.disposition === 'computed')).toHaveLength(37)
    expect(via.filter((entry) => entry.disposition === 'backend-only')).toHaveLength(2)
    expect(via.filter((entry) => entry.disposition === 'missing')).toHaveLength(0)
    for (const terminal of ['TotPartBchapterVIA', 'TotPartCchapterVIA', 'TotPartCAandDchapterVIA', 'TotalChapVIADeductions']) {
      expect(via.filter((entry) => entry.fieldName === terminal).every((entry) => entry.disposition === 'computed')).toBe(true)
    }
    expect(via.filter((entry) => entry.path.includes('.DeductUndChapVIA.')).every((entry) => entry.disposition === 'computed')).toBe(true)
    expect(via.filter((entry) => entry.path.includes('.UsrDeductUndChapVIA.') && !entry.array && !entry.object && !['TotPartBchapterVIA', 'TotPartCchapterVIA', 'TotPartCAandDchapterVIA', 'TotalChapVIADeductions'].includes(entry.fieldName)).every((entry) => entry.disposition === 'dedicated-input')).toBe(true)
  })

  it('covers every official user-suppliable Schedule VIA section', () => {
    const sections = ['80C', '80CCC', '80CCD1B', '80CCDEmployeeOrSE', '80CCDEmployer', '80D', '80DD', '80DDB', '80E', '80EE', '80EEA', '80EEB', '80G', '80GG', '80GGA', '80GGC', '80IA', '80IAB', '80IB', '80IBA', '80IC', '80JJA', '80JJAA', '80QQB', '80RRB', '80TTA', '80TTB', '80U']
    const via = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleVIA')
    for (const section of sections) expect(via.some((entry) => entry.path === `ScheduleVIA.UsrDeductUndChapVIA.Section${section}`)).toBe(true)
    expect(via.some((entry) => entry.path === 'ScheduleVIA.UsrDeductUndChapVIA.AnyOthSec80CCH')).toBe(true)
  })

  it('covers every mandatory PARTA_BS scalar without falsely covering structures', () => {
    const bs = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'PARTA_BS')
    expect(bs.filter((entry) => entry.required && entry.disposition === 'missing')).toHaveLength(0)
    expect(bs.filter((entry) => entry.array || entry.object).every((entry) => entry.disposition === 'backend-only')).toBe(true)
    expect(bs.some((entry) => entry.path.endsWith('CashinHand') && entry.disposition === 'dedicated-input')).toBe(true)
    expect(bs.some((entry) => entry.path.endsWith('TotFundSrc') && entry.disposition === 'computed')).toBe(true)
  })
})
