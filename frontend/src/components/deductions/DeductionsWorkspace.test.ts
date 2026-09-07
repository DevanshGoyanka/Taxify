import { describe, expect, it } from 'vitest';
import { money } from './DeductionsWorkspace';

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
