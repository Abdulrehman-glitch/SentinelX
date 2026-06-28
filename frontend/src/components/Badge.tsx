type BadgeTone = "slate" | "green" | "amber" | "red" | "blue";

type BadgeProps = {
  children: string;
  tone?: BadgeTone;
};

const toneStyles: Record<BadgeTone, { background: string; color: string; border: string }> = {
  slate: { background: "rgba(100,116,139,0.12)", color: "#94a3b8", border: "rgba(100,116,139,0.2)" },
  green: { background: "rgba(34,197,94,0.1)",   color: "#4ade80", border: "rgba(34,197,94,0.22)" },
  amber: { background: "rgba(245,158,11,0.1)",  color: "#fbbf24", border: "rgba(245,158,11,0.22)" },
  red:   { background: "rgba(244,63,94,0.1)",   color: "#fb7185", border: "rgba(244,63,94,0.22)"  },
  blue:  { background: "rgba(96,165,250,0.1)",  color: "#93c5fd", border: "rgba(96,165,250,0.22)" },
};

export function Badge({ children, tone = "slate" }: BadgeProps) {
  const s = toneStyles[tone];
  return (
    <span
      className="inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-medium"
      style={{ background: s.background, color: s.color, borderColor: s.border }}
    >
      {children}
    </span>
  );
}

export function getStatusTone(status?: string | null): BadgeTone {
  const s = status?.toLowerCase();
  if (s === "online" || s === "resolved" || s === "completed" || s === "success" || s === "logged" || s === "healthy") return "green";
  if (s === "warning" || s === "pending" || s === "queued" || s === "running" || s === "investigating") return "amber";
  if (s === "offline" || s === "critical" || s === "failed" || s === "error" || s === "unresolved" || s === "open") return "red";
  return "slate";
}

export function getSeverityTone(severity?: string | null): BadgeTone {
  const s = severity?.toLowerCase();
  if (s === "critical") return "red";
  if (s === "warning")  return "amber";
  if (s === "info")     return "blue";
  return "slate";
}
