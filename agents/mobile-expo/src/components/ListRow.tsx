import { StyleSheet, View } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { spacing, touchTarget } from "@/theme/tokens";
import { Card } from "./Card";
import { PressableScale } from "./PressableScale";
import { SXText } from "./SXText";

interface Props {
  title: string;
  subtitle?: string;
  meta?: string;
  left?: React.ReactNode;
  right?: React.ReactNode;
  onPress?: () => void;
  accessibilityLabel?: string;
}

export function ListRow({ title, subtitle, meta, left, right, onPress, accessibilityLabel }: Props) {
  const { colors } = useTheme();
  const body = (
    <Card style={styles.row}>
      {left}
      <View style={styles.content}>
        <SXText variant="cardTitle" numberOfLines={1}>
          {title}
        </SXText>
        {subtitle ? (
          <SXText variant="label" tone="secondary" numberOfLines={2}>
            {subtitle}
          </SXText>
        ) : null}
        {meta ? (
          <SXText variant="meta" tone="tertiary" numberOfLines={1}>
            {meta}
          </SXText>
        ) : null}
      </View>
      <View style={styles.right}>
        {right}
        {onPress && (
          <SXText variant="cardTitle" color={colors.textTertiary}>
            ›
          </SXText>
        )}
      </View>
    </Card>
  );

  if (!onPress) return body;
  return (
    <PressableScale
      haptic="selection"
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityHint={subtitle}
    >
      {body}
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    minHeight: touchTarget + 20,
  },
  content: {
    flex: 1,
    gap: 3,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
});
