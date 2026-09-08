/** Official AY 2026-27 TAN jurisdiction prefixes from the CBDT schemas. */
export const CBDT_TAN_PATTERN =
  /^(HYD|VPN|BBN|BPL|JBP|CHE|CMB|MRI|DEL|CAL|MRT|AHM|BRD|RKT|SRT|BLR|AGR|KNP|CHN|TVD|ALD|LKN|MUM|NGP|AMR|JLD|PTL|RTK|KLP|NSK|PNE|PTN|RCH|JDH|JPR|SHL)[A-Z][0-9]{5}[A-Z]$/;

export function normalizeTan(value: unknown): string {
  return String(value ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10);
}

export function isValidTan(value: unknown): boolean {
  return CBDT_TAN_PATTERN.test(normalizeTan(value));
}
