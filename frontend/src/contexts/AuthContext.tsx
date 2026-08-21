import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { refreshAccessToken, sentinelxApi, setSessionEndedHandler } from "../lib/api";
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
    try {
      setIsLoading(true);
      setErrorMessage(null);

      // On a cold load there is no access token in memory — that is by
      // design, since it is never persisted. The HttpOnly refresh cookie is
      // what survives the reload, so ask the server to trade it for a new
      // access token before deciding the user is signed out.
      if (!authStorage.getToken()) {
        const restored = await refreshAccessToken();
        if (!restored) {
          setUser(null);
          return;
        }
      }

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
      authStorage.setToken(response.access_token, response.expires_in);
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
      authStorage.setToken(response.access_token, response.expires_in);
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

  // The API layer calls this when a silent refresh has already been tried and
  // failed, i.e. the session is genuinely over (logged out elsewhere, revoked,
  // expired, or refresh-token replay detected). Without it the app would keep
  // rendering an authenticated shell full of failing queries.
  useEffect(() => {
    setSessionEndedHandler(() => {
      setUser(null);
      setShowLoadingScreen(false);
      setErrorMessage("Your session ended. Please sign in again.");
    });
    return () => setSessionEndedHandler(null);
  }, []);

  // Renew shortly before expiry rather than waiting for a 401. This keeps
  // long-lived dashboard views (which poll every 15-20s) from showing a burst
  // of failed requests each time the 15-minute access token turns over.
  useEffect(() => {
    if (!user) return;

    let timer: ReturnType<typeof setTimeout>;

    const scheduleNext = () => {
      const remaining = authStorage.msUntilExpiry();
      // Refresh at 75% of the remaining lifetime, with a 30s floor so a clock
      // skew or a very short token cannot produce a tight loop.
      const delay = remaining === null ? 10 * 60 * 1000 : Math.max(30_000, remaining * 0.75);

      timer = setTimeout(async () => {
        const ok = await refreshAccessToken();
        if (ok) scheduleNext();
      }, delay);
    };

    scheduleNext();
    return () => clearTimeout(timer);
  }, [user]);

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
