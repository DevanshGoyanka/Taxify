import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import {
  applyLegacyPatch, banksFromManager, banksToManager, challansToManager,
  composeLegacyPayload, createReturnEditorModel, createReturnEditorModelFromLegacy,
  deductionLoansFromManager, deductionLoansToManager, familyPensionFromManager,
  familyPensionToManager, giftsFromManager, giftsToManager, interestFromManager,
  interestToManager, patchCompatibilityExtras, replaceChallanKind, tdsFromManager,
  tdsToManager, updateEmployers, updateHouseProperties, winningsFromManager,
  winningsToManager,
} from './editorModel';
import type { DeductionLoan, InterestIncome, TaxChallan, TdsCredit } from './types';

const interest = (id = 'interest-1'): InterestIncome => ({ id, kind: 'NSC', grossAmount: 100, tdsDeducted: 10, bankName: 'Bank', accountType: 'FD', accountNumber: '1', ifscCode: 'IFSC', postOfficeName: 'PO', accountNumberPO: '2', nscCertificateNumber: 'CERT', yearOfPurchase: 2020, scssAccountNumber: '3', dateOfOpening: '2020-01-01', deductorName: 'D', deductorTAN: 'TAN', remarks: 'keep' });
const tds = (): TdsCredit => ({ id: 'tds-1', section: '194A', deductorName: 'Bank', deductorTAN: 'TAN', deductorPAN: 'ABCDE1234F', certificateNo: 'CERT-1', grossAmount: 1000, taxDeducted: 100, deductionDate: '2025-01-01', uniqueTransactionNo: 'UTN', financialYear: '2025-26', verified26AS: true, claimedInReturn: true });

function loan(section: DeductionLoan['section'], id: string): DeductionLoan {
  return { id, section, loanTakenFrom: 'B', lenderName: 'Lender', lenderPAN: 'ABCDE1234F', loanAccountNo: 'ACC', dateOfLoan: '2025-01-01', totalLoanAmount: 100, outstandingAmount: 80, interestAmount: 10, firstTimeBuyerEligible: true, vehicleRegNo: 'MH01AB1234' };
}

