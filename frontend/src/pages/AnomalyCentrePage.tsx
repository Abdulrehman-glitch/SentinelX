import { AnomalyCentre } from "../components/AnomalyCentre";
import { ConsoleHeader } from "../components/ConsoleHeader";

export function AnomalyCentrePage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Anomaly Centre"
          title="Signal Investigation"
          description="Correlate backend alerts with threshold-derived telemetry anomalies for faster device investigation."
        />

        <AnomalyCentre />
      </section>
    </main>
  );
}