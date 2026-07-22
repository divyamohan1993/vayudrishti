import { cn } from "@/lib/cn";
import { CONFIDENCE_META } from "@/lib/aqi";
import type { Confidence } from "@/lib/schemas";

/**
 * Confidence tier, encoded identically everywhere (spec §5.0): a 3-bar signal
 * gauge (non-colour cue) + a text label. Never colour alone.
 */
export function ConfidenceTag({
  level,
  showLabel = true,
  className,
}: {
  level: Confidence;
  showLabel?: boolean;
  className?: string;
}) {
  const m = CONFIDENCE_META[level];
  const filled = level === "high" ? 3 : level === "med" ? 2 : 1;
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={`${m.label} confidence`}
    >
      <span aria-hidden className="flex h-3 items-end gap-[2px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-[3px] rounded-[1px]"
            style={{
              height: `${((i + 1) / 3) * 100}%`,
              backgroundColor: i < filled ? m.color : "var(--color-surface-3)",
            }}
          />
        ))}
      </span>
      {showLabel && (
        <span className="text-[0.68rem] font-medium uppercase tracking-wider text-ink-mute">
          {m.label}
        </span>
      )}
      <span className="sr-only">{m.label} confidence</span>
    </span>
  );
}