describe('return editor model', () => {
  it('loads unknown fields and gives canonical values precedence over extras', () => {
    const model = createReturnEditorModelFromLegacy({ name: 'Canonical', future: { enabled: true } });
    const patched = patchCompatibilityExtras(model, { name: 'Wrong', employerEntries: [{ id: 'bad' }], future2: 7 });
    expect(composeLegacyPayload(patched)).toMatchObject({ name: 'Canonical', employerEntries: [], future: { enabled: true }, future2: 7 });
  });

  it('performs detached immutable updates and allows sequential updates to survive', () => {
    const model = createReturnEditorModel(createEmptyReturnDraft());
    const employers = [{ ...createEmptyReturnDraft().employers[0] }].filter(Boolean);
    const first = updateEmployers(model, employers);
    const properties = createEmptyReturnDraft().houseProperties;
    const second = updateHouseProperties(first, properties);
    properties.push({} as never);
    expect(model).not.toBe(first);
    expect(first.draft).not.toBe(second.draft);
    expect(second.draft.employers).toEqual(employers);
    expect(second.draft.houseProperties).toEqual([]);
  });

  it('preserves unknown fields nested inside canonical records', () => {
    const model = createReturnEditorModelFromLegacy({
      employerEntries: [{ id: 'e', employerName: 'A', basic: 100, futurePayrollCode: 'X' }],
    });
    const updated = updateEmployers(model, [{ ...model.draft.employers[0], basic: 200 }]);
    const payload = composeLegacyPayload(updated);
    expect((payload.employerEntries as Array<Record<string, unknown>>)[0]).toMatchObject({
      id: 'e',
      basic: 200,
      futurePayrollCode: 'X',
    });
  });

  it('deep merges partial legacy patches without resetting sibling schedule fields', () => {
    const model = createReturnEditorModelFromLegacy({
      filing: { filingSection: '139(5)', returnType: 'REVISED', originalAcknowledgementNumber: 'ACK' },
      section80D: {
        selfSeniorCitizen: 'Y',
        selfFamily: { policies: [], preventiveCheckup: 1000, medicalExpense: 2000 },
      },
    });
    const updated = applyLegacyPatch(model, {
      filing: { noticeNumber: 'NOTICE' },
      section80D: { selfFamily: { preventiveCheckup: 1500 } },
    });
    expect(updated.draft.filing).toMatchObject({
      filingSection: '139(5)',
      returnType: 'REVISED',
      originalAcknowledgementNumber: 'ACK',
      noticeNumber: 'NOTICE',
    });
    expect(updated.draft.deductions.section80D.selfFamily).toMatchObject({
      preventiveCheckup: 1500,
      medicalExpense: 2000,
    });
  });

  it('atomically applies legacy patches without losing unrelated edits or unknown extras', () => {
    const initial = createReturnEditorModelFromLegacy({ name: 'A', future: 'keep', employerEntries: [{ id: 'e', employerName: 'Old', commission: 9 }] });
    const updated = applyLegacyPatch(initial, { name: 'B', interestEntries: [{ id: 'i', itdTag: 'NSC', grossAmount: 50 }] });
    expect(composeLegacyPayload(updated)).toMatchObject({ name: 'B', future: 'keep' });
    expect(updated.draft.employers[0]).toMatchObject({ id: 'e', employerName: 'Old', commission: 9 });
    expect(updated.draft.otherSources.interest[0]).toMatchObject({ id: 'i', kind: 'NSC', grossAmount: 50 });
  });

  it('round trips interest aliases and preserves manager-hidden fields by ID without mutation', () => {
    const canonical = [interest()];
    const manager = interestToManager(canonical);
    const before = structuredClone(manager);
    manager[0] = { id: 'interest-1', itdTag: 'SAVINGS_BANK', grossAmount: 200, tdsDeducted: 20, bankName: 'New' };
    const result = interestFromManager(manager, canonical);
    expect(result[0]).toMatchObject({ kind: 'SAVINGS_BANK', grossAmount: 200, bankName: 'New', remarks: 'keep', nscCertificateNumber: 'CERT' });
    expect(before[0]).toMatchObject({ itdTag: 'NSC', grossAmount: 100 });
    expect(canonical[0]).toEqual(interest());
  });

  it('round trips family pension, winnings, and gifts while preserving hidden values', () => {
    expect(familyPensionFromManager(familyPensionToManager({ grossAmount: 90, payerName: 'P', relationToPensioner: 'Spouse' }))).toEqual({ grossAmount: 90, payerName: 'P', relationToPensioner: 'Spouse' });
    const winnings = [{ id: 'w', type: 'LOTTERY' as const, grossAmount: 20, tdsDeducted: 2, payerName: 'P', payerTAN: 'T', dateOfWinning: '2025-01-01' }];
    const winningManager = winningsToManager(winnings);
    delete winningManager[0].payerTAN;
    expect(winningsFromManager(winningManager, winnings)[0]).toMatchObject({ payerTAN: 'T', dateOfWinning: '2025-01-01' });
    const gifts = [{ id: 'g', propertyType: 'CASH' as const, value: 70, donorName: 'D', donorRelation: 'Friend', dateOfReceipt: '2025-02-01', description: 'Gift', fromRelative: false, receivedOnMarriage: true }];
    const giftManager = giftsToManager(gifts);
    delete giftManager[0].donorRelation;
    expect(giftsFromManager(giftManager, gifts)[0]).toMatchObject({ donorRelation: 'Friend', receivedOnMarriage: true });
  });

  it('round trips all grouped deduction loans including 80EEA stamp duty', () => {
    const canonical = { loans: [loan('80E', 'e'), loan('80EE', 'ee'), loan('80EEA', 'eea'), loan('80EEB', 'eeb')], section80EEAStampDutyValue: 4500000 };
    const manager = deductionLoansToManager(canonical);
    const before = structuredClone(manager);
    manager.section80EEA.loans[0].interestAmount = 25;
    const result = deductionLoansFromManager(manager, canonical);
    expect(result.section80EEAStampDutyValue).toBe(4500000);
    expect(result.loans.map((entry) => entry.section)).toEqual(['80E', '80EE', '80EEA', '80EEB']);
    expect(result.loans.find((entry) => entry.id === 'eea')).toMatchObject({ interestAmount: 25, lenderPAN: 'ABCDE1234F' });
    expect(before.section80EEA.loans[0].interestAmount).toBe(10);
  });

  it('round trips TDS aliases and UI-only PAN/certificate fields through serialization', () => {
    const canonical = [tds()];
    const manager = tdsToManager(canonical);
    manager[0] = { ...manager[0], incomeAmount: 2000, tdsDeducted: 200 };
    const result = tdsFromManager(manager, canonical);
    expect(result[0]).toMatchObject({ grossAmount: 2000, taxDeducted: 200, deductorPAN: 'ABCDE1234F', certificateNo: 'CERT-1', uniqueTransactionNo: 'UTN' });
    const draft = createEmptyReturnDraft();
    draft.taxes.tds = result;
    const reloaded = createReturnEditorModelFromLegacy(composeLegacyPayload(createReturnEditorModel(draft)));
    expect(reloaded.draft.taxes.tds[0]).toMatchObject({ deductorPAN: 'ABCDE1234F', certificateNo: 'CERT-1' });
  });

  it('replaces advance and self-assessment challans independently and supports challanNo alias', () => {
    const challans: TaxChallan[] = [
      { id: 'a', kind: 'ADVANCE_TAX', bsrCode: '1', depositDate: '2025-06-15', challanSerialNo: '10', amount: 100, cin: 'A' },
      { id: 's', kind: 'SELF_ASSESSMENT', bsrCode: '2', depositDate: '2026-07-01', challanSerialNo: '20', amount: 200, cin: 'S' },
    ];
    const advance = replaceChallanKind(challans, 'ADVANCE_TAX', [{ id: 'a', amount: 150, challanNo: 11 }]);
    expect(advance.find((entry) => entry.kind === 'SELF_ASSESSMENT')).toEqual(challans[1]);
    expect(advance.find((entry) => entry.id === 'a')).toMatchObject({ amount: 150, challanSerialNo: '11', bsrCode: '1' });
    const projectedSelf = challansToManager(advance, 'SELF_ASSESSMENT');
    projectedSelf[0] = { ...projectedSelf[0], challanNo: '21', amount: 250 };
    const self = replaceChallanKind(advance, 'SELF_ASSESSMENT', projectedSelf);
    expect(challansToManager(self, 'ADVANCE_TAX')[0]).toMatchObject({ amount: 150, challanNo: '11' });
    expect(self.find((entry) => entry.id === 's')).toMatchObject({ amount: 250, challanSerialNo: '21' });
  });

  it('normalizes the self-assessment challanNo alias from a direct legacy payload', () => {
    const model = createReturnEditorModelFromLegacy({
      selfAssessmentTaxEntries: [{ id: 's', bsrCode: '1234567', challanNo: 42, amount: 500 }],
    });
    expect(model.draft.taxes.challans[0]).toMatchObject({
      id: 's',
      kind: 'SELF_ASSESSMENT',
      challanSerialNo: '42',
      amount: 500,
    });
  });

  it('round trips detached bank account wrappers', () => {
    const accounts = [{ id: 'b', bankName: 'Bank', accountNumber: '1', ifscCode: 'IFSC', accountType: 'SB' as const, useForRefund: true }];
    const wrapper = banksToManager(accounts);
    wrapper.accounts[0].bankName = 'Changed';
    const result = banksFromManager(wrapper);
    wrapper.accounts[0].bankName = 'Again';
    expect(accounts[0].bankName).toBe('Bank');
    expect(result[0].bankName).toBe('Changed');
  });

  it('generates deterministic IDs for adapter input without IDs', () => {
    const entry = { id: '', itdTag: 'OTHER' as const, grossAmount: 1, tdsDeducted: 0 };
    expect(interestFromManager([entry])[0].id).toBe(interestFromManager([entry])[0].id);
  });
});
