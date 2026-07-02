import {
  createContext,
  useCallback,
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
  showLoadingScreen: boolean;
  errorMessage: string | null;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  dismissLoadingScreen: () => void;
  hasRole: (roles: UserRole[]) => boolean;
  hasMinRole: (minRole: UserRole) => boolean;
};

const ROLE_LEVEL: Record<UserRole, number> = {
  platform_admin: 100,
  owner: 80,
  admin: 60,
  engineer: 40,
  operator: 30,
  viewer: 10,
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showLoadingScreen, setShowLoadingScreen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
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
    } catch {
      authStorage.clearToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const response = await sentinelxApi.login(payload);
      authStorage.setToken(response.access_token);
      setUser(response.user);
      setShowLoadingScreen(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Login failed.";
      setErrorMessage(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signup = useCallback(async (payload: SignupPayload) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const response = await sentinelxApi.signup(payload);
      authStorage.setToken(response.access_token);
      setUser(response.user);
      setShowLoadingScreen(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Signup failed.";
      setErrorMessage(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await sentinelxApi.logout();
    } catch {
      // best-effort
    } finally {
      authStorage.clearToken();
      setUser(null);
      setShowLoadingScreen(false);
    }
  }, []);

  const dismissLoadingScreen = useCallback(() => {
    setShowLoadingScreen(false);
  }, []);

  const hasRole = useCallback((roles: UserRole[]) => {
    if (!user) return false;
    return roles.includes(user.role as UserRole);
  }, [user]);

  const hasMinRole = useCallback((minRole: UserRole) => {
    if (!user) return false;
    return (ROLE_LEVEL[user.role as UserRole] ?? 0) >= (ROLE_LEVEL[minRole] ?? 0);
  }, [user]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      showLoadingScreen,
      errorMessage,
      login,
      signup,
      logout,
      refreshUser,
      dismissLoadingScreen,
      hasRole,
      hasMinRole,
    }),
    [
      user,
      isLoading,
      showLoadingScreen,
      errorMessage,
      login,
      signup,
      logout,
      refreshUser,
      dismissLoadingScreen,
      hasRole,
      hasMinRole,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
