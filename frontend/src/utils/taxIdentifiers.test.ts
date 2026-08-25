import { describe, expect, it } from 'vitest';
import { isValidTan, normalizeTan } from './taxIdentifiers';

describe('TAN validation', () => {
  it('accepts official jurisdiction-prefixed TANs', () => {
    expect(isValidTan('DELA12345B')).toBe(true);
    expect(isValidTan('muma54321z')).toBe(true);
  });

  it('rejects generic PAN-shaped and unknown-prefix values', () => {
    expect(isValidTan('ABCD12345E')).toBe(false);
    expect(isValidTan('XYZA12345B')).toBe(false);
  });

  it('normalizes input before validation', () => {
    expect(normalizeTan(' del-a 12345b ')).toBe('DELA12345B');
  });
});
