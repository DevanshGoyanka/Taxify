import { describe, expect, it } from 'vitest';
import { validationFor, type Row } from './ITR2SchedulesWorkspace';

describe('validationFor — Schedule 5A (Portuguese Civil Code)', () => {
  const baseRow: Row = { id: '5a-1', spouseName: 'Anjali Nair', spousePAN: 'XYZAB5678C', spouseAadhaar: '' };

  it('accepts a valid 12-digit Aadhaar', () => {
    const row = { ...baseRow, spouseAadhaar: '123456789012' };
    expect(validationFor('5A', row, '2026-27')).not.toContain('Spouse Aadhaar must contain 12 digits when supplied.');
  });

  it('rejects an Aadhaar that is not 12 digits', () => {
    const row = { ...baseRow, spouseAadhaar: '12345' };
    expect(validationFor('5A', row, '2026-27')).toContain('Spouse Aadhaar must contain 12 digits when supplied.');
  });

  it('allows an empty Aadhaar (optional field)', () => {
    expect(validationFor('5A', baseRow, '2026-27')).toEqual([]);
  });

  it('requires spouse name and PAN', () => {
    const row: Row = { id: '5a-2', spouseName: '', spousePAN: '' };
    const errors = validationFor('5A', row, '2026-27');
    expect(errors).toContain('Spouse name and PAN are required.');
  });

  it('rejects a malformed spouse PAN', () => {
    const row = { ...baseRow, spousePAN: 'not-a-pan' };
    expect(validationFor('5A', row, '2026-27')).toContain('Spouse PAN must be valid.');
  });
});

describe('validationFor — Schedule ESOP', () => {
  const baseRow: Row = {
    id: 'esop-1', employerPAN: 'ABCPN1234F', dpiitRegistrationNumber: 'DIPP12345', assessmentYear: '2026-27',
  };

  it('accepts a valid DIPP registration number', () => {
    expect(validationFor('ESOP', baseRow, '2026-27')).toEqual([]);
  });

  it('rejects a registration number that does not match DIPP + 3-5 digits', () => {
    const row = { ...baseRow, dpiitRegistrationNumber: 'DPIIT12345' };
    expect(validationFor('ESOP', row, '2026-27')).toContain(
      'DPIIT registration number must match DIPP followed by 3-5 digits (e.g. DIPP12345).',
    );
  });

  it('requires a valid employer PAN', () => {
    const row = { ...baseRow, employerPAN: '' };
    expect(validationFor('ESOP', row, '2026-27')).toContain('A valid employer PAN is required.');
  });
});

describe('validationFor — Schedule BFLA', () => {
  it('rejects brought-forward loss exceeding the original loss', () => {
    const row: Row = { id: 'bfla-1', assessmentYear: '2025-26', originalLoss: 100, broughtForward: 200 };
    expect(validationFor('BFLA', row, '2026-27')).toContain('Brought-forward loss cannot exceed original loss.');
  });

  it('rejects a malformed assessment year', () => {
    const row: Row = { id: 'bfla-2', assessmentYear: 'not-a-year' };
    expect(validationFor('BFLA', row, '2026-27')).toContain('Assessment year must use YYYY-YY format.');
  });
});

describe('validationFor — Schedule SI', () => {
  it('rejects deductions on a special-rate-only section', () => {
    const row: Row = { id: 'si-1', section: '115BB', deductions: 500 };
    expect(validationFor('SI', row, '2026-27')).toContain('Deductions are not permitted for this special-rate section.');
  });
});

describe('validationFor — Schedule TR relief limits', () => {
  it('rejects relief claimed above the foreign tax paid', () => {
    const row: Row = {
      id: 'tr-1', countryCode: 'US', taxIdentificationNo: 'T123',
      taxPaidOutsideIndia: 1000, indianTaxPayable: 5000, reliefClaimed: 2000,
    };
    expect(validationFor('TR', row, '2026-27')).toContain('Relief cannot exceed foreign tax paid or Indian tax payable.');
  });
});

describe('validationFor — negative amounts', () => {
  it('flags any negative money-shaped field regardless of section', () => {
    const row: Row = { id: 'al-1', immovableProperty: -100 };
    expect(validationFor('AL', row, '2026-27').some((message) => message.includes('cannot be negative'))).toBe(true);
  });
});
