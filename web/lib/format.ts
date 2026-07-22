/**
 * Display formatting. Storage is UTC ISO-8601 (spec §5.0); the UI always shows
 * IST (Asia/Kolkata) with an explicit "IST" suffix. ASCII hyphen/minus only
 * (no unicode dashes) so generated strings pass the humanizer gate.
 */

const IST = "Asia/Kolkata";

function toDate(iso: string): Date | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** e.g. "22 Jul 2026, 6:30 PM IST" */
export function formatIST(iso: string): string {
  const d = toDate(iso);
  if (!d) return "unknown";
  const s = new Intl.DateTimeFormat("en-IN", {
    timeZone: IST,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(d);
  return `${s} IST`;
}

/** Date only, e.g. "22 Jul 2026" (for calendars / windows). */
export function formatISTDate(iso: string): string {
  const d = toDate(iso);
  if (!d) return "unknown";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST,
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(d);
}

/** Short time, e.g. "6:30 PM IST" (timeline ticks). */
export function formatISTTime(iso: string): string {
  const d = toDate(iso);
  if (!d) return "unknown";
  const s = new Intl.DateTimeFormat("en-IN", {
    timeZone: IST,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(d);
  return `${s} IST`;
}

/** Human data-age relative to now, e.g. "3h ago", "just now", "2d ago". */
export function dataAge(iso: string, now: number = Date.now()): { label: string; hours: number } {
  const d = toDate(iso);
  if (!d) return { label: "unknown", hours: Infinity };
  const ms = now - d.getTime();
  const hours = ms / 3_600_000;
  if (ms < 0) return { label: "scheduled", hours: 0 };
  if (hours < 1) {
    const mins = Math.max(1, Math.round(ms / 60_000));
    return { label: mins <= 1 ? "just now" : `${mins}m ago`, hours };
  }
  if (hours < 24) return { label: `${Math.round(hours)}h ago`, hours };
  const days = Math.round(hours / 24);
  return { label: `${days}d ago`, hours };
}

/** Round to fixed digits, dropping trailing zeros; real ASCII minus. */
export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n == null || Number.isNaN(n)) return "-";
  const v = Number(n.toFixed(digits));
  return v.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

/** Signed number, always shows the sign (for deltas). */
export function fmtSigned(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "-";
  const v = Number(n.toFixed(digits));
  const s = Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: digits });
  return `${v > 0 ? "+" : v < 0 ? "-" : ""}${s}`;
}

/** Compact large counts, e.g. 12400 -> "12.4K", 2_100_000 -> "2.1M". */
export function fmtCompact(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "-";
  return Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: digits,
  }).format(n);
}

/** Confidence interval as "lo to hi" (word, gate-safe). */
export function fmtCI(low: number, high: number, digits = 0): string {
  return `${fmtNum(low, digits)} to ${fmtNum(high, digits)}`;
}

/** IST hour-of-day (0-23) for a timestamp, for diurnal axis ticks. */
export function istHour(iso: string): number | null {
  const d = toDate(iso);
  if (!d) return null;
  const h = new Intl.DateTimeFormat("en-GB", {
    timeZone: IST,
    hour: "2-digit",
    hour12: false,
  }).format(d);
  return Number(h);
}
