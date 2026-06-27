type BadgeTone = "slate" | "green" | "amber" | "red" | "blue";

type BadgeProps = {
  children: string;
  tone?: BadgeTone;
};

const toneClasses: Record<BadgeTone, string> = {
  slate: "border-slate-500/20 bg-slate-400/10 text-slate-300",
  green: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  amber: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  red: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  blue: "border-sky-400/25 bg-sky-400/10 text-sky-300",
};

export function Badge({ children, tone = "slate" }: BadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

export function getStatusTone(status?: string | null): BadgeTone {
  const normalisedStatus = status?.toLowerCase();

  if (
    normalisedStatus === "online" ||
    normalisedStatus === "resolved" ||
    normalisedStatus === "completed" ||
    normalisedStatus === "success" ||
    normalisedStatus === "logged" ||
    normalisedStatus === "healthy"
  ) {
    return "green";
  }

  if (
    normalisedStatus === "warning" ||
    normalisedStatus === "pending" ||
    normalisedStatus === "queued" ||
    normalisedStatus === "running" ||
    normalisedStatus === "investigating"
  ) {
    return "amber";
  }

  if (
    normalisedStatus === "offline" ||
    normalisedStatus === "critical" ||
    normalisedStatus === "failed" ||
    normalisedStatus === "error" ||
    normalisedStatus === "unresolved" ||
    normalisedStatus === "open"
  ) {
    return "red";
  }

  return "slate";
}

export function getSeverityTone(severity?: string | null): BadgeTone {
  const normalisedSeverity = severity?.toLowerCase();

  if (normalisedSeverity === "critical") {
    return "red";
  }

  if (normalisedSeverity === "warning") {
    return "amber";
  }

  if (normalisedSeverity === "info") {
    return "blue";
  }

  return "slate";
}