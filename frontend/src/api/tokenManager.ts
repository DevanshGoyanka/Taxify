/**
 * Token manager — persists the JWT in localStorage.
 *
 * Our backend issues JWTs with a 24-hour expiry baked into the token itself.
 * We track expiry locally as now + 24h so ProtectedRoute can do a fast
 * client-side check without an extra network call.
 */

const TOKEN_KEY = 'auth_token';
const EMAIL_KEY = 'auth_email';
const EXPIRY_KEY = 'auth_expiry';
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

export const tokenManager = {
  /** Persist token and email. Expiry is fixed at 24 h (matches backend JWT). */
  save(token: string, email: string) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EMAIL_KEY, email);
    localStorage.setItem(EXPIRY_KEY, String(Date.now() + TWENTY_FOUR_HOURS_MS));
  },

  getToken: () => localStorage.getItem(TOKEN_KEY),
  getEmail: () => localStorage.getItem(EMAIL_KEY),

  isExpired() {
    const e = localStorage.getItem(EXPIRY_KEY);
    return !e || Date.now() > parseInt(e);
  },

  isAuthenticated() {
    return !!this.getToken() && !this.isExpired();
  },

  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(EXPIRY_KEY);
  },
};
