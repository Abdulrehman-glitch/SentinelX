type ShellBadgeProps = {
  label: string;
  value: string;
};

export function ShellBadge({ label, value }: ShellBadgeProps) {
  return (
    <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] sx-c-info">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-cyan-50">{value}</p>
    </div>
  );
}