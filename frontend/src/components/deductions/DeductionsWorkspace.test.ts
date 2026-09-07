import { describe, expect, it } from 'vitest';
import { money, category80DTotal } from './DeductionsWorkspace';
import type { Category80D, Investment80C, Donation80G } from '../../domain/returns/types';

describe('money() — backend Decimal-as-string coercion', () => {
  it('parses a numeric string, matching the real wire shape of a loaded draft', () => {
    expect(money('839')).toBe(839);
    expect(money('157')).toBe(157);
  });

  it('sums two backend-serialized string amounts correctly when each is coerced first', () => {
    // Each 80TTA/80TTB-style section header in DeductionsWorkspace.tsx computes
    // its summary as money(a) + money(b), not (a + b) then formatted. Before
    // the fix, several of these headers did raw `a + b` on the two chapterVIA
    // string fields directly -- since both operands are strings on a freshly
    // loaded draft (e.g. section80TTA: "157", section80TTB: "839"), `+` silently
    // performed JS string concatenation ("157" + "839" = "157839") instead of
    // arithmetic addition (157 + 839 = 996), corrupting the displayed total
    // into a plausible-looking but wrong number rather than an obvious error.
    const section80TTA = '157';
    const section80TTB = '839';
    expect(money(section80TTA) + money(section80TTB)).toBe(996);
    // Demonstrates what the pre-fix code actually computed, for contrast.
    expect(Number(section80TTA + section80TTB)).toBe(157839);
  });

  it('treats non-numeric or missing input as 0, matching prior behavior', () => {
    expect(money(undefined)).toBe(0);
    expect(money('')).toBe(0);
    expect(money('not-a-number')).toBe(0);
    expect(money(-50)).toBe(0);
  });
});

describe('Section 80C / 80D / 80G section-header and viaTotal sums', () => {
  // Section80CManager, Section80DManager, and DonationEntryManager each store their
  // entries in their own draft field (section80C / section80D / section80G), separate
  // from the chapterVIA.section80C / section80D / section80G scalars the section
  // headers previously read directly. Nothing ever synced those scalars from the real
  // entries (unlike 80CCC pension and the deduction-loans manager, which both do sync
  // their derived totals back into chapterVIA) -- so a real, backend-accepted 80C
  // investment, 80D policy, or 80G donation displayed as Rs 0 in its own section
  // header and in the "Chapter VI-A aggregate (user-entered)" total, confirmed live
  // against the real /v2/tax-summary/compute response which correctly included them.

  it('sums 80C investment amounts directly from the investments array', () => {
    const investments: Investment80C[] = [
      { id: '80c-1', investmentType: 'EPF', identificationNo: 'EPF12345', accountOrPolicyNo: 'PF/AC/998877', dateOfInvestment: '2025-11-15', institutionName: 'Employer', institutionPAN: 'AAACS8577K', amount: '120000' as unknown as number },
    ];
    const total = investments.reduce((sum, investment) => sum + money(investment.amount), 0);
    expect(total).toBe(120000);
  });

  it('category80DTotal sums a category\'s policies plus preventive checkup and medical expense', () => {
    const category: Category80D = {
      policies: [
        { id: 'p1', insurerName: 'LIC', policyNo: 'POL1', premiumAmount: '15000' as unknown as number, policyType: 'FAMILY_FLOATER', dateOfCommencement: '2020-01-01' },
        { id: 'p2', insurerName: 'HDFC Ergo', policyNo: 'POL2', premiumAmount: '5000' as unknown as number, policyType: 'INDIVIDUAL', dateOfCommencement: '2021-01-01' },
      ],
      preventiveCheckup: '2000' as unknown as number,
      medicalExpense: '0' as unknown as number,
    };
    expect(category80DTotal(category)).toBe(22000);
  });

  it('sums 80G donation cash and other-mode amounts directly from the donations array', () => {
    const donations: Donation80G[] = [
      { id: 'g1', category: '50_APPROVAL_REQD', doneeName: 'Trust', doneePAN: 'ABCDE1234F', arnNumber: '', addrDetail: '', city: '', stateCode: '', pinCode: '', donationAmtCash: '1000' as unknown as number, donationAmtOtherMode: '9000' as unknown as number, transactionRefNum: '', ifscCode: '', donationDate: '2025-06-01', receiptNumber: '', notes: '' },
    ];
    const total = donations.reduce((sum, donation) => sum + money(donation.donationAmtCash) + money(donation.donationAmtOtherMode), 0);
    expect(total).toBe(10000);
  });
});
