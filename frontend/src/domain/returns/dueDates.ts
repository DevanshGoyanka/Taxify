import type { ReturnDraft } from './types';

type FilingSection = ReturnDraft['filing']['filingSection'];

export const ON_TIME_SECTION: FilingSection = '139(1)';
export const BELATED_SECTION: FilingSection = '139(4)';
export const REVISED_SECTION: FilingSection = '139(5)';

/**
 * Mirrors app/engine/common/due_dates.py. The due dates under section 139(1)
 * for non-audit cases: ITR-1/ITR-2 on 31 July, ITR-3/ITR-4 on 31 August.
 */
export function getDueDate(form: ReturnDraft['form'], assessmentYear = '2026-27'): string {
  const parsed = Number.parseInt((assessmentYear || '').split('-')[0] ?? '', 10);
  const year = Number.isFinite(parsed) ? parsed : 2026;
  return form === 'ITR-1' || form === 'ITR-2' ? `${year}-07-31` : `${year}-08-31`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function isDueDatePassed(
  form: ReturnDraft['form'],
  assessmentYear = '2026-27',
  onDate: string = todayIso(),
): boolean {
  return onDate > getDueDate(form, assessmentYear);
}

/**
 * The section that applies to a return filed today: on-time before the due
 * date, belated after it, revised once an original return has been filed.
 */
export function applicableFilingSection(
  form: ReturnDraft['form'],
  assessmentYear = '2026-27',
  options: { originalReturnFiled?: boolean; onDate?: string } = {},
): FilingSection {
  if (options.originalReturnFiled) return REVISED_SECTION;
  return isDueDatePassed(form, assessmentYear, options.onDate ?? todayIso())
    ? BELATED_SECTION
    : ON_TIME_SECTION;
}

/**
 * Returns an actionable message when the chosen section contradicts the due
 * date, or null when it does not. Only 139(1) can contradict it — it means
 * "on or before the due date", so once that date has gone the return is
 * either belated or revised. The notice-driven sections and 119(2)(b) are
 * triggered by a departmental action, not by the calendar.
 *
 * The ITD portal enforces the same rule by quietly dropping the form from its
 * ITR list rather than reporting an error, so catching it here is what turns
 * an unexplained stall into something the operator can act on.
 */
export function filingSectionDueDateError(
  filingSection: FilingSection,
  form: ReturnDraft['form'],
  assessmentYear = '2026-27',
  onDate: string = todayIso(),
): string | null {
  if (filingSection !== ON_TIME_SECTION) return null;
  if (!isDueDatePassed(form, assessmentYear, onDate)) return null;
  return `Filing: section 139(1) means the return is filed on or before the due date, but the ${form} due date for AY ${assessmentYear} was ${getDueDate(form, assessmentYear)} and it has passed. Use 139(4) (belated) if this return has not been filed yet, or 139(5) (revised) with the original acknowledgement number and filing date if it has.`;
}
