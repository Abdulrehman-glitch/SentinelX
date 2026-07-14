import AsyncStorage from "@react-native-async-storage/async-storage";

// Base URL is user-editable (Settings → Connection) because local testing
// points at the laptop's LAN IP, e.g. http://192.168.1.20:8000/api/v1.
const DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1";
const STORAGE_KEY = "sx.api.baseUrl";

let cachedBaseUrl: string | null = null;
const listeners = new Set<(url: string) => void>();

export async function loadBaseUrl(): Promise<string> {
  if (cachedBaseUrl) return cachedBaseUrl;
  const stored = await AsyncStorage.getItem(STORAGE_KEY);
  cachedBaseUrl = stored?.trim() || DEFAULT_BASE_URL;
  return cachedBaseUrl;
}

export function getBaseUrlSync(): string {
  return cachedBaseUrl ?? DEFAULT_BASE_URL;
}

export async function setBaseUrl(url: string): Promise<void> {
  const normalized = url.trim().replace(/\/+$/, "");
  cachedBaseUrl = normalized || DEFAULT_BASE_URL;
  await AsyncStorage.setItem(STORAGE_KEY, cachedBaseUrl);
  listeners.forEach((fn) => fn(cachedBaseUrl!));
}

export function onBaseUrlChange(fn: (url: string) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function isSecureUrl(url: string): boolean {
  return url.startsWith("https://");
}

export const APP_NAME = "SentinelX Mobile";
export const AGENT_TYPE = "ios_mobile_agent";
export const AGENT_VERSION = "1.0.0";
