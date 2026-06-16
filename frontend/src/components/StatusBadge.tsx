type StatusBadgeProps = {
  label: string;
  status: string;
};

export function StatusBadge({ label, status }: StatusBadgeProps) {
  const isOnline = status.toLowerCase() === "online";

  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <span className="text-sm font-medium text-slate-600">{label}</span>

      <span
        className={`rounded-full px-3 py-1 text-xs font-semibold ${
          isOnline
            ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
            : "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
        }`}
      >
        {status}
      </span>
    </div>
  );
}