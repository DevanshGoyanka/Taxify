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

  // AY "2026-27" → reference date is 31 March of the END year (2027).
  // The end year is the last two digits of the AY suffix + 2000.
  const endYearSuffix = assessmentYear.split('-')[1] ?? '27';
  const endYear = parseInt(endYearSuffix, 10) + 2000;
  const refDate = new Date(endYear, 2, 31); // March = month index 2

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
 * @returns ISO date string like "2027-03-31".
 */
export function getReferenceDate(assessmentYear: string): string {
  const endYearSuffix = assessmentYear.split('-')[1] ?? '27';
  const endYear = parseInt(endYearSuffix, 10) + 2000;
  return `${endYear}-03-31`;
}
