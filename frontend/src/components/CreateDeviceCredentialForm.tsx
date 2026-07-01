import { useState, type FormEvent } from "react";
import { useCreateDeviceCredentialMutation } from "../hooks/useSecurityMutations";
import type { CreatedDeviceCredential } from "../types/api";

export function CreateDeviceCredentialForm() {
  const createCredentialMutation = useCreateDeviceCredentialMutation();

  const [name, setName] = useState("Local laptop agent token");
  const [deviceId, setDeviceId] = useState("");
  const [createdCredential, setCreatedCredential] =
    useState<CreatedDeviceCredential | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const response = await createCredentialMutation.mutateAsync({
      name: name.trim(),
      device_id: deviceId.trim() || null,
    });

    setCreatedCredential(response);
    setName("Local laptop agent token");
    setDeviceId("");
  }

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <h2 className="text-lg font-bold text-slate-50">Create Agent Credential</h2>

      <p className="mt-1 text-sm text-slate-400">
        Generate a device/agent token. The raw token is shown once only.
      </p>

      {createdCredential && (
        <div className="mt-5 rounded-2xl border border-violet-500/25 bg-violet-500/10 p-4">
          <p className="text-sm font-semibold text-violet-300">
            Copy this token now. It will not be shown again.
          </p>

          <code className="mt-3 block overflow-x-auto rounded-xl bg-black/40 p-3 font-mono text-xs text-amber-100">
            {createdCredential.token}
          </code>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 grid gap-4 lg:grid-cols-2">
        <div>
          <label className="text-sm font-semibold text-slate-300">Credential name</label>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">
            Device ID optional
          </label>
          <input
            value={deviceId}
            onChange={(event) => setDeviceId(event.target.value)}
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
            placeholder="Optional existing device ID"
          />
        </div>

        <div className="lg:col-span-2">
          <button
            type="submit"
            disabled={createCredentialMutation.isPending || !name.trim()}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {createCredentialMutation.isPending
              ? "Creating..."
              : "Generate credential"}
          </button>
        </div>
      </form>
    </section>
  );
}