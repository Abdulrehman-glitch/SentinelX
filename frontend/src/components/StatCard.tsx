const DELAY_CLASSES = [
  "",
  "sx-delay-1",
  "sx-delay-2",
  "sx-delay-3",
  "sx-delay-4",
  "sx-delay-5",
  "sx-delay-6",
];

type StatCardProps = {
  title: string;
  value: number;
  description: string;
  index?: number;
};

export function StatCard({ title, value, description, index = 0 }: StatCardProps) {
  const delayClass = DELAY_CLASSES[Math.min(index, DELAY_CLASSES.length - 1)];

  return (
    <article className={`sx-kpi rounded-2xl p-5 sx-animate-in ${delayClass}`}>
      <div className="h-1 w-16 rounded-full sx-accent-line" />

      <p className="mt-5 text-sm font-semibold uppercase tracking-[0.18em] sx-c-muted">
        {title}
      </p>

      <p className="mt-3 text-4xl font-bold tracking-tight sx-c-text">
        {value.toLocaleString()}
      </p>

      <p className="mt-2 text-sm leading-6 sx-c-muted">{description}</p>
    </article>
  );
}
