import { StyleSheet, View } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { spacing, StatusTone } from "@/theme/tokens";
import { Card } from "./Card";
import { SXText } from "./SXText";

interface Props {
  label: string;
  value: number | string;
  tone?: StatusTone;
}

export function KpiCard({ label, value, tone }: Props) {
  const { colors } = useTheme();
  return (
    <Card style={styles.card} accessible accessibilityLabel={`${label}: ${value}`}>
      <SXText variant="metric" style={{ fontSize: 28 }} color={tone ? colors.status[tone] : colors.textPrimary}>
        {String(value)}
      </SXText>
      <SXText variant="meta" tone="secondary">
        {label}
      </SXText>
    </Card>
  );
}

export function KpiGrid({ children }: { children: React.ReactNode }) {
  return <View style={styles.grid}>{children}</View>;
}

const styles = StyleSheet.create({
  card: {
    flexGrow: 1,
    flexBasis: "30%",
    gap: 2,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
});
