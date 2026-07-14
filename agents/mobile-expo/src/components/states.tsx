import { useEffect, useRef } from "react";
import { ActivityIndicator, Animated, StyleSheet, View } from "react-native";

import { isAppError, toAppError } from "@/lib/errors";
import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing, touchTarget } from "@/theme/tokens";
import { Card } from "./Card";
import { PressableScale } from "./PressableScale";
import { SXText } from "./SXText";

// §11/§32 — loading skeletons, empty states, and error states with retry +
// diagnostic reference. Shared by every list and detail screen.

export function Skeleton({ height = 72, count = 3 }: { height?: number; count?: number }) {
  const { colors, reduceMotion } = useTheme();
  const opacity = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    if (reduceMotion) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity, reduceMotion]);

  return (
    <View style={{ gap: spacing.md }} accessibilityLabel="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <Animated.View
          key={i}
          style={{
            height,
            borderRadius: radius.card,
            backgroundColor: colors.surfaceGrouped,
            opacity,
          }}
        />
      ))}
    </View>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Card surface="grouped" style={styles.stateCard}>
      <SXText variant="cardTitle">{title}</SXText>
      <SXText variant="label" tone="secondary" style={styles.centerText}>
        {message}
      </SXText>
    </Card>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const appError = isAppError(error) ? error : toAppError(error);
  const { colors } = useTheme();
  return (
    <Card surface="grouped" style={styles.stateCard}>
      <SXText variant="cardTitle" accessibilityRole="alert">
        {appError.title}
      </SXText>
      <SXText variant="label" tone="secondary" style={styles.centerText}>
        {appError.message}
      </SXText>
      <SXText variant="meta" tone="tertiary">
        Ref {appError.reference}
      </SXText>
      {onRetry && appError.retryable && (
        <PressableScale
          haptic="selection"
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel="Retry"
          style={[styles.retryButton, { backgroundColor: colors.accent }]}
        >
          <SXText variant="label" tone="inverse" style={{ fontWeight: "600" }}>
            Retry
          </SXText>
        </PressableScale>
      )}
    </Card>
  );
}

export function LoadingInline({ label = "Loading…" }: { label?: string }) {
  const { colors } = useTheme();
  return (
    <View style={styles.inline}>
      <ActivityIndicator color={colors.accent} />
      <SXText variant="label" tone="secondary">
        {label}
      </SXText>
    </View>
  );
}

const styles = StyleSheet.create({
  stateCard: {
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xxxl,
  },
  centerText: {
    textAlign: "center",
  },
  retryButton: {
    marginTop: spacing.sm,
    minHeight: touchTarget,
    minWidth: 120,
    borderRadius: radius.button,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  inline: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.lg,
  },
});
