import { describe, expect, it } from 'vitest';
import { calculateAgeFromDob, getReferenceDate } from './age';

describe('calculateAgeFromDob', () => {
  // AY "2026-27" assesses the previous year 2025-26, which ends 31 March
  // 2026 -- the correct statutory reference date. The prior implementation
  // parsed the AY's suffix ("27") as a calendar year and added 2000,
  // landing on 31 March 2027 -- a full year past the real reference date,
  // confirmed against the backend's own hardcoded reference date
  // (app/engine/draft_to_itr1_input.py's _age_bracket_from_dob uses
  // datetime.date(2026, 3, 31) for the same AY).

  it('computes age as on 31 March of the AY start year, not the suffix year', () => {
    // Born 1 June 2006: has not yet had a 2026 birthday as of 31 March
    // 2026, so is 19, not 20.
    expect(calculateAgeFromDob('2006-06-01', '2026-27')).toBe(19);
  });

  it('counts a birthday that falls exactly on the reference date', () => {
    expect(calculateAgeFromDob('2006-03-31', '2026-27')).toBe(20);
  });

  it('does not count a birthday the day after the reference date', () => {
    expect(calculateAgeFromDob('2006-04-01', '2026-27')).toBe(19);
  });

  it('returns 0 for a missing or invalid DOB', () => {
    expect(calculateAgeFromDob(null, '2026-27')).toBe(0);
    expect(calculateAgeFromDob(undefined, '2026-27')).toBe(0);
    expect(calculateAgeFromDob('not-a-date', '2026-27')).toBe(0);
  });

  it('respects a different assessment year', () => {
    // AY 2025-26 references 31 March 2025.
    expect(calculateAgeFromDob('2006-06-01', '2025-26')).toBe(18);
  });
});

describe('getReferenceDate', () => {
  it('returns 31 March of the AY start year, not the suffix year', () => {
    expect(getReferenceDate('2026-27')).toBe('2026-03-31');
  });

  it('respects a different assessment year', () => {
    expect(getReferenceDate('2025-26')).toBe('2025-03-31');
  });
});
