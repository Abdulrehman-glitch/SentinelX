import { ReactNode } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/theme/ThemeContext";
import { spacing } from "@/theme/tokens";
import { SXText } from "./SXText";

interface Props {
  title?: string;
  eyebrow?: string;
  headerRight?: ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  children: ReactNode;
  // Space for the floating glass tab bar.
  bottomInset?: boolean;
}

export function Screen({
  title,
  eyebrow,
  headerRight,
  scroll = true,
  refreshing = false,
  onRefresh,
  children,
  bottomInset = true,
}: Props) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();

  const header = (title || eyebrow) && (
    <View style={styles.header}>
      <View style={{ flex: 1, gap: 2 }}>
        {eyebrow ? (
          <SXText variant="meta" tone="tertiary" style={styles.eyebrow}>
            {eyebrow}
          </SXText>
        ) : null}
        {title ? <SXText variant="pageTitle">{title}</SXText> : null}
      </View>
      {headerRight}
    </View>
  );

  const content = (
    <>
      {header}
      {children}
    </>
  );

  if (!scroll) {
    return (
      <View style={[styles.fill, { backgroundColor: colors.background, paddingTop: insets.top + spacing.md }]}>
        <View style={styles.body}>{content}</View>
      </View>
    );
  }

  return (
    <View style={[styles.fill, { backgroundColor: colors.background }]}>
      <ScrollView
        contentContainerStyle={[
          styles.body,
          {
            paddingTop: insets.top + spacing.md,
            paddingBottom: bottomInset ? 104 + insets.bottom : insets.bottom + spacing.xxl,
          },
        ]}
        refreshControl={
          onRefresh ? (
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
          ) : undefined
        }
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {content}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  body: {
    paddingHorizontal: spacing.screenX,
    gap: spacing.lg,
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  eyebrow: {
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
});
