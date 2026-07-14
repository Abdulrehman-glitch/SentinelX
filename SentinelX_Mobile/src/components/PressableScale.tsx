import * as Haptics from "expo-haptics";
import { useRef } from "react";
import { Animated, Pressable, PressableProps } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { motion } from "@/theme/tokens";

interface Props extends PressableProps {
  haptic?: "selection" | "warning" | "critical" | "none";
  children: React.ReactNode;
}

// §26 — spring response on press; respects Reduce Motion.
export function PressableScale({ haptic = "none", onPress, children, style, ...rest }: Props) {
  const scale = useRef(new Animated.Value(1)).current;
  const { reduceMotion } = useTheme();

  const animate = (to: number) => {
    if (reduceMotion) return;
    Animated.spring(scale, { toValue: to, useNativeDriver: true, speed: 40, bounciness: 6 }).start();
  };

  return (
    <Pressable
      {...rest}
      onPressIn={() => animate(0.97)}
      onPressOut={() => animate(1)}
      onPress={(e) => {
        if (haptic === "selection") Haptics.selectionAsync().catch(() => {});
        if (haptic === "warning") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
        if (haptic === "critical") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
        onPress?.(e);
      }}
      style={typeof style === "function" ? style : undefined}
    >
      <Animated.View style={[typeof style !== "function" ? style : undefined, { transform: [{ scale }] }]}>
        {children}
      </Animated.View>
    </Pressable>
  );
}

export const pressDuration = motion.fast;
