import { View } from "react-native";
import Svg, { Line, Path } from "react-native-svg";

import { useTheme } from "@/theme/ThemeContext";
import { SXText } from "./SXText";

interface Props {
  values: (number | null)[];
  height?: number;
  color?: string;
  max?: number;
  threshold?: number;
  accessibilityLabel?: string;
}

// §27 — small telemetry sparkline. Gaps in the data are left as gaps rather
// than interpolated across; an optional threshold line marks the alert level.
export function Sparkline({ values, height = 44, color, max = 100, threshold, accessibilityLabel }: Props) {
  const { colors } = useTheme();
  const stroke = color ?? colors.accentBlue;
  const width = 100; // viewBox units; scales to container

  if (values.length === 0 || values.every((v) => v == null)) {
    return (
      <View style={{ height, justifyContent: "center" }}>
        <SXText variant="meta" tone="tertiary">
          No data
        </SXText>
      </View>
    );
  }

  const step = values.length > 1 ? width / (values.length - 1) : width;
  let d = "";
  let penDown = false;
  values.forEach((v, i) => {
    if (v == null || Number.isNaN(v)) {
      penDown = false;
      return;
    }
    const x = i * step;
    const y = height - (Math.min(Math.max(v, 0), max) / max) * height;
    d += penDown ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : ` M ${x.toFixed(1)} ${y.toFixed(1)}`;
    penDown = true;
  });

  const thresholdY = threshold != null ? height - (threshold / max) * height : null;

  return (
    <View accessible accessibilityLabel={accessibilityLabel ?? "Telemetry trend"}>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {thresholdY != null && (
          <Line
            x1="0"
            y1={thresholdY}
            x2={width}
            y2={thresholdY}
            stroke={colors.status.warning}
            strokeWidth={0.7}
            strokeDasharray="3 2"
          />
        )}
        <Path d={d.trim()} stroke={stroke} strokeWidth={1.8} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      </Svg>
    </View>
  );
}
