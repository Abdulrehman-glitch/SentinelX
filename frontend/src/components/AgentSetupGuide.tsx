import { CopyBlock } from "./CopyBlock";
import { CreateDeviceCredentialForm } from "./CreateDeviceCredentialForm";
import { DeviceCredentialsTable } from "./DeviceCredentialsTable";
import { Badge } from "./Badge";
import { useDeviceCredentialsQuery } from "../hooks/useDeviceCredentialsQuery";
import { API_BASE_URL } from "../lib/api";

const agentEnvTemplate = `SENTINELX_API_BASE_URL=${API_BASE_URL}
SENTINELX_AGENT_TOKEN=PASTE_GENERATED_AGENT_TOKEN_HERE
SENTINELX_HEARTBEAT_INTERVAL_SECONDS=15
SENTINELX_METRIC_INTERVAL_SECONDS=10`;

const backendCommand = `cd /d C:\\SentinelX\\backend
.venv\\Scripts\\activate
uvicorn app.main:app --reload`;

const agentCommand = `cd /d C:\\SentinelX\\agent
.venv\\Scripts\\activate
python -m sentinelx_agent.main`;

const frontendCommand = `cd /d C:\\SentinelX\\frontend
npm run dev -- --host 127.0.0.1 --port 5173`;

export function AgentSetupGuide() {
  const credentialsQuery = useDeviceCredentialsQuery();

  return (
    <>
      <section className="sx-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-50">
              Agent Onboarding Wizard
            </h2>

            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
              Generate a device credential, configure the local agent, start the
              backend, and verify live heartbeat/metric ingestion.
            </p>
          </div>

          <Badge tone="green">Secure onboarding</Badge>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-4">
          {[
            ["1", "Create credential", "Generate an agent token from SentinelX."],
            ["2", "Configure .env", "Paste the token into the agent environment."],
            ["3", "Run backend", "Start FastAPI before the agent."],
            ["4", "Run agent", "Verify device, heartbeat, metrics, and alerts."],
          ].map(([step, title, description]) => (
            <article
              key={step}
              className="rounded-2xl border border-white/[0.056] bg-black/25 p-4"
            >
              <p className="font-mono text-xs font-bold text-violet-400">
                STEP {step}
              </p>
              <h3 className="mt-2 font-bold text-slate-50">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <CreateDeviceCredentialForm />

      <section className="mt-8 grid gap-5 xl:grid-cols-2">
        <CopyBlock title="Agent .env template" value={agentEnvTemplate} />
        <CopyBlock title="Start backend" value={backendCommand} />
        <CopyBlock title="Start agent" value={agentCommand} />
        <CopyBlock title="Start frontend locked to 5173" value={frontendCommand} />
      </section>

      <section className="sx-panel mt-8 rounded-2xl p-5">
        <h2 className="text-lg font-bold text-slate-50">
          Verification Checklist
        </h2>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {[
            "Backend health endpoint returns online.",
            "Agent terminal shows registration/heartbeat activity.",
            "Devices page shows the new monitored machine.",
            "Device detail page shows latest CPU, memory, and disk metrics.",
            "Metrics Explorer chart updates from backend data.",
            "Audit logs record credential creation/revocation.",
          ].map((item) => (
            <div
              key={item}
              className="rounded-xl border border-white/[0.056] bg-black/25 p-4 text-sm text-slate-300"
            >
              {item}
            </div>
          ))}
        </div>
      </section>

      <DeviceCredentialsTable credentials={credentialsQuery.data ?? []} />
    </>
  );
}