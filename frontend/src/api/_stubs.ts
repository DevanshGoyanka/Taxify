export class NotImplementedError extends Error {
  constructor(endpoint: string) {
    super(`Backend endpoint not implemented: ${endpoint}`);
    this.name = 'NotImplementedError';
  }
}

export function stub<T>(endpoint: string, fallback: T): T {
  console.warn(`[STUB] ${endpoint} — returning mock data.`);
  return fallback;
}
