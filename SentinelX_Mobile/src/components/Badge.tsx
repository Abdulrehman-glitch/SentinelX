import { StyleSheet, View } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing, StatusTone } from "@/theme/tokens";
import { SXText } from "./SXText";

interface Props {
  tone: StatusTone;
  label: string;
  dot?: boolean;
}

// §27 — severity is never colour-only: badges always carry a text label.
export function Badge({ tone, label, dot = true }: Props) {
  const { colors } = useTheme();
  return (
    <View style={[styles.badge, { backgroundColor: colors.statusSoft[tone] }]}>
      {dot && <View style={[styles.dot, { backgroundColor: colors.status[tone] }]} />}
      <SXText variant="meta" style={{ color: colors.status[tone], fontWeight: "600" }}>
        {label}
      </SXText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
    alignSelf: "flex-start",
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
});
