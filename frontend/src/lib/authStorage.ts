const AUTH_TOKEN_KEY = "sx_auth_token";

export const authStorage = {
  getToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  },

  setToken(token: string) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  },

  clearToken() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  },
};