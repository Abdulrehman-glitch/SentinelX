import { useEffect, useState, type FormEvent } from "react";
import { useUpdateUserSettingsMutation } from "../hooks/useSecurityMutations";
import type { UserSettings } from "../types/api";
import { applyAccessibilitySettings, persistUiSettings } from "../utils/accessibility";

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

// Pill-toggle component replacing <select> dropdowns
function PillToggle<T extends string>({
  label,
  description,
  value,
  options,
  onChange,
}: {
  label: string;
  description?: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div>
      <p className="text-sm font-semibold" style={{ color: "var(--sx-text)" }}>{label}</p>
      {description && (
        <p className="mt-0.5 text-xs" style={{ color: "var(--sx-muted)" }}>{description}</p>
      )}
      <div
        className="mt-2 flex overflow-hidden rounded-xl"
        role="group"
        aria-label={label}
        style={{ border: "1px solid var(--sx-border-md)", background: "rgba(0,0,0,0.2)" }}
      >
        {options.map((opt, i) => (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={value === opt.value}
            onClick={() => onChange(opt.value)}
            className="flex-1 py-2.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-inset"
            style={{
              background: value === opt.value
                ? "linear-gradient(135deg, var(--sx-accent) 0%, var(--sx-accent-2) 100%)"
                : "transparent",
              color: value === opt.value ? "#ffffff" : "var(--sx-muted)",
              borderRight: i < options.length - 1 ? "1px solid var(--sx-border)" : "none",
              fontFamily: "var(--font-ui)",
              letterSpacing: "0.01em",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// Improved slider with value display
function SliderField({
  label,
  description,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  description?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  const percent = ((value - min) / (max - min)) * 100;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-semibold" style={{ color: "var(--sx-text)" }}>{label}</p>
        <span
          className="text-sm font-bold tabular-nums"
          style={{ color: "var(--sx-accent)", fontFamily: "var(--font-mono)" }}
        >
          {value}{unit}
        </span>
      </div>
      {description && (
        <p className="mt-0.5 text-xs" style={{ color: "var(--sx-muted)" }}>{description}</p>
      )}
      <div className="relative mt-3">
        <input
          type="range"
          min={min}
          max={max}
          step={step ?? 1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="sx-range w-full"
          aria-label={label}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-valuetext={`${value}${unit ?? ""}`}
          style={{ "--range-pct": `${percent}%` } as React.CSSProperties}
        />
        <div
          className="mt-1.5 flex justify-between"
          style={{ fontFamily: "var(--font-mono)", fontSize: "0.62rem", color: "var(--sx-dim)" }}
        >
          <span>{min}{unit}</span>
          <span>{max}{unit}</span>
        </div>
      </div>
    </div>
  );
}

// Accessible toggle switch
function ToggleSwitch({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start justify-between gap-4 cursor-pointer group">
      <div className="flex-1">
        <p
          className="text-sm font-semibold transition-colors group-hover:opacity-90"
          style={{ color: "var(--sx-text)" }}
        >
          {label}
        </p>
        {description && (
          <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--sx-muted)" }}>
            {description}
          </p>
        )}
      </div>
      <div className="relative shrink-0 mt-0.5" aria-hidden="true">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only"
          aria-label={label}
        />
        <div
          onClick={() => onChange(!checked)}
          className="relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-200 focus-within:ring-2 focus-within:ring-violet-500 focus-within:ring-offset-1"
          style={{
            background: checked
              ? "linear-gradient(135deg, var(--sx-accent), var(--sx-accent-2))"
              : "var(--sx-border-md)",
            cursor: "pointer",
          }}
          role="switch"
          aria-checked={checked}
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); onChange(!checked); } }}
        >
          <span
            className="inline-block h-4 w-4 rounded-full bg-white transition-transform duration-200 shadow-sm"
            style={{ transform: checked ? "translateX(1.375rem)" : "translateX(0.25rem)" }}
          />
        </div>
      </div>
    </label>
  );
}

export function UserSettingsForm({ settings }: UserSettingsFormProps) {
  const updateSettingsMutation = useUpdateUserSettingsMutation();
  const [formState, setFormState] = useState<UserSettings>(defaultSettings);

  useEffect(() => {
    const nextSettings = settings ?? defaultSettings;
    setFormState(nextSettings);
    applyAccessibilitySettings(nextSettings);
  }, [settings]);

  useEffect(() => {
    applyAccessibilitySettings(formState);
  }, [formState]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const updatedSettings = await updateSettingsMutation.mutateAsync(formState);
    persistUiSettings(updatedSettings);
    applyAccessibilitySettings(updatedSettings);
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-8">

      {/* ── Section: Appearance ─────────────────────────── */}
      <section className="sx-panel rounded-2xl p-6">
        <h3 className="text-base font-bold mb-1" style={{ color: "var(--sx-text)" }}>
          Appearance
        </h3>
        <p className="text-xs mb-5" style={{ color: "var(--sx-muted)" }}>
          Adjust the visual presentation of the monitoring console.
        </p>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <PillToggle
            label="Theme"
            description="Choose your preferred colour scheme."
            value={formState.theme}
            options={[
              { value: "dark" as const, label: "Dark" },
              { value: "light" as const, label: "Light" },
              { value: "system" as const, label: "System" },
            ]}
            onChange={(v) => setFormState((s) => ({ ...s, theme: v }))}
          />

          <PillToggle
            label="Density"
            description="Controls spacing between interface elements."
            value={formState.density}
            options={[
              { value: "comfortable" as const, label: "Comfortable" },
              { value: "compact" as const, label: "Compact" },
            ]}
            onChange={(v) => setFormState((s) => ({ ...s, density: v }))}
          />

          <PillToggle
            label="Font Size"
            description="Base text size for the whole interface."
            value={formState.font_size}
            options={[
              { value: "normal" as const, label: "Normal" },
              { value: "large" as const, label: "Large" },
            ]}
            onChange={(v) => setFormState((s) => ({ ...s, font_size: v }))}
          />
        </div>
      </section>

      {/* ── Section: Data & Refresh ─────────────────────── */}
      <section className="sx-panel rounded-2xl p-6">
        <h3 className="text-base font-bold mb-1" style={{ color: "var(--sx-text)" }}>
          Data & Refresh
        </h3>
        <p className="text-xs mb-5" style={{ color: "var(--sx-muted)" }}>
          Control how much data is shown and how frequently it refreshes.
        </p>

        <div className="grid gap-8 sm:grid-cols-2">
          <SliderField
            label="Table Page Size"
            description="Number of rows shown per table page."
            value={formState.table_page_size}
            min={5}
            max={50}
            step={5}
            unit=" rows"
            onChange={(v) => setFormState((s) => ({ ...s, table_page_size: v }))}
          />

          <SliderField
            label="Auto-Refresh Interval"
            description="How often the dashboard data updates automatically."
            value={formState.auto_refresh_seconds}
            min={5}
            max={120}
            step={5}
            unit="s"
            onChange={(v) => setFormState((s) => ({ ...s, auto_refresh_seconds: v }))}
          />
        </div>
      </section>

      {/* ── Section: Accessibility ──────────────────────── */}
      <section className="sx-panel rounded-2xl p-6">
        <h3 className="text-base font-bold mb-1" style={{ color: "var(--sx-text)" }}>
          Accessibility
        </h3>
        <p className="text-xs mb-5" style={{ color: "var(--sx-muted)" }}>
          Make the interface more comfortable and usable for your needs.
        </p>

        <div className="space-y-5">
          <ToggleSwitch
            label="Reduce Motion"
            description="Disables animations and transitions throughout the interface. Recommended for motion sensitivity."
            checked={formState.reduce_motion}
            onChange={(v) => setFormState((s) => ({ ...s, reduce_motion: v }))}
          />

          <div
            className="border-t"
            style={{ borderColor: "var(--sx-border)" }}
          />

          <ToggleSwitch
            label="High Contrast"
            description="Increases border and text contrast ratios for improved legibility."
            checked={formState.high_contrast}
            onChange={(v) => setFormState((s) => ({ ...s, high_contrast: v }))}
          />

          <div className="border-t" style={{ borderColor: "var(--sx-border)" }} />

          <ToggleSwitch
            label="Colour-Blind Safe Mode"
            description="Replaces colour-only indicators with patterns that are distinguishable without colour vision."
            checked={formState.color_blind_mode}
            onChange={(v) => setFormState((s) => ({ ...s, color_blind_mode: v }))}
          />
        </div>
      </section>

      {/* ── Save ────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={updateSettingsMutation.isPending}
          className="sx-button-primary rounded-xl px-6 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          {updateSettingsMutation.isPending ? (
            <span className="flex items-center gap-2">
              <span className="sx-spinner" aria-hidden="true" />
              Saving…
            </span>
          ) : (
            "Save preferences"
          )}
        </button>

        {updateSettingsMutation.isSuccess && (
          <span className="text-sm font-medium" style={{ color: "var(--sx-green)" }}>
            Saved successfully
          </span>
        )}
        {updateSettingsMutation.isError && (
          <span className="text-sm font-medium" style={{ color: "var(--sx-red)" }}>
            Failed to save. Please try again.
          </span>
        )}
      </div>
    </form>
  );
}
