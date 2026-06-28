import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { sentinelxApi } from "../lib/api";
import { authStorage } from "../lib/authStorage";
import type { AuthUser, LoginPayload, SignupPayload, UserRole } from "../types/api";

type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  errorMessage: string | null;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  hasRole: (roles: UserRole[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function refreshUser() {
    const token = authStorage.getToken();

    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setErrorMessage(null);

      const currentUser = await sentinelxApi.getMe();
      setUser(currentUser);
    } catch (error) {
      authStorage.clearToken();
      setUser(null);

      const message =
        error instanceof Error ? error.message : "Unable to load current user.";

      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }

  async function login(payload: LoginPayload) {
    try {
      setIsLoading(true);
      setErrorMessage(null);

      const response = await sentinelxApi.login(payload);

      authStorage.setToken(response.access_token);
      setUser(response.user);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Login failed.";

      setErrorMessage(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function signup(payload: SignupPayload) {
    try {
      setIsLoading(true);
      setErrorMessage(null);

      const response = await sentinelxApi.signup(payload);

      authStorage.setToken(response.access_token);
      setUser(response.user);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Signup failed.";

      setErrorMessage(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function logout() {
    try {
      await sentinelxApi.logout();
    } catch {
      // Logout is best-effort because local token removal is the critical step.
    } finally {
      authStorage.clearToken();
      setUser(null);
    }
  }

  function hasRole(roles: UserRole[]) {
    if (!user) {
      return false;
    }

    return roles.includes(user.role);
  }

  useEffect(() => {
    refreshUser();
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      errorMessage,
      login,
      signup,
      logout,
      refreshUser,
      hasRole,
    }),
    [user, isLoading, errorMessage],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}