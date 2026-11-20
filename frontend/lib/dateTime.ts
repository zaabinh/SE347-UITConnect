export function formatRelativeTime(value: string): string {
  const hour = 60 * 60 * 1000;
  const day = 24 * hour;
  const timestamp = new Date(value).getTime();
  const delta = Math.max(1, Date.now() - timestamp);
  const hours = Math.floor(delta / hour);
  const days = Math.floor(delta / day);

  if (hours < 1) {
    const minutes = Math.max(1, Math.floor(delta / (60 * 1000)));
    return `${minutes}m ago`;
  }

  if (hours < 24) {
    return `${hours}h ago`;
  }

  return `${days}d ago`;
}
