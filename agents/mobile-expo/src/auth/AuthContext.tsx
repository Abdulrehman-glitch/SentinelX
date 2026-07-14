import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AppState, AppStateStatus } from "react-native";

import { configureClient } from "@/api/client";
import { sentinelxApi } from "@/api/endpoints";
import type { UserPublic } from "@/api/types";
import { toAppError } from "@/lib/errors";
import { authenticate } from "./biometrics";
import {
  clearSession,
  getBiometricLockEnabled,
  getLockTimeoutMs,
  loadSession,
  saveSession,
  setBiometricLockEnabled as persistBiometricLock,
  setLockTimeoutMs as persistLockTimeout,
} from "./secureSession";

interface AuthValue {
  status: "loading" | "signedOut" | "signedIn";
  user: UserPublic | null;
  sessionExpired: boolean;
  locked: boolean;
  privacyShield: boolean;
  biometricLockEnabled: boolean;
  lockTimeoutMs: number;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  unlock: () => Promise<boolean>;
  setBiometricLock: (enabled: boolean) => Promise<void>;
  setLockTimeout: (ms: number) => Promise<void>;
  requireBiometric: (reason: string) => Promise<boolean>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthValue["status"]>("loading");
  const [user, setUser] = useState<UserPublic | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [locked, setLocked] = useState(false);
  const [privacyShield, setPrivacyShield] = useState(false);
  const [biometricLockEnabled, setBiometricLockEnabledState] = useState(false);
  const [lockTimeoutMs, setLockTimeoutMsState] = useState(60_000);

  const tokenRef = useRef<string | null>(null);
  const backgroundedAtRef = useRef<number | null>(null);
  const biometricEnabledRef = useRef(false);
  const lockTimeoutRef = useRef(60_000);

  useEffect(() => {
    configureClient({
      tokenProvider: () => tokenRef.current,
      sessionExpiredHandler: () => {
        tokenRef.current = null;
        setSessionExpired(true);
        setUser(null);
        setStatus("signedOut");
        clearSession().catch(() => {});
      },
    });

    (async () => {
      const [session, bioLock, timeout] = await Promise.all([
        loadSession(),
        getBiometricLockEnabled(),
        getLockTimeoutMs(),
      ]);
      biometricEnabledRef.current = bioLock;
      lockTimeoutRef.current = timeout;
      setBiometricLockEnabledState(bioLock);
      setLockTimeoutMsState(timeout);
      if (session) {
        tokenRef.current = session.token;
        setUser(session.user);
        setStatus("signedIn");
        if (bioLock) setLocked(true);
      } else {
        setStatus("signedOut");
      }
    })().catch(() => setStatus("signedOut"));
  }, []);

  // §4 — privacy shield in the app switcher + relock after background timeout.
  useEffect(() => {
    const sub = AppState.addEventListener("change", (next: AppStateStatus) => {
      if (next === "inactive" || next === "background") {
        setPrivacyShield(true);
        if (backgroundedAtRef.current == null) backgroundedAtRef.current = Date.now();
        return;
      }
      if (next === "active") {
        setPrivacyShield(false);
        const away = backgroundedAtRef.current ? Date.now() - backgroundedAtRef.current : 0;
        backgroundedAtRef.current = null;
        if (biometricEnabledRef.current && tokenRef.current && away >= lockTimeoutRef.current) {
          setLocked(true);
        }
      }
    });
    return () => sub.remove();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await sentinelxApi.login(email.trim().toLowerCase(), password);
    tokenRef.current = response.access_token;
    await saveSession(response.access_token, response.user);
    setUser(response.user);
    setSessionExpired(false);
    setLocked(false);
    setStatus("signedIn");
  }, []);

  const logout = useCallback(async () => {
    try {
      await sentinelxApi.logout();
    } catch (err) {
      // Logout is audit-log only server-side; local clearing must not fail.
      toAppError(err);
    }
    tokenRef.current = null;
    await clearSession();
    setUser(null);
    setLocked(false);
    setStatus("signedOut");
  }, []);

  const unlock = useCallback(async () => {
    const ok = await authenticate("Unlock SentinelX");
    if (ok) setLocked(false);
    return ok;
  }, []);

  const setBiometricLock = useCallback(async (enabled: boolean) => {
    if (enabled) {
      const ok = await authenticate("Confirm to enable the biometric lock");
      if (!ok) return;
    }
    biometricEnabledRef.current = enabled;
    setBiometricLockEnabledState(enabled);
    await persistBiometricLock(enabled);
  }, []);

  const setLockTimeout = useCallback(async (ms: number) => {
    lockTimeoutRef.current = ms;
    setLockTimeoutMsState(ms);
    await persistLockTimeout(ms);
  }, []);

  // §16 — biometric confirmation before sensitive actions (recovery, revoke).
  const requireBiometric = useCallback(async (reason: string) => {
    if (!biometricEnabledRef.current) return true;
    return authenticate(reason);
  }, []);

  const value = useMemo(
    () => ({
      status,
      user,
      sessionExpired,
      locked,
      privacyShield,
      biometricLockEnabled,
      lockTimeoutMs,
      login,
      logout,
      unlock,
      setBiometricLock,
      setLockTimeout,
      requireBiometric,
    }),
    [
      status,
      user,
      sessionExpired,
      locked,
      privacyShield,
      biometricLockEnabled,
      lockTimeoutMs,
      login,
      logout,
      unlock,
      setBiometricLock,
      setLockTimeout,
      requireBiometric,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
