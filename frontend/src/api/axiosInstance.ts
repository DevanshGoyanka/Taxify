import axios from 'axios';

// Base URL from Vite env var; falls back to our FastAPI server on port 8000.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const axiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach stored JWT to every request automatically.
axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// On 401 → clear storage and redirect to login.
axiosInstance.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.clear();
      window.location.href = '/login';
    }
    // Keep blob responses intact so download APIs can parse structured JSON
    // error bodies instead of receiving only a generic normalized Error.
    if (error.config?.responseType === 'blob') {
      return Promise.reject(error);
    }
    // Expose backend's unified error message when available.
    const raw =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message;
    // If the message is a dict (e.g. {message, errors}), stringify it.
    let message: string;
    if (typeof raw === 'string') {
      message = raw;
    } else if (raw && typeof raw === 'object') {
      const parts: string[] = [];
      if (raw.message) parts.push(String(raw.message));
      if (Array.isArray(raw.errors)) {
        parts.push(...raw.errors.map((item: unknown) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object') {
            const errorItem = item as { field?: unknown; message?: unknown };
            const field = errorItem.field ? `${String(errorItem.field)}: ` : '';
            return `${field}${String(errorItem.message ?? JSON.stringify(item))}`;
          }
          return String(item);
        }));
      }
      if (parts.length === 0) parts.push(JSON.stringify(raw));
      message = parts.join(' ');
    } else {
      message = String(raw ?? 'Unknown error');
    }
    const normalizedError = new Error(message) as Error & {
      details?: unknown;
      status?: number;
    };
    normalizedError.details = raw;
    normalizedError.status = error.response?.status;
    return Promise.reject(normalizedError);
  }
);

export default axiosInstance;
