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
    // Expose backend's unified error message when available.
    const message =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message;
    return Promise.reject(new Error(message));
  }
);

export default axiosInstance;
