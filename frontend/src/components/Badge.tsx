type BadgeTone = "slate" | "green" | "amber" | "red" | "blue";

type BadgeProps = {
  children: string;
  tone?: BadgeTone;
};

const toneClasses: Record<BadgeTone, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  red: "bg-rose-50 text-rose-700 ring-rose-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
};

export function Badge({ children, tone = "slate" }: BadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${toneClasses[tone]}`}
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
    normalisedStatus === "logged"
  ) {
    return "green";
  }

  if (
    normalisedStatus === "warning" ||
    normalisedStatus === "pending" ||
    normalisedStatus === "queued" ||
    normalisedStatus === "running"
  ) {
    return "amber";
  }

  if (
    normalisedStatus === "offline" ||
    normalisedStatus === "critical" ||
    normalisedStatus === "failed" ||
    normalisedStatus === "error" ||
    normalisedStatus === "unresolved"
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