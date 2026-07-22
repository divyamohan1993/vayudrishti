import type { GrapCalendarEntry } from "@/lib/schemas";
import { formatISTDate } from "@/lib/format";
import { stageLabel } from "@/lib/i18n";
import { safeHref } from "@/lib/url";

/** GRAP stage calendar. Every window cites its CAQM order (public record). */
export function GrapOrders({ calendar }: { calendar: GrapCalendarEntry[] }) {
  return (
    <ol className="flex flex-col gap-1.5">
      {calendar.map((c, i) => {
        const href = safeHref(c.source_url);
        return (
          <li
            key={i}
            className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-[var(--radius-sm)] border px-3 py-2 text-xs"
            style={{ borderColor: "var(--line)" }}
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-ink">{stageLabel(c.stage)}</span>
              <span className="tabular text-ink-mute">
                {formatISTDate(c.start_utc)}
                {c.end_utc ? ` to ${formatISTDate(c.end_utc)}` : " (ongoing)"}
              </span>
            </span>
            {href ? (
              <a href={href} target="_blank" rel="noopener noreferrer" className="whitespace-nowrap text-airglow">
                CAQM order &#8599;
              </a>
            ) : (
              <span className="text-ink-dim">order link unavailable</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
