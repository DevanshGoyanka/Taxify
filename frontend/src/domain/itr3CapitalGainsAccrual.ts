/** Typed ScheduleCGFor23.AccruOrRecOfCG quarterly accrual model. */

export const CG_ACCRUAL_DATE_RANGES = [
  'Upto15Of6',
  'Upto15Of9',
  'Up16Of9To15Of12',
  'Up16Of12To15Of3',
  'Up16Of3To31Of3',
] as const;

export type CGAccrualDateRange = (typeof CG_ACCRUAL_DATE_RANGES)[number];
export type CGAccrualBucket =
  | 'ShortTermUnder20Per'
  | 'ShortTermUnder30Per'
  | 'ShortTermUnderAppRate'
  | 'ShortTermUnderDTAARate'
  | 'LongTermUnder12_5Per'
  | 'LongTermUnderDTAARate'
  | 'VDATrnsfGainsUnder30Per';

export type CGAccrualDateValues = Readonly<Record<CGAccrualDateRange, number>>;
export type ScheduleCGAccrual = Readonly<Record<CGAccrualBucket, CGAccrualDateValues>>;

export const CG_ACCRUAL_BUCKETS: readonly CGAccrualBucket[] = [
  'ShortTermUnder20Per', 'ShortTermUnder30Per', 'ShortTermUnderAppRate',
  'ShortTermUnderDTAARate', 'LongTermUnder12_5Per', 'LongTermUnderDTAARate',
  'VDATrnsfGainsUnder30Per',
] as const;

export const CG_ACCRUAL_BUCKET_LABELS: Readonly<Record<CGAccrualBucket, string>> = {
  ShortTermUnder20Per: 'STCG taxable at 20%',
  ShortTermUnder30Per: 'STCG taxable at 30%',
  ShortTermUnderAppRate: 'STCG at applicable rate',
  ShortTermUnderDTAARate: 'STCG under DTAA',
  LongTermUnder12_5Per: 'LTCG taxable at 12.5%',
  LongTermUnderDTAARate: 'LTCG under DTAA',
  VDATrnsfGainsUnder30Per: 'VDA gains taxable at 30%',
};

export const EMPTY_SCHEDULE_CG_ACCRUAL: ScheduleCGAccrual = Object.freeze(
  Object.fromEntries(CG_ACCRUAL_BUCKETS.map((bucket) => [
    bucket, Object.fromEntries(CG_ACCRUAL_DATE_RANGES.map((range) => [range, 0])),
  ])) as ScheduleCGAccrual,
);

/** Returns a complete official seven-bucket, five-period accrual object. */
export function normalizeScheduleCGAccrual(value: unknown): ScheduleCGAccrual {
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return Object.fromEntries(CG_ACCRUAL_BUCKETS.map((bucket) => {
    const input = source[bucket] && typeof source[bucket] === 'object' ? source[bucket] as Record<string, unknown> : {};
    return [bucket, Object.fromEntries(CG_ACCRUAL_DATE_RANGES.map((range) => {
      const n = Number(input[range] ?? 0);
      return [range, Number.isFinite(n) && n >= 0 ? Math.trunc(n) : 0];
    }))];
  })) as ScheduleCGAccrual;
}

/** Validates all user-editable accrual amounts against official non-negative integer limits. */
export function validateScheduleCGAccrual(value: unknown): string[] {
  const errors: string[] = [];
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  for (const bucket of CG_ACCRUAL_BUCKETS) {
    const row = source[bucket];
    if (!row || typeof row !== 'object') { errors.push(`${bucket} is required.`); continue; }
    for (const range of CG_ACCRUAL_DATE_RANGES) {
      const amount = (row as Record<string, unknown>)[range];
      if (typeof amount !== 'number' || !Number.isInteger(amount) || amount < 0 || amount > 99999999999999) {
        errors.push(`${bucket}.${range} must be a non-negative integer.`);
      }
    }
  }
  return errors;
}

/** Applies one editable official bucket value without accepting computed Schedule CG totals. */
export function updateScheduleCGAccrual(
  current: ScheduleCGAccrual,
  bucket: CGAccrualBucket,
  range: CGAccrualDateRange,
  amount: number,
): ScheduleCGAccrual {
  if (!Number.isInteger(amount) || amount < 0 || amount > 99999999999999) return current;
  return { ...current, [bucket]: { ...current[bucket], [range]: amount } };
}

/** Converts a typed accrual model to canonical CBDT leaf paths. */
export function scheduleCGAccrualPaths(): readonly string[] {
  return CG_ACCRUAL_BUCKETS.flatMap((bucket) => CG_ACCRUAL_DATE_RANGES.map((range) => `ScheduleCGFor23.AccruOrRecOfCG.${bucket}.DateRange.${range}`));
}
