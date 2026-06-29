import { useEffect, useState, type FormEvent } from "react";
import { useUpdateUserSettingsMutation } from "../hooks/useSecurityMutations";
import type { UserSettings } from "../types/api";
import { applyAccessibilitySettings } from "../utils/accessibility";

type UserSettingsFormProps = {
  settings?: UserSettings | null;
};

const defaultSettings: UserSettings = {
  theme: "dark",
  density: "comfortable",
  font_size: "normal",
  reduce_motion: false,
  high_contrast: false,
  color_blind_mode: false,
  table_page_size: 10,
  auto_refresh_seconds: 15,
};

export function UserSettingsForm({ settings }: UserSettingsFormProps) {
  const updateSettingsMutation = useUpdateUserSettingsMutation();
  const [formState, setFormState] = useState<UserSettings>(defaultSettings);

  useEffect(() => {
    const nextSettings = settings ?? defaultSettings;
    setFormState(nextSettings);
    applyAccessibilitySettings(nextSettings);
  }, [settings]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const updatedSettings = await updateSettingsMutation.mutateAsync(formState);
    applyAccessibilitySettings(updatedSettings);
  }

  return (
    <section className="sx-panel mt-8 rounded-2xl p-5">
      <h2 className="text-lg font-bold text-slate-50">
        Accessibility & Interface Preferences
      </h2>

      <p className="mt-1 text-sm text-slate-400">
        Adjust density, contrast, motion and refresh preferences for the monitoring console.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 grid gap-5 lg:grid-cols-3">
        <div>
          <label className="text-sm font-semibold text-slate-300">Theme</label>
          <select
            value={formState.theme}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                theme: event.target.value as UserSettings["theme"],
              }))
            }
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value="dark">dark</option>
            <option value="light">light</option>
            <option value="system">system</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Density</label>
          <select
            value={formState.density}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                density: event.target.value as UserSettings["density"],
              }))
            }
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value="comfortable">comfortable</option>
            <option value="compact">compact</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">Font Size</label>
          <select
            value={formState.font_size}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                font_size: event.target.value as UserSettings["font_size"],
              }))
            }
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          >
            <option value="normal">normal</option>
            <option value="large">large</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">
            Table Page Size
          </label>
          <input
            type="number"
            min={5}
            max={50}
            value={formState.table_page_size}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                table_page_size: Number(event.target.value),
              }))
            }
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-slate-300">
            Auto Refresh Seconds
          </label>
          <input
            type="number"
            min={5}
            max={120}
            value={formState.auto_refresh_seconds}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                auto_refresh_seconds: Number(event.target.value),
              }))
            }
            className="sx-input mt-2 w-full rounded-xl px-3 py-2 text-sm outline-none"
          />
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
          <p className="text-sm font-semibold text-slate-300">Accessibility Toggles</p>

          <div className="mt-3 space-y-3 text-sm text-slate-300">
            {[
              ["reduce_motion", "Reduce motion"],
              ["high_contrast", "High contrast"],
              ["color_blind_mode", "Colour-blind-safe mode"],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-4">
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(formState[key as keyof UserSettings])}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      [key]: event.target.checked,
                    }))
                  }
                />
              </label>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3">
          <button
            type="submit"
            disabled={updateSettingsMutation.isPending}
            className="sx-button-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
          >
            {updateSettingsMutation.isPending ? "Saving..." : "Save settings"}
          </button>
        </div>
      </form>
    </section>
  );
}