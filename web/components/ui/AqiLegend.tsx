import { cn } from "@/lib/cn";
import { AQI_ORDER, AQI_STYLES } from "@/lib/aqi";

/**
 * The CPCB AQI reference. Each category shows its textured colour, name, and
 * sub-index range, so the map's colours are decodable without relying on hue
 * (the satisfactory/moderate pair is only ΔE 11.3 apart — texture + label carry
 * the distinction). Headline metric labelled per spec §5.0.
 */
export function AqiLegend({
  className,
  orientation = "vertical",
}: {
  className?: string;
  orientation?: "vertical" | "horizontal";
}) {
  return (
    <div className={className}>
      <p className="eyebrow mb-2">PM2.5 sub-index (24h) · CPCB</p>
      <ul
        className={cn(
          "gap-x-4 gap-y-1.5",
          orientation === "vertical" ? "grid" : "flex flex-wrap",
        )}
      >
        {AQI_ORDER.map((cat) => {
          const s = AQI_STYLES[cat];
          return (
            <li key={cat} className="flex items-center gap-2">
              <span
                aria-hidden
                className={cn("pat h-3.5 w-3.5 shrink-0 rounded-[3px]", s.pattern)}
                style={{ backgroundColor: s.color }}
              />
              <span className="text-xs text-ink-soft">{cat}</span>
              <span className="tabular text-[0.68rem] text-ink-dim">{s.indexRange}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
