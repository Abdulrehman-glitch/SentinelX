type MetricCardProps = {
  title: string;
  value?: number | null;
  suffix?: string;
  description: string;
};

function getMetricTone(value?: number | null): { borderColor: string; color: string; accent: string } {
  if (typeof value !== "number") {
    return { borderColor: "var(--sx-border)", color: "var(--sx-text)", accent: "var(--sx-muted)" };
  }
  if (value >= 90) {
    return { borderColor: "rgba(244,63,94,0.28)", color: "var(--sx-red)", accent: "rgba(244,63,94,0.12)" };
  }
  if (value >= 75) {
    return { borderColor: "rgba(245,158,11,0.28)", color: "var(--sx-amber)", accent: "rgba(245,158,11,0.10)" };
  }
  return { borderColor: "rgba(34,197,94,0.25)", color: "var(--sx-green)", accent: "rgba(34,197,94,0.08)" };
}

export function MetricCard({ title, value, suffix = "%", description }: MetricCardProps) {
  const displayValue = typeof value === "number" ? `${value.toFixed(1)}${suffix}` : "No data";
  const tone = getMetricTone(value);

  return (
    <article
      className="rounded-lg border p-5"
      style={{ background: "var(--sx-panel)", borderColor: tone.borderColor }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.18em]"
        style={{ color: "var(--sx-muted)", fontFamily: "var(--font-mono)" }}
      >
        {title}
      </p>

      <p
        className="mt-3 text-4xl font-bold tracking-tight"
        style={{ color: tone.color, fontFamily: "var(--font-ui)" }}
      >
        {displayValue}
      </p>

      <p className="mt-2 text-sm leading-5" style={{ color: "var(--sx-muted)" }}>
        {description}
      </p>
    </article>
  );
}
