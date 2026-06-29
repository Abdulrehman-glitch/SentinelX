import { PermissionGate } from "./PermissionGate";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useCreateRecoveryActionMutation } from "../hooks/useRecoveryMutations";
import type { Device } from "../types/api";

type Playbook = {
  name: string;
  action_type: string;
  description: string;
  details: string;
};

const playbooks: Playbook[] = [
  {
    name: "High CPU Investigation",
    action_type: "collect_diagnostics",
    description: "Log a diagnostic collection action for sustained CPU pressure.",
    details:
      "Playbook: High CPU Investigation. Collect process/resource diagnostics and link action to alert review.",
  },
  {
    name: "Memory Pressure Response",
    action_type: "restart_service",
    description: "Log a safe service restart recommendation for memory pressure.",
    details:
      "Playbook: Memory Pressure Response. Logged safe restart_service action for engineering review.",
  },
  {
    name: "Disk Usage Cleanup",
    action_type: "clear_temp_files",
    description: "Log a temp-file cleanup recovery action for disk pressure.",
    details:
      "Playbook: Disk Usage Cleanup. Logged clear_temp_files action for traceability.",
  },
  {
    name: "Agent Connectivity Check",
    action_type: "network_check",
    description: "Log a network check for heartbeat or connectivity problems.",
    details:
      "Playbook: Agent Connectivity Check. Logged network_check action after connectivity warning.",
  },
];

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

export function RecoveryPlaybookTemplates() {
  const devicesQuery = useDevicesQuery();
  const createRecoveryActionMutation = useCreateRecoveryActionMutation();

  const firstDevice = devicesQuery.data?.[0] ?? null;
  const firstDeviceId = firstDevice ? getDeviceId(firstDevice) : "";

  async function runPlaybook(playbook: Playbook) {
    if (!firstDeviceId) {
      return;
    }

    await createRecoveryActionMutation.mutateAsync({
      device_id: firstDeviceId,
      action_type: playbook.action_type,
      status: "logged",
      details: playbook.details,
    });
  }

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <div>
        <h2 className="text-lg font-bold text-slate-50">
          Safe Recovery Playbooks
        </h2>

        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
          Predefined safe playbooks for the MVP. They log recovery intent and
          evidence only; no destructive action is executed.
        </p>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {playbooks.map((playbook) => (
          <article
            key={playbook.name}
            className="rounded-2xl border border-white/[0.056] bg-black/25 p-4"
          >
            <h3 className="font-bold text-slate-50">{playbook.name}</h3>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              {playbook.description}
            </p>

            <p className="mt-3 font-mono text-xs text-slate-500">
              Action: {playbook.action_type}
            </p>

            <PermissionGate
              roles={["admin", "engineer"]}
              fallback={
                <p className="mt-4 text-xs font-semibold text-slate-500">
                  Read only for viewers
                </p>
              }
            >
              <button
                type="button"
                onClick={() => runPlaybook(playbook)}
                disabled={
                  createRecoveryActionMutation.isPending || !firstDeviceId
                }
                className="sx-button-primary mt-4 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                Log playbook
              </button>
            </PermissionGate>
          </article>
        ))}
      </div>
    </section>
  );
}