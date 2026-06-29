import { ConsoleHeader } from "../components/ConsoleHeader";
import { MetricsExplorer } from "../components/MetricsExplorer";

export function MetricsExplorerPage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Metrics Explorer"
          title="Telemetry Investigation"
          description="Explore per-device telemetry history, compare resource usage trends, and export raw monitoring data."
        />

        <MetricsExplorer />
      </section>
    </main>
  );
}