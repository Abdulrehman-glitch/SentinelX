import { StyleSheet, View } from "react-native";

import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { formatRelativeTime } from "@/lib/format";
import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing } from "@/theme/tokens";
import { SXText } from "./SXText";

// §19 — cached data is clearly labelled whenever the device is offline.
export function OfflineBanner({ lastUpdatedAt }: { lastUpdatedAt?: number | null }) {
  const { online } = useNetworkStatus();
  const { colors } = useTheme();

  if (online) return null;

  return (
    <View
      style={[styles.banner, { backgroundColor: colors.statusSoft.offline, borderColor: colors.border }]}
      accessibilityRole="alert"
      accessibilityLabel="Offline. Showing cached data."
    >
      <View style={[styles.dot, { backgroundColor: colors.status.offline }]} />
      <SXText variant="label" tone="secondary" style={{ flex: 1 }}>
        Offline — showing cached data
        {lastUpdatedAt ? ` from ${formatRelativeTime(new Date(lastUpdatedAt))}` : ""}
      </SXText>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderRadius: radius.chip,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
});
