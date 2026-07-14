// §8 — exponential backoff with random jitter for the telemetry queue.

export interface BackoffOptions {
  baseMs?: number;
  maxMs?: number;
  factor?: number;
  jitterRatio?: number;
}

export function backoffDelay(attempt: number, opts: BackoffOptions = {}, random: () => number = Math.random): number {
  const base = opts.baseMs ?? 2_000;
  const max = opts.maxMs ?? 5 * 60_000;
  const factor = opts.factor ?? 2;
  const jitterRatio = opts.jitterRatio ?? 0.3;

  const exp = Math.min(base * Math.pow(factor, Math.max(0, attempt)), max);
  const jitter = exp * jitterRatio * (random() * 2 - 1);
  return Math.max(500, Math.round(exp + jitter));
}

// Auth failures must not be retried; rate limits and transient faults may be.
export function isRetryableStatus(status: number | undefined): boolean {
  if (status == null) return true; // network-level failure
  if (status === 429) return true;
  if (status >= 500) return true;
  return false;
}
