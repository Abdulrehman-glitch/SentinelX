import { ConsoleHeader } from "../components/ConsoleHeader";
import { ExecutiveReport } from "../components/ExecutiveReport";

export function ReportsPage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Reporting"
          title="Operational Reports"
          description="Generate formal, period-scoped operational reports across fleet health, alerts, incidents, recovery and audit — ready to export or print."
        />

        <ExecutiveReport />
      </section>
    </main>
  );
}