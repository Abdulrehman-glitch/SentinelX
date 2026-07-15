import type { ReactNode } from "react";

type BadgeTone = "slate" | "green" | "amber" | "red" | "blue" | "violet";

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
};

const toneStyles: Record<BadgeTone, { background: string; color: string; border: string }> = {
  slate:  { background: "rgba(100,116,139,0.12)", color: "var(--sx-muted)",       border: "rgba(100,116,139,0.20)" },
  green:  { background: "rgba(16,185,129,0.10)",  color: "var(--sx-green)",       border: "rgba(16,185,129,0.22)"  },
  amber:  { background: "rgba(161,98,7,0.10)",    color: "var(--sx-amber)",       border: "rgba(161,98,7,0.22)"    },
  red:    { background: "rgba(244,63,94,0.10)",   color: "var(--sx-red)",         border: "rgba(244,63,94,0.22)"   },
  blue:   { background: "rgba(37,99,235,0.10)",   color: "var(--sx-blue)",        border: "rgba(37,99,235,0.22)"   },
  violet: { background: "rgba(13,148,136,0.10)",  color: "var(--sx-accent-text)", border: "rgba(13,148,136,0.25)"  },
};

export function Badge({ children, tone = "slate" }: BadgeProps) {
  const s = toneStyles[tone];
  return (
    <span
      className="sx-badge inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide"
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
  if (s === "info")     return "violet";
  return "slate";
}
