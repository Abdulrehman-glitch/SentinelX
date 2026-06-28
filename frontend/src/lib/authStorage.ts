const AUTH_TOKEN_KEY = "NTe3j5pQWwoHANzo9lvuHEmQtTTGOawi2MKD9kknAx9DKeV244VTLw8iqOayvzPWTcR0yZQxKBptu9pc0C-hbg";

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