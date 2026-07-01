import { Badge, getStatusTone } from "./Badge";

type StatusBadgeProps = {
  label: string;
  status: string;
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  return (
    <div className="sx-panel rounded-2xl px-5 py-4">
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm font-semibold uppercase tracking-[0.18em] sx-c-muted">
          {label}
        </span>

        <Badge tone={getStatusTone(status)}>{status}</Badge>
      </div>
    </div>
  );
}