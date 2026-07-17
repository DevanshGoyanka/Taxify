import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
dayjs.extend(relativeTime);

export const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-IN');
export const INR = (n: number) => `₹${fmt(n)}`;
export const INRLakh = (n: number) => {
  if (n >= 10000000) return `₹${(n/10000000).toFixed(2)}Cr`;
  if (n >= 100000) return `₹${(n/100000).toFixed(2)}L`;
  return INR(n);
};
export const relTime = (iso: string) => dayjs(iso).fromNow();
export const fmtDate = (iso: string) => dayjs(iso).format('DD MMM YYYY');
export const toAPIDate = (date: Date | string) => dayjs(date).format('YYYY-MM-DD');
export const panInitials = (name: string) =>
  name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
export const deriveEntityFromPAN = (pan: string) => {
  const map: Record<string, string> = {
    P: 'Individual', H: 'HUF', F: 'Firm', A: 'AOP', B: 'BOI',
    C: 'Company', G: 'Govt', J: 'AI', L: 'Local', T: 'Trust'
  };
  return map[pan?.[3]?.toUpperCase()] ?? 'Unknown';
};
