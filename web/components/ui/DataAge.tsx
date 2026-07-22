"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { dataAge, formatIST } from "@/lib/format";
import { useMounted } from "@/lib/hooks";

/**
 * Live data-age indicator from generated_at (spec §6). Shows an airglow "live"
 * pulse when fresh, a dim dot when stale. Absolute IST timestamp on hover.
 * Relative label renders only after mount to stay hydration-safe.
 */
export function DataAge({
  generatedAt,
  fixture,
  className,
  staleHours = 12,
}: {
  generatedAt: string;
  fixture?: boolean;
  className?: string;
  staleHours?: number;
}) {
  const mounted = useMounted();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  const { label, hours } = dataAge(generatedAt, now);
  const stale = hours > staleHours;
  const absolute = formatIST(generatedAt);

  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={`Data generated ${absolute}`}
    >
      <span
        aria-hidden
        className={cn("h-1.5 w-1.5 rounded-full", !stale && !fixture && "live-dot")}
        style={{ backgroundColor: fixture ? "var(--color-ember)" : stale ? "var(--color-ink-dim)" : "var(--color-airglow)" }}
      />
      <span className="tabular text-[0.7rem] text-ink-mute">
        {fixture ? "sample data" : mounted ? label : absolute}
      </span>
    </span>
  );
}
