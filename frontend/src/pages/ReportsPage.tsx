import { ConsoleHeader } from "../components/ConsoleHeader";
import { ExecutiveReport } from "../components/ExecutiveReport";

export function ReportsPage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Reports"
          title="Operational Reporting"
          description="Generate evidence-ready operational summaries for demonstration, evaluation, and documentation."
        />

        <ExecutiveReport />
      </section>
    </main>
  );
}