type MetricCardProps = {
  title: string;
  value?: number | null;
  suffix?: string;
  description: string;
};

function getMetricTone(value?: number | null) {
  if (typeof value !== "number") {
    return "border-slate-700 bg-slate-900/60 text-slate-50";
  }

  if (value >= 90) {
    return "border-rose-400/30 bg-rose-400/10 text-rose-100";
  }

  if (value >= 75) {
    return "border-amber-400/30 bg-amber-400/10 text-amber-100";
  }

  return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
}

export function MetricCard({
  title,
  value,
  suffix = "%",
  description,
}: MetricCardProps) {
  const displayValue =
    typeof value === "number" ? `${value.toFixed(1)}${suffix}` : "No data";

  return (
    <article className={`rounded-2xl border p-5 shadow-sm ${getMetricTone(value)}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.18em] opacity-75">
        {title}
      </p>

      <p className="mt-3 text-4xl font-bold tracking-tight">{displayValue}</p>

      <p className="mt-2 text-sm leading-6 opacity-75">{description}</p>
    </article>
  );
}