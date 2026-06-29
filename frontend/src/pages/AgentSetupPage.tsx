import { AgentSetupGuide } from "../components/AgentSetupGuide";
import { ConsoleHeader } from "../components/ConsoleHeader";

export function AgentSetupPage() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <ConsoleHeader
          eyebrow="Agent Setup"
          title="Device Onboarding"
          description="Generate agent credentials, configure the monitoring agent, and verify device telemetry ingestion."
        />

        <AgentSetupGuide />
      </section>
    </main>
  );
}