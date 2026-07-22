"use client";

import type { ReplayIndex } from "@/lib/schemas";
import { useUIStore } from "@/lib/store";
import { formatISTDate } from "@/lib/format";
import { cn } from "@/lib/cn";

/**
 * Replay mode (spec §11): swap the map + forecast to a historical window built
 * from OUT-OF-FOLD predictions only. The demo's Severe-winter drama (Nov 2025)
 * that the monsoon "now" cannot show.
 */
export function ReplayControl({ index }: { index: ReplayIndex }) {
  const active = useUIStore((s) => s.replayActive);
  const date = useUIStore((s) => s.replayDate);
  const setReplay = useUIStore((s) => s.setReplay);
  const dates = index.dates;
  if (dates.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={active}
        onClick={() => setReplay(!active, active ? null : dates[dates.length - 1])}
        className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs")}
        style={{
          borderColor: active ? "var(--line-airglow)" : "var(--line)",
          color: active ? "var(--color-airglow)" : "var(--color-ink-mute)",
          background: active ? "var(--color-airglow-ghost)" : "transparent",
        }}
      >
        <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: active ? "var(--color-airglow)" : "var(--color-ink-dim)" }} />
        Replay
      </button>
      {active && (
        <label className="flex items-center gap-1.5 text-xs text-ink-mute">
          <span className="sr-only">Replay date</span>
          <select
            value={date ?? ""}
            onChange={(e) => setReplay(true, e.target.value)}
            className="rounded-[var(--radius-sm)] border bg-[var(--color-deep)] px-2 py-1 text-xs text-ink"
            style={{ borderColor: "var(--line)" }}
          >
            {dates.map((d) => (
              <option key={d} value={d}>
                {formatISTDate(d)}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
