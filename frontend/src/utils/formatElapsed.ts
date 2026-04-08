/**
 * Format a millisecond duration as a human-readable elapsed string.
 *
 * - < 1 hour  → "Xm YYs"
 * - ≥ 1 hour  → "Xh YYm YYs"
 */
export function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;

  if (h > 0) {
    return `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
  }
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/**
 * Format a millisecond duration as a short string (no seconds).
 *
 * - < 1 minute → "< 1m"
 * - < 1 hour   → "Xm"
 * - ≥ 1 hour   → "Xh YYm"
 */
export function formatElapsedShort(ms: number): string {
  const totalMin = Math.round(ms / 60000);
  if (totalMin < 1) return "< 1m";
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h > 0) {
    return m > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${h}h`;
  }
  return `${m}m`;
}
