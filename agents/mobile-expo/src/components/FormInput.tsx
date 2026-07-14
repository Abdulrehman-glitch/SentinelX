import { useState } from "react";
import { Pressable, StyleSheet, TextInput, TextInputProps, View } from "react-native";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing, touchTarget } from "@/theme/tokens";
import { SXText } from "./SXText";

interface Props extends TextInputProps {
  label: string;
  error?: string | null;
  secureToggle?: boolean;
}

export function FormInput({ label, error, secureToggle, secureTextEntry, style, ...rest }: Props) {
  const { colors } = useTheme();
  const [hidden, setHidden] = useState(secureTextEntry ?? false);

  return (
    <View style={{ gap: 6 }}>
      <SXText variant="label" tone="secondary">
        {label}
      </SXText>
      <View
        style={[
          styles.field,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.status.critical : colors.border,
          },
        ]}
      >
        <TextInput
          {...rest}
          secureTextEntry={secureToggle ? hidden : secureTextEntry}
          placeholderTextColor={colors.textTertiary}
          style={[styles.input, { color: colors.textPrimary }, style]}
          accessibilityLabel={label}
        />
        {secureToggle && (
          <Pressable
            onPress={() => setHidden((h) => !h)}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={hidden ? "Show password" : "Hide password"}
          >
            <SXText variant="label" tone="accent">
              {hidden ? "Show" : "Hide"}
            </SXText>
          </Pressable>
        )}
      </View>
      {error ? (
        <SXText variant="meta" color={colors.status.critical} accessibilityRole="alert">
          {error}
        </SXText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: radius.button,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    minHeight: touchTarget + 6,
    gap: spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: 16,
    paddingVertical: spacing.md,
  },
});
