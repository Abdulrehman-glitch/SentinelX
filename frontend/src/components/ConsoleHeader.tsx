import type { ReactNode } from "react";

type ConsoleHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function ConsoleHeader({
  eyebrow,
  title,
  description,
  children,
}: ConsoleHeaderProps) {
  return (
    <header className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-cyan-300/80">
          {eyebrow}
        </p>

        <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-50 md:text-5xl">
          {title}
        </h1>

        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
          {description}
        </p>
      </div>

      {children && <div className="flex flex-col items-start gap-2 lg:items-end">{children}</div>}
    </header>
  );
}