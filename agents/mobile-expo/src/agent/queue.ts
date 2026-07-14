import AsyncStorage from "@react-native-async-storage/async-storage";

// §8 — capped, persisted retry queue for heartbeats that failed to send.
// Entries carry a client id so a replayed heartbeat can be de-duplicated,
// and only non-sensitive state summaries — the device token stays in Keychain.

export interface QueuedHeartbeat {
  clientId: string;
  status: string;
  message: string;
  queuedAt: string;
  attempts: number;
}

export const QUEUE_CAP = 50;
const STORAGE_KEY = "sx.agent.heartbeatQueue";

// Pure helpers (unit-tested) -------------------------------------------------

export function enqueue(queue: QueuedHeartbeat[], entry: QueuedHeartbeat, cap = QUEUE_CAP): QueuedHeartbeat[] {
  if (queue.some((q) => q.clientId === entry.clientId)) return queue;
  const next = [...queue, entry];
  // Drop the oldest entries first when over cap.
  return next.length > cap ? next.slice(next.length - cap) : next;
}

export function removeSent(queue: QueuedHeartbeat[], clientIds: string[]): QueuedHeartbeat[] {
  const sent = new Set(clientIds);
  return queue.filter((q) => !sent.has(q.clientId));
}

export function markAttempt(queue: QueuedHeartbeat[], clientId: string): QueuedHeartbeat[] {
  return queue.map((q) => (q.clientId === clientId ? { ...q, attempts: q.attempts + 1 } : q));
}

// Persistence ----------------------------------------------------------------

export async function loadQueue(): Promise<QueuedHeartbeat[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as QueuedHeartbeat[]) : [];
  } catch {
    // Corrupted cache — reset rather than crash (§32 safe reset).
    await AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
    return [];
  }
}

export async function saveQueue(queue: QueuedHeartbeat[]): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
}

export async function clearQueue(): Promise<void> {
  await AsyncStorage.removeItem(STORAGE_KEY);
}
