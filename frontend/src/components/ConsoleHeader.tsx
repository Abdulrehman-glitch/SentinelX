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
    <header className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between sx-animate-in">
      <div>
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.26em]"
          style={{ color: "var(--sx-accent)", fontFamily: "var(--font-mono)" }}
        >
          {eyebrow}
        </p>

        <h1
          className="mt-2.5 text-3xl font-bold tracking-tight md:text-4xl"
          style={{ color: "var(--sx-text)", fontFamily: "var(--font-ui)" }}
        >
          {title}
        </h1>

        <div className="sx-accent-line mt-3 sx-animate-in sx-delay-2" />

        <p
          className="mt-3 max-w-3xl text-sm leading-6 sx-animate-in sx-delay-3"
          style={{ color: "var(--sx-muted)" }}
        >
          {description}
        </p>
      </div>

      {children && (
        <div className="flex flex-col items-start gap-2 lg:items-end sx-animate-in sx-delay-2">
          {children}
        </div>
      )}
    </header>
  );
}
