import { ScrollView, StyleSheet } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing, touchTarget } from "@/theme/tokens";
import { PressableScale } from "./PressableScale";
import { SXText } from "./SXText";

export interface ChipOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  options: ChipOption<T>[];
  selected: T;
  onSelect: (value: T) => void;
}

// §11 — horizontal filter chips with selection haptics.
export function Chips<T extends string>({ options, selected, onSelect }: Props<T>) {
  const { colors } = useTheme();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {options.map((opt) => {
        const active = opt.value === selected;
        return (
          <PressableScale
            key={opt.value}
            haptic="selection"
            onPress={() => onSelect(opt.value)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            accessibilityLabel={`Filter: ${opt.label}`}
            style={[
              styles.chip,
              {
                backgroundColor: active ? colors.accent : colors.surface,
                borderColor: active ? colors.accent : colors.border,
              },
            ]}
          >
            <SXText variant="label" color={active ? "#FFFFFF" : colors.textSecondary} style={{ fontWeight: "600" }}>
              {opt.label}
            </SXText>
          </PressableScale>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: spacing.sm,
    paddingVertical: 2,
  },
  chip: {
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    minHeight: Math.max(36, touchTarget - 8),
    alignItems: "center",
    justifyContent: "center",
  },
});
