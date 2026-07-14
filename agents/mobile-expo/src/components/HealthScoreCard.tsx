import { useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";

import { classifyHealthScore, healthTone } from "@/lib/health";
import { useTheme } from "@/theme/ThemeContext";
import { spacing } from "@/theme/tokens";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { SXText } from "./SXText";

interface Props {
  score: number | null;
  explanation?: string[];
  subtitle?: string;
}

// §10/§26 — primary status card with a smooth health-score count-up that
// falls back to a static value under Reduce Motion.
export function HealthScoreCard({ score, explanation = [], subtitle }: Props) {
  const { colors, reduceMotion } = useTheme();
  const [displayed, setDisplayed] = useState(reduceMotion ? (score ?? 0) : 0);
  const animated = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (score == null) return;
    if (reduceMotion) {
      setDisplayed(score);
      return;
    }
    const listener = animated.addListener(({ value }) => setDisplayed(Math.round(value)));
    Animated.timing(animated, { toValue: score, duration: 700, useNativeDriver: false }).start();
    return () => animated.removeListener(listener);
  }, [score, animated, reduceMotion]);

  const status = classifyHealthScore(score);
  const tone = healthTone(status);
  const label = status === "unknown" ? "Unknown" : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <Card surface="lavender" style={styles.card} accessible accessibilityLabel={`Fleet health ${score ?? "unknown"} out of 100, ${label}`}>
      <View style={styles.row}>
        <View style={{ gap: 4 }}>
          <SXText variant="label" tone="secondary">
            Fleet health
          </SXText>
          <View style={styles.scoreRow}>
            <SXText variant="metric" style={{ fontSize: 44 }} color={colors.status[tone]}>
              {score == null ? "—" : displayed}
            </SXText>
            <SXText variant="label" tone="tertiary" style={{ marginBottom: 8 }}>
              / 100
            </SXText>
          </View>
        </View>
        <Badge tone={tone} label={label} />
      </View>
      {subtitle ? (
        <SXText variant="meta" tone="secondary">
          {subtitle}
        </SXText>
      ) : null}
      {explanation.slice(0, 3).map((reason) => (
        <SXText key={reason} variant="meta" tone="tertiary">
          · {reason}
        </SXText>
      ))}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: spacing.xs,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  scoreRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 6,
  },
});
