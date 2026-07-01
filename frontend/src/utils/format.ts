export function formatDate(value?: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

/** Human "x min ago" style relative time. */
export function formatRelativeTime(value?: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Never";

  const diffMs = Date.now() - date.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 0) return "Just now";
  if (sec < 45) return "Just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day} day${day === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString();
}

/**
 * Recency bucket for a last-seen timestamp — used to colour a live status dot.
 * online: seen in the last 2 min, idle: last 15 min, else offline.
 */
export function lastSeenStatus(value?: string | null): "online" | "idle" | "offline" {
  if (!value) return "offline";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "offline";
  const min = (Date.now() - date.getTime()) / 60000;
  if (min <= 2) return "online";
  if (min <= 15) return "idle";
  return "offline";
}

export function formatLabel(value?: string | null) {
  if (!value) {
    return "Unknown";
  }

  return value
    .split("_")
    .map((word) => {
      if (!word) {
        return word;
      }

      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

export function truncateMiddle(value: string, maxLength = 18) {
  if (value.length <= maxLength) {
    return value;
  }

  const keep = Math.floor((maxLength - 3) / 2);

  return `${value.slice(0, keep)}...${value.slice(value.length - keep)}`;
}