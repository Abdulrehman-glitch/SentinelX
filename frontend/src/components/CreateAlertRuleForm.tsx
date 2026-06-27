import { useState } from "react";
import { useCreateAlertRuleMutation } from "../hooks/useOperationalMutations";

export function CreateAlertRuleForm() {
  const createAlertRuleMutation = useCreateAlertRuleMutation();

  const [name, setName] = useState("");
  const [metricType, setMetricType] = useState("cpu_percent");
  const [operator, setOperator] = useState(">=");
  const [threshold, setThreshold] = useState(90);
  const [severity, setSeverity] = useState("critical");
  const [description, setDescription] = useState("");
  const [cooldownSeconds, setCooldownSeconds] = useState(300);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!name.trim()) {
      return;
    }

    await createAlertRuleMutation.mutateAsync({
      name: name.trim(),
      metric_type: metricType,
      operator,
      threshold,
      severity,
      enabled: true,
      description: description.trim() || null,
      cooldown_seconds: cooldownSeconds,
    });

    setName("");
    setMetricType("cpu_percent");
    setOperator(">=");
    setThreshold(90);
    setSeverity("critical");
    setDescription("");
    setCooldownSeconds(300);
  }

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <h2 className="text-lg font-bold text-slate-50">Create Alert Rule</h2>
      <p className="mt-1 text-sm text-slate-400">
        Add a threshold rule for CPU, memory, or disk telemetry.
      </p>

      <form onSubmit={handleSubmit} className="mt-5 grid gap-4 lg:grid-cols-3">
        <div>
          <label className="text-sm font-semibold text-slate-300">Rule Name</label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="Critical CPU Usage"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Metric</label>
          <select
            value={metricType}
            onChange={(event) => setMetricType(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value="cpu_percent">cpu_percent</option>
            <option value="memory_percent">memory_percent</option>
            <option value="disk_percent">disk_percent</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Operator</label>
          <select
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value=">=">{">="}</option>
            <option value=">">{">"}</option>
            <option value="<=">{"<="}</option>
            <option value="<">{"<"}</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Threshold</label>
          <input
            type="number"
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
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
          <label className="text-sm font-semibold text-slate-300">Cooldown Seconds</label>
          <input
            type="number"
            value={cooldownSeconds}
            onChange={(event) => setCooldownSeconds(Number(event.target.value))}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          />
        </div>

        <div className="lg:col-span-3">
          <label className="text-sm font-semibold text-slate-300">Description</label>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="Triggers when CPU usage reaches or exceeds 90 percent."
          />
        </div>

        <div className="lg:col-span-3">
          <button
            type="submit"
            disabled={createAlertRuleMutation.isPending || !name.trim()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {createAlertRuleMutation.isPending ? "Creating..." : "Create rule"}
          </button>
        </div>
      </form>
    </section>
  );
}