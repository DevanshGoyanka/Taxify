import { describe, expect, it } from 'vitest';
import { normalizeNatureOfEmployment } from './normalizeNatureOfEmployment';

describe('normalizeNatureOfEmployment', () => {
  it('preserves official CBDT codes', () => {
    expect(normalizeNatureOfEmployment('PESG')).toBe('PESG');
  });

  it('maps pensioner descriptions to pensioner codes', () => {
    expect(normalizeNatureOfEmployment('Central Government pensioner')).toBe('PE');
    expect(normalizeNatureOfEmployment('State Government Pension')).toBe('PESG');
    expect(normalizeNatureOfEmployment('PSU pensioner')).toBe('PEPS');
    expect(normalizeNatureOfEmployment('Other pensioner')).toBe('PEO');
  });

  it('does not misuse pensioner code PE for private employment', () => {
    expect(normalizeNatureOfEmployment('Private sector employee')).toBe('OTH');
  });
});
