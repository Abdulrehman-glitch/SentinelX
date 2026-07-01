import type { UserSettings } from "../types/api";

const SETTINGS_CLASS_NAMES = [
  "sx-density-compact",
  "sx-font-large",
  "sx-reduce-motion",
  "sx-high-contrast",
  "sx-color-blind-mode",
];

const THEME_CLASS_NAMES = ["light-mode", "dark-mode", "system-mode"];
const LOCAL_SETTINGS_KEY = "sentinelx_ui_settings";

type StoredUiSettings = Partial<UserSettings> & { saved_at?: string };

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined" || !window.matchMedia) {
    return "dark";
  }

  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function persistUiSettings(settings: UserSettings) {
  try {
    const stored: StoredUiSettings = {
      ...settings,
      saved_at: new Date().toISOString(),
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(stored));
  } catch {
    // Local storage is best-effort only. Backend settings remain source of truth.
  }
}

export function loadStoredUiSettings(): StoredUiSettings | null {
  try {
    const raw = localStorage.getItem(LOCAL_SETTINGS_KEY);
    return raw ? (JSON.parse(raw) as StoredUiSettings) : null;
  } catch {
    return null;
  }
}

function applyTheme(theme: UserSettings["theme"] | undefined) {
  const root = document.documentElement;
  THEME_CLASS_NAMES.forEach((className) => root.classList.remove(className));
  root.removeAttribute("data-theme");

  const selectedTheme = theme ?? loadStoredUiSettings()?.theme ?? "system";

  if (selectedTheme === "light") {
    root.dataset.theme = "light";
    root.classList.add("light-mode");
    root.style.colorScheme = "light";
    return;
  }

  if (selectedTheme === "dark") {
    root.dataset.theme = "dark";
    root.classList.add("dark-mode");
    root.style.colorScheme = "dark";
    return;
  }

  const resolvedTheme = getSystemTheme();
  root.dataset.theme = resolvedTheme;
  root.classList.add("system-mode", `${resolvedTheme}-mode`);
  root.style.colorScheme = resolvedTheme;
}

export function applyAccessibilitySettings(settings?: UserSettings | null) {
  const root = document.documentElement;

  SETTINGS_CLASS_NAMES.forEach((className) => {
    root.classList.remove(className);
  });

  const storedSettings = loadStoredUiSettings();
  const activeSettings = settings ?? storedSettings ?? null;

  applyTheme(activeSettings?.theme);

  if (!activeSettings) {
    return;
  }

  if (activeSettings.density === "compact") {
    root.classList.add("sx-density-compact");
  }

  if (activeSettings.font_size === "large") {
    root.classList.add("sx-font-large");
  }

  if (activeSettings.reduce_motion) {
    root.classList.add("sx-reduce-motion");
  }

  if (activeSettings.high_contrast) {
    root.classList.add("sx-high-contrast");
  }

  if (activeSettings.color_blind_mode) {
    root.classList.add("sx-color-blind-mode");
  }
}

export function subscribeToSystemThemeChanges() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return () => undefined;
  }

  const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
  const handler = () => {
    const storedSettings = loadStoredUiSettings();
    if (!storedSettings?.theme || storedSettings.theme === "system") {
      applyAccessibilitySettings(storedSettings as UserSettings | null);
    }
  };

  mediaQuery.addEventListener("change", handler);
  return () => mediaQuery.removeEventListener("change", handler);
}
