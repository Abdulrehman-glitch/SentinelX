import { BlurView } from "expo-blur";
import { GlassView, isLiquidGlassAvailable } from "expo-glass-effect";
import { Platform, StyleSheet, View, ViewProps } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius } from "@/theme/tokens";

// §23 — glass reserved for important surfaces (tab bar, sheets, key controls).
// Falls back to blur, then to a solid tinted surface when Reduce Transparency
// is on or the platform lacks support.

interface Props extends ViewProps {
  cornerRadius?: number;
  intensity?: number;
}

export function GlassSurface({ cornerRadius = radius.card, intensity = 40, style, children, ...rest }: Props) {
  const { colors, dark, reduceTransparency } = useTheme();

  if (reduceTransparency) {
    return (
      <View
        {...rest}
        style={[styles.base, { borderRadius: cornerRadius, backgroundColor: colors.surface, borderColor: colors.border }, style]}
      >
        {children}
      </View>
    );
  }

  if (Platform.OS === "ios" && isLiquidGlassAvailable()) {
    return (
      <GlassView
        {...rest}
        style={[styles.base, { borderRadius: cornerRadius, borderColor: colors.glassBorder }, style]}
      >
        {children}
      </GlassView>
    );
  }

  return (
    <BlurView
      {...rest}
      intensity={intensity}
      tint={dark ? "dark" : "light"}
      style={[
        styles.base,
        styles.blurClip,
        { borderRadius: cornerRadius, backgroundColor: colors.glassTint, borderColor: colors.glassBorder },
        style,
      ]}
    >
      {children}
    </BlurView>
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: StyleSheet.hairlineWidth,
    shadowColor: "#1A1D2B",
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
  },
  blurClip: {
    overflow: "hidden",
  },
});
