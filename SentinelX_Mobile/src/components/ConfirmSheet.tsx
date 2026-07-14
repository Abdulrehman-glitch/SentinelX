import { Modal, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useTheme } from "@/theme/ThemeContext";
import { radius, spacing } from "@/theme/tokens";
import { Button } from "./Button";
import { GlassSurface } from "./GlassSurface";
import { SXText } from "./SXText";

interface Props {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// §16/§23 — glass confirmation surface for important or destructive actions.
export function ConfirmSheet({ visible, title, message, confirmLabel, destructive, busy, onConfirm, onCancel }: Props) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <View style={styles.backdrop}>
        <GlassSurface cornerRadius={radius.sheet} style={[styles.sheet, { marginBottom: insets.bottom + spacing.lg }]}>
          <SXText variant="sectionTitle">{title}</SXText>
          <SXText variant="body" tone="secondary">
            {message}
          </SXText>
          <View style={styles.actions}>
            <Button label="Cancel" kind="secondary" onPress={onCancel} style={styles.actionButton} />
            <Button
              label={confirmLabel}
              kind={destructive ? "destructive" : "primary"}
              haptic={destructive ? "warning" : "selection"}
              loading={busy}
              onPress={onConfirm}
              style={styles.actionButton}
            />
          </View>
          <SXText variant="meta" color={colors.textTertiary}>
            This action is recorded in the audit log.
          </SXText>
        </GlassSurface>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(23,24,28,0.35)",
    justifyContent: "flex-end",
    paddingHorizontal: spacing.lg,
  },
  sheet: {
    padding: spacing.xxl,
    gap: spacing.md,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  actionButton: {
    flex: 1,
  },
});
