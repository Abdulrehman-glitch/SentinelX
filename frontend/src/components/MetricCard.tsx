type MetricCardProps = {
  title: string;
  value?: number | null;
  suffix?: string;
  description: string;
};

function getMetricTone(value?: number | null) {
  if (typeof value !== "number") {
    return "border-slate-200 bg-white text-slate-950";
  }

  if (value >= 90) {
    return "border-rose-200 bg-rose-50 text-rose-900";
  }

  if (value >= 75) {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }

  return "border-emerald-200 bg-emerald-50 text-emerald-900";
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
      <p className="text-sm font-medium opacity-75">{title}</p>

      <p className="mt-3 text-4xl font-bold tracking-tight">{displayValue}</p>

      <p className="mt-2 text-sm opacity-75">{description}</p>
    </article>
  );
}