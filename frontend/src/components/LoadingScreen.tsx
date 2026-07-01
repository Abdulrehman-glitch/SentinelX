import { useEffect, useState } from "react";

const LOADING_STEPS = [
  "Authenticating session",
  "Loading organization",
  "Verifying permissions",
  "Fetching device fleet",
  "Connecting telemetry stream",
  "Preparing console",
];

type Props = {
  onComplete?: () => void;
  durationMs?: number;
};

export function LoadingScreen({ onComplete, durationMs = 2600 }: Props) {
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const stepDuration = durationMs / LOADING_STEPS.length;
    const interval = setInterval(() => {
      setStep((s) => {
        if (s < LOADING_STEPS.length - 1) return s + 1;
        clearInterval(interval);
        setTimeout(() => {
          setDone(true);
          onComplete?.();
        }, stepDuration * 0.6);
        return s;
      });
    }, stepDuration);

    return () => clearInterval(interval);
  }, [durationMs, onComplete]);

  return (
    <div className={`sx-loading-screen ${done ? "sx-loading-done" : ""}`} role="status" aria-label="Loading SentinelX">
      <div className="sx-loading-inner">
        {/* Logo */}
        <div className="sx-loading-logo">
          <div className="sx-loading-badge">
            <span>SX</span>
            <div className="sx-loading-ring" aria-hidden="true" />
          </div>
          <p className="sx-loading-brand">SentinelX</p>
          <p className="sx-loading-tagline">Operations Console</p>
        </div>

        {/* Progress bar */}
        <div className="sx-loading-bar-wrap" aria-hidden="true">
          <div
            className="sx-loading-bar-fill"
            style={{ width: `${((step + 1) / LOADING_STEPS.length) * 100}%` }}
          />
        </div>

        {/* Steps */}
        <div className="sx-loading-steps" aria-live="polite">
          <p className="sx-loading-step-text">{LOADING_STEPS[step]}</p>
          <p className="sx-loading-step-count">
            {step + 1} / {LOADING_STEPS.length}
          </p>
        </div>
      </div>
    </div>
  );
}
