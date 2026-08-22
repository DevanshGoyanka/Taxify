import { normalizeEmploymentNature, type NatureOfEmployment } from '../domain/returns/cbdtEnums';

/**
 * Normalizes portal employment descriptions to CBDT employment codes.
 *
 * @param raw Portal-provided code or description.
 * @returns A valid CBDT nature-of-employment code.
 */
export function normalizeNatureOfEmployment(raw: unknown): NatureOfEmployment {
  const code = normalizeEmploymentNature(raw);
  if (code) return code;

  const text = String(raw ?? '').trim().toLowerCase();
  if (text.includes('pension')) {
    if (text.includes('central') && text.includes('gov')) return 'PE';
    if (text.includes('state') && text.includes('gov')) return 'PESG';
    if (text.includes('public sector') || text.includes('psu')) return 'PEPS';
    return 'PEO';
  }
  if (text.includes('central') && text.includes('gov')) return 'CGOV';
  if (text.includes('state') && text.includes('gov')) return 'SGOV';
  if (text.includes('public sector') || text.includes('psu')) return 'PSU';
  return 'OTH';
}
