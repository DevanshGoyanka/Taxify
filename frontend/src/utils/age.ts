/**
 * Age derivation utility — single source of truth for all components.
 *
 * Derives age as on 31st March of the given assessment year from a date
 * of birth string. This is the statutory reference date for age-bracket
 * determination (senior citizen 60–80, super senior 80+).
 */

/**
 * Derive age as on 31st March of the assessment year from DOB.
 *
 * @param dob ISO date string (YYYY-MM-DD), or null/undefined.
 * @param assessmentYear Assessment year string like "2026-27".
 * @returns Age in whole years (0 if DOB is missing/invalid).
 */
export function calculateAgeFromDob(
  dob: string | undefined | null,
  assessmentYear: string,
): number {
  if (!dob) return 0;
  const birthDate = new Date(dob);
  if (Number.isNaN(birthDate.getTime())) return 0;

  // AY "2026-27" assesses income for the previous year 2025-26, which ends
  // 31 March 2026 -- the reference date's year is the AY string's OWN first
  // (start) component, not the suffix. The previous version parsed the
  // suffix ("27") as if it were itself a calendar year and added 2000,
  // landing on 31 March 2027 -- one full year past the correct statutory
  // reference date. Confirmed against the backend's own hardcoded
  // datetime.date(2026, 3, 31) in draft_to_itr1_input.py's
  // _age_bracket_from_dob(), which is unaffected by this bug since it is
  // computed independently server-side -- this was a display-only defect.
  const startYear = parseInt(assessmentYear.split('-')[0] ?? '2026', 10);
  const refDate = new Date(startYear, 2, 31); // March = month index 2

  let age = refDate.getFullYear() - birthDate.getFullYear();
  const monthDiff = refDate.getMonth() - birthDate.getMonth();
  if (
    monthDiff < 0 ||
    (monthDiff === 0 && refDate.getDate() < birthDate.getDate())
  ) {
    age -= 1;
  }
  return age >= 0 ? age : 0;
}

/**
 * Derive the statutory reference date (31 March) for an assessment year.
 *
 * @param assessmentYear Assessment year string like "2026-27".
 * @returns ISO date string like "2026-03-31".
 */
export function getReferenceDate(assessmentYear: string): string {
  const startYear = parseInt(assessmentYear.split('-')[0] ?? '2026', 10);
  return `${startYear}-03-31`;
}
