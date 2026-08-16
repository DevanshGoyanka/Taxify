/** Valid CBDT nature-of-employment codes accepted by the canonical draft. */
const VALID_NATURE_OF_EMPLOYMENT = new Set([
  'CGOV', 'SGOV', 'PSU', 'PE', 'PESG', 'PEPS', 'PEO', 'OTH',
]);

/**
 * Normalizes portal employment descriptions to CBDT employment codes.
 *
 * @param raw Portal-provided code or description.
 * @returns A valid CBDT nature-of-employment code.
 */
export function normalizeNatureOfEmployment(raw: unknown): string {
  const code = String(raw ?? '').trim().toUpperCase();
  if (VALID_NATURE_OF_EMPLOYMENT.has(code)) return code;

  const text = String(raw ?? '').trim().toLowerCase();
  if (text.includes('central') && text.includes('gov')) return 'CGOV';
  if (text.includes('state') && text.includes('gov')) return 'SGOV';
  if (text.includes('private') && text.includes('public sector')) return 'PESG';
  if (text.includes('private') && text.includes('private sector')) return 'PEPS';
  if (text.includes('public sector') || text.includes('psu')) return 'PSU';
  if (text.includes('private')) return 'PE';
  return 'OTH';
}
