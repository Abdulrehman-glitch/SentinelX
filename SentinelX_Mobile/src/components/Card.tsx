import { StyleSheet, View, ViewProps } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing } from "@/theme/tokens";

type Surface = "default" | "lavender" | "blue" | "grouped";

interface Props extends ViewProps {
  surface?: Surface;
  padded?: boolean;
}

export function Card({ surface = "default", padded = true, style, ...rest }: Props) {
  const { colors } = useTheme();
  const backgroundColor = {
    default: colors.surface,
    lavender: colors.surfaceLavender,
    blue: colors.surfaceBlue,
    grouped: colors.surfaceGrouped,
  }[surface];

  return (
    <View
      {...rest}
      style={[
        styles.card,
        { backgroundColor, borderColor: colors.border },
        padded && { padding: spacing.cardPad },
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.card,
    borderWidth: StyleSheet.hairlineWidth,
    shadowColor: "#1A1D2B",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
});
