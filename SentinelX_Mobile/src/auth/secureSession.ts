import * as SecureStore from "expo-secure-store";

import type { UserPublic } from "@/api/types";

// All session material lives in the iOS Keychain via SecureStore (§4, §29).
// Nothing auth-related is ever written to AsyncStorage.
const KEYS = {
  accessToken: "sx.session.accessToken",
  user: "sx.session.user",
  biometricLock: "sx.pref.biometricLock",
  lockTimeoutMs: "sx.pref.lockTimeoutMs",
} as const;

export async function saveSession(token: string, user: UserPublic): Promise<void> {
  await SecureStore.setItemAsync(KEYS.accessToken, token);
  await SecureStore.setItemAsync(KEYS.user, JSON.stringify(user));
}

export async function loadSession(): Promise<{ token: string; user: UserPublic } | null> {
  const token = await SecureStore.getItemAsync(KEYS.accessToken);
  const rawUser = await SecureStore.getItemAsync(KEYS.user);
  if (!token || !rawUser) return null;
  try {
    return { token, user: JSON.parse(rawUser) as UserPublic };
  } catch {
    await clearSession();
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(KEYS.accessToken);
  await SecureStore.deleteItemAsync(KEYS.user);
}

export async function getBiometricLockEnabled(): Promise<boolean> {
  return (await SecureStore.getItemAsync(KEYS.biometricLock)) === "true";
}

export async function setBiometricLockEnabled(enabled: boolean): Promise<void> {
  await SecureStore.setItemAsync(KEYS.biometricLock, String(enabled));
}

export async function getLockTimeoutMs(): Promise<number> {
  const raw = await SecureStore.getItemAsync(KEYS.lockTimeoutMs);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : 60_000;
}

export async function setLockTimeoutMs(ms: number): Promise<void> {
  await SecureStore.setItemAsync(KEYS.lockTimeoutMs, String(ms));
}
