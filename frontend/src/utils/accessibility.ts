import type { UserSettings } from "../types/api";

const SETTINGS_CLASS_NAMES = [
  "sx-density-compact",
  "sx-font-large",
  "sx-reduce-motion",
  "sx-high-contrast",
  "sx-color-blind-mode",
];

export function applyAccessibilitySettings(settings?: UserSettings | null) {
  SETTINGS_CLASS_NAMES.forEach((className) => {
    document.documentElement.classList.remove(className);
  });

  if (!settings) {
    return;
  }

  if (settings.density === "compact") {
    document.documentElement.classList.add("sx-density-compact");
  }

  if (settings.font_size === "large") {
    document.documentElement.classList.add("sx-font-large");
  }

  if (settings.reduce_motion) {
    document.documentElement.classList.add("sx-reduce-motion");
  }

  if (settings.high_contrast) {
    document.documentElement.classList.add("sx-high-contrast");
  }

  if (settings.color_blind_mode) {
    document.documentElement.classList.add("sx-color-blind-mode");
  }
}