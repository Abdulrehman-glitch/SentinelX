import { Text, TextProps } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { type } from "@/theme/tokens";

type Variant = keyof typeof type;
type Tone = "primary" | "secondary" | "tertiary" | "disabled" | "accent" | "inverse";

interface Props extends TextProps {
  variant?: Variant;
  tone?: Tone;
  color?: string;
}

export function SXText({ variant = "body", tone = "primary", color, style, ...rest }: Props) {
  const { colors } = useTheme();
  const toneColor =
    color ??
    {
      primary: colors.textPrimary,
      secondary: colors.textSecondary,
      tertiary: colors.textTertiary,
      disabled: colors.textDisabled,
      accent: colors.accent,
      inverse: "#FFFFFF",
    }[tone];

  return (
    <Text
      allowFontScaling
      maxFontSizeMultiplier={variant === "metric" || variant === "pageTitle" ? 1.6 : 2}
      {...rest}
      style={[type[variant], { color: toneColor }, style]}
    />
  );
}
