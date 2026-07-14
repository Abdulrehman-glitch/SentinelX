// Design tokens — checklist §22 (palette), §24 (type), §25 (spacing/shape).
// Screens read colors through useTheme(), never these maps directly.

export type StatusTone = "healthy" | "warning" | "critical" | "info" | "offline";

export interface ThemeColors {
  background: string;
  surface: string;
  surfaceLavender: string;
  surfaceBlue: string;
  surfaceGrouped: string;
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textDisabled: string;
  accent: string;
  accentSoft: string;
  accentBlue: string;
  border: string;
  glassTint: string;
  glassBorder: string;
  status: Record<StatusTone, string>;
  statusSoft: Record<StatusTone, string>;
}

export const lightColors: ThemeColors = {
  background: "#F6F7FB",
  surface: "#FFFFFF",
  surfaceLavender: "#F3F0FF",
  surfaceBlue: "#EEF5FF",
  surfaceGrouped: "#ECEEF4",
  textPrimary: "#17181C",
  textSecondary: "#626773",
  textTertiary: "#8D93A1",
  textDisabled: "#B8BDC8",
  accent: "#6F5CE7",
  accentSoft: "#A99BFF",
  accentBlue: "#4F7DF3",
  border: "#E3E6EE",
  glassTint: "rgba(255,255,255,0.78)",
  glassBorder: "rgba(255,255,255,0.55)",
  status: {
    healthy: "#2CA66F",
    warning: "#D58A20",
    critical: "#D64B55",
    info: "#4E79D9",
    offline: "#8A8F9A",
  },
  statusSoft: {
    healthy: "#E2F4EB",
    warning: "#F9EEDC",
    critical: "#FAE4E6",
    info: "#E4ECFA",
    offline: "#ECEDF0",
  },
};

export const darkColors: ThemeColors = {
  background: "#101116",
  surface: "#1A1C23",
  surfaceLavender: "#211E33",
  surfaceBlue: "#182031",
  surfaceGrouped: "#15171E",
  textPrimary: "#F2F3F7",
  textSecondary: "#A6ABB8",
  textTertiary: "#767C8A",
  textDisabled: "#4A4F5C",
  accent: "#8F7DFF",
  accentSoft: "#6F5CE7",
  accentBlue: "#6E95F6",
  border: "#2A2D38",
  glassTint: "rgba(26,28,35,0.72)",
  glassBorder: "rgba(255,255,255,0.08)",
  status: {
    healthy: "#3FBF85",
    warning: "#E5A34A",
    critical: "#E4707A",
    info: "#6E95F6",
    offline: "#7B8089",
  },
  statusSoft: {
    healthy: "#12291F",
    warning: "#2E2414",
    critical: "#301A1D",
    info: "#16223A",
    offline: "#1F2126",
  },
};

// §25 — base unit 4.
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  screenX: 18,
  cardPad: 18,
} as const;

export const radius = {
  card: 20,
  button: 16,
  pill: 999,
  sheet: 24,
  chip: 12,
} as const;

// §24 — native system font, tabular numerals for telemetry.
export const type = {
  pageTitle: { fontSize: 32, fontWeight: "700" as const, letterSpacing: -0.5 },
  sectionTitle: { fontSize: 21, fontWeight: "600" as const, letterSpacing: -0.3 },
  cardTitle: { fontSize: 16, fontWeight: "600" as const },
  metric: { fontSize: 32, fontWeight: "700" as const, fontVariant: ["tabular-nums"] as const },
  body: { fontSize: 16, fontWeight: "400" as const },
  label: { fontSize: 13, fontWeight: "500" as const },
  meta: { fontSize: 12, fontWeight: "400" as const },
} as const;

export const touchTarget = 44;

// §26 — common transitions 180–300 ms.
export const motion = {
  fast: 180,
  base: 240,
  slow: 300,
} as const;
