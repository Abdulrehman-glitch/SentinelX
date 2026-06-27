import type { ReactNode } from "react";

type ConsolePanelProps = {
  children: ReactNode;
  className?: string;
};

export function ConsolePanel({ children, className = "" }: ConsolePanelProps) {
  return (
    <section className={`sx-panel rounded-2xl ${className}`}>
      {children}
    </section>
  );
}