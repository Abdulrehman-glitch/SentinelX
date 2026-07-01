import { useState } from "react";
import { PermissionGate } from "./PermissionGate";
import { useDevicesQuery } from "../hooks/useDevicesQuery";
import { useCreateRecoveryActionMutation } from "../hooks/useRecoveryMutations";
import type { Device } from "../types/api";

function getDeviceId(device: Device) {
  return device.id ?? device.device_id ?? "";
}

const actionTypes = [
  "restart_service",
  "clear_temp_files",
  "rotate_logs",
  "collect_diagnostics",
  "restart_agent",
  "network_check",
];

export function RecoveryCommandForm() {
  const devicesQuery = useDevicesQuery();
  const createRecoveryActionMutation = useCreateRecoveryActionMutation();

  const [deviceId, setDeviceId] = useState("");
  const [actionType, setActionType] = useState("restart_service");
  const [details, setDetails] = useState(
    "Safe recovery command logged from SentinelX Recovery Command Center.",
  );

  const firstDeviceId = devicesQuery.data?.[0]
    ? getDeviceId(devicesQuery.data[0])
    : "";

  const activeDeviceId = deviceId || firstDeviceId;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!activeDeviceId) {
      return;
    }

    await createRecoveryActionMutation.mutateAsync({
      device_id: activeDeviceId,
      action_type: actionType,
      status: "logged",
      details,
    });

    setDetails("Safe recovery command logged from SentinelX Recovery Command Center.");
  }

  return (
    <PermissionGate
      roles={["admin", "engineer"]}
      fallback={
        <section className="sx-panel rounded-2xl p-5 text-sm sx-c-muted">
          Recovery command execution is restricted to admins and engineers.
          Viewers can review logged recovery actions from the Recovery page.
        </section>
      }
    >
      <section className="sx-panel rounded-2xl p-5">
        <h2 className="text-lg font-bold sx-c-text">
          Safe Recovery Command
        </h2>

        <p className="mt-1 max-w-3xl text-sm leading-6 sx-c-muted">
          SentinelX MVP recovery actions are logged only. No destructive system
          action is executed from this interface.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 grid gap-4 lg:grid-cols-3">
          <div>
            <label className="text-sm font-semibold sx-c-muted">Device</label>
            <select
              value={activeDeviceId}
              onChange={(event) => setDeviceId(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            >
              {(devicesQuery.data ?? []).map((device) => {
                const id = getDeviceId(device);

                return (
                  <option key={id} value={id}>
                    {device.hostname}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="text-sm font-semibold sx-c-muted">
              Action Type
            </label>
            <select
              value={actionType}
              onChange={(event) => setActionType(event.target.value)}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            >
              {actionTypes.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-semibold sx-c-muted">Status</label>
            <input
              disabled
              value="logged"
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm opacity-70 outline-none"
            />
          </div>

          <div className="lg:col-span-3">
            <label className="text-sm font-semibold sx-c-muted">Details</label>
            <textarea
              value={details}
              onChange={(event) => setDetails(event.target.value)}
              rows={3}
              className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            />
          </div>

          <div className="lg:col-span-3">
            <button
              type="submit"
              disabled={
                createRecoveryActionMutation.isPending ||
                !activeDeviceId ||
                !details.trim()
              }
              className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createRecoveryActionMutation.isPending
                ? "Logging..."
                : "Log recovery command"}
            </button>
          </div>
        </form>
      </section>
    </PermissionGate>
  );
}