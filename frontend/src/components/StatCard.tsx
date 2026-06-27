type StatCardProps = {
  title: string;
  value: number;
  description: string;
};

export function StatCard({ title, value, description }: StatCardProps) {
  return (
    <article className="sx-kpi rounded-2xl p-5">
      <div className="h-1 w-16 rounded-full sx-accent-line" />

      <p className="mt-5 text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
        {title}
      </p>

      <p className="mt-3 text-4xl font-bold tracking-tight text-slate-50">
        {value}
      </p>

      <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
    </article>
  );
}