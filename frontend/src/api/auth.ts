import axiosInstance from './axiosInstance';

export interface AuthResponse {
  token: string;
  email: string;
}

export const authApi = {
  /**
   * Login with email + password.
   * Backend returns { access_token, token_type }.
   * We map access_token → token for frontend compatibility.
   */
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const { data } = await axiosInstance.post('/auth/login', { email, password });
    return { token: data.access_token, email };
  },

  /**
   * Register a new account.
   * Backend endpoint is /auth/signup (not /auth/register).
   */
  register: async (email: string, password: string): Promise<AuthResponse> => {
    const { data } = await axiosInstance.post('/auth/signup', { email, password });
    return { token: data.access_token, email };
  },

  /**
   * Verify the stored JWT is still valid and fetch current user info.
   * Called on app load by ProtectedRoute.
   */
  me: async (): Promise<{ id: number; email: string }> => {
    const { data } = await axiosInstance.get('/me');
    return data;
  },
};
