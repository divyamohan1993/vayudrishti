import { cn } from "@/lib/cn";
import { AQI_STYLES } from "@/lib/aqi";
import type { AqiCategory } from "@/lib/schemas";

/**
 * AQI category, never colour-only (spec §7): a textured colour swatch ALWAYS
 * accompanied by the category label. `solid` fills a pill with the AA-contrast
 * foreground; `swatch` keeps the label in bone ink beside a decorative chip.
 */
export function AqiChip({
  category,
  value,
  variant = "swatch",
  className,
}: {
  category: AqiCategory;
  value?: number;
  variant?: "swatch" | "solid";
  className?: string;
}) {
  const s = AQI_STYLES[category];

  if (variant === "solid") {
    return (
      <span
        className={cn(
          "pat inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-0.5 text-xs font-semibold",
          s.pattern,
          className,
        )}
        style={{ backgroundColor: s.color, color: s.fg }}
      >
        {value != null && <span className="tabular">{Math.round(value)}</span>}
        <span>{category}</span>
      </span>
    );
  }

  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        aria-hidden
        className={cn("pat inline-block h-3 w-3 shrink-0 rounded-[3px]", s.pattern)}
        style={{ backgroundColor: s.color }}
      />
      <span className="text-xs text-ink-soft">
        {value != null && <span className="tabular mr-1 text-ink">{Math.round(value)}</span>}
        {category}
      </span>
    </span>
  );
}
