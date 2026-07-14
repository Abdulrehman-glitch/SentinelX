import { ActivityIndicator, StyleSheet, ViewStyle } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing, touchTarget } from "@/theme/tokens";
import { PressableScale } from "./PressableScale";
import { SXText } from "./SXText";

interface Props {
  label: string;
  onPress: () => void;
  kind?: "primary" | "secondary" | "destructive";
  loading?: boolean;
  disabled?: boolean;
  haptic?: "selection" | "warning" | "critical" | "none";
  style?: ViewStyle;
}

export function Button({ label, onPress, kind = "primary", loading, disabled, haptic = "selection", style }: Props) {
  const { colors } = useTheme();
  const isDisabled = disabled || loading;

  const background =
    kind === "primary" ? colors.accent : kind === "destructive" ? colors.status.critical : colors.surfaceGrouped;
  const textColor = kind === "secondary" ? colors.textPrimary : "#FFFFFF";

  return (
    <PressableScale
      haptic={haptic}
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!isDisabled, busy: !!loading }}
      style={[styles.button, { backgroundColor: background, opacity: isDisabled ? 0.55 : 1 }, style]}
    >
      {loading ? (
        <ActivityIndicator color={textColor} />
      ) : (
        <SXText variant="label" color={textColor} style={{ fontWeight: "600", fontSize: 15 }}>
          {label}
        </SXText>
      )}
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: touchTarget + 4,
    borderRadius: radius.button,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    flexDirection: "row",
    gap: spacing.sm,
  },
});
