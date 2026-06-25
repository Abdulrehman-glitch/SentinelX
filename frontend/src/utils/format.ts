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