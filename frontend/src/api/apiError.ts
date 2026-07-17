import { AxiosError } from 'axios';

export class ApiError extends Error {
  status: number;
  body: any;
  
  constructor(status: number, body: any) {
    super(body?.message ?? body?.error ?? 'An unexpected error occurred');
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export async function handleApiCall<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof AxiosError && err.response) {
      throw new ApiError(err.response.status, err.response.data);
    }
    throw err;
  }
}
