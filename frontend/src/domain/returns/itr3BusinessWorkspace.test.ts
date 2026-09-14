import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import { normalizeLoadedDraft, stripCompatibility } from './canonicalRepository';

describe('ITR-3 canonical business workspace', () => {
  it('round-trips core, auxiliary, and selected schedules through normalization', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    draft.itr3BusinessWorkspace = {
      core: { PARTA_BS: { FundSrc: { PropFund: { PropCap: 125000 } } } },
      auxiliary: { ScheduleGST: { TurnoverGrsRcptForGSTIN: [{ GSTIN: '07ABCDE1234F1Z5', Turnover: 900000 }] } },
      selectedSchedules: ['ScheduleGST', 'PARTA_QD'],
    };

    const restored = normalizeLoadedDraft(JSON.parse(JSON.stringify(draft)));
    expect(restored.itr3BusinessWorkspace).toEqual(draft.itr3BusinessWorkspace);
  });

  it('does not remove canonical business workspace data when stripping compatibility keys', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    draft.itr3BusinessWorkspace.core = { PARTA_PL: { CreditsToPL: { compatibility: 'internal', Total: 500 } } };
    const stripped = stripCompatibility(draft);
    expect(stripped.itr3BusinessWorkspace.core).toEqual({ PARTA_PL: { CreditsToPL: { Total: 500 } } });
  });

  it('keeps other-form drafts on the same safe empty workspace default', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    expect(draft.itr3BusinessWorkspace).toEqual({ core: {}, auxiliary: {}, selectedSchedules: [] });
  });
});
