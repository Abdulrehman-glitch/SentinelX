import { useState } from "react";
import { useCreateIncidentMutation } from "../hooks/useOperationalMutations";

export function CreateIncidentForm() {
  const createIncidentMutation = useCreateIncidentMutation();

  const [title, setTitle] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [severity, setSeverity] = useState("warning");
  const [description, setDescription] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    await createIncidentMutation.mutateAsync({
      device_id: deviceId.trim() || null,
      title: title.trim(),
      description: description.trim() || null,
      severity,
      source: "manual",
      linked_alert_id: null,
      assigned_to: "Engineer",
    });

    setTitle("");
    setDeviceId("");
    setSeverity("warning");
    setDescription("");
  }

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <h2 className="text-lg font-bold text-slate-50">Create Incident</h2>
      <p className="mt-1 text-sm text-slate-400">
        Manually log an operational incident for investigation and timeline tracking.
      </p>

      <form onSubmit={handleSubmit} className="mt-5 grid gap-4 lg:grid-cols-2">
        <div>
          <label className="text-sm font-semibold text-slate-300">Title</label>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="High CPU utilisation incident"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Device ID</label>
          <input
            value={deviceId}
            onChange={(event) => setDeviceId(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="Optional device ID"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Severity</label>
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value="warning">warning</option>
            <option value="critical">critical</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Assigned To</label>
          <input
            disabled
            value="Engineer"
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm opacity-70 outline-none"
          />
        </div>

        <div className="lg:col-span-2">
          <label className="text-sm font-semibold text-slate-300">Description</label>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="Describe the incident context..."
          />
        </div>

        <div className="lg:col-span-2">
          <button
            type="submit"
            disabled={createIncidentMutation.isPending || !title.trim()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {createIncidentMutation.isPending ? "Creating..." : "Create incident"}
          </button>
        </div>
      </form>
    </section>
  );
}