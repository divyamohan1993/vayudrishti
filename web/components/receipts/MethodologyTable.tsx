import type { AqiBreakpoint } from "@/lib/schemas";
import { AQI_STYLES } from "@/lib/aqi";
import { cn } from "@/lib/cn";

const POLLUTANT_LABEL: Record<string, string> = {
  pm25: "PM2.5",
  pm10: "PM10",
  no2: "NO2",
  so2: "SO2",
  nh3: "NH3",
  o3: "O3",
  co: "CO",
  pb: "Pb",
};

/**
 * CPCB National AQI breakpoint table (spec §5.0). Rendered on /receipts and
 * /about-data from published data (receipts.methodology.aqi_breakpoints), never
 * hardcoded. The Severe band's upper bound is a documented extrapolation.
 */
export function MethodologyTable({
  breakpoints,
  headlineLabel,
  severeNote,
}: {
  breakpoints: AqiBreakpoint[];
  headlineLabel?: string;
  severeNote?: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      {headlineLabel && (
        <p className="text-sm text-ink-soft">
          Headline metric: <span className="font-medium text-ink">{headlineLabel}</span>.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <thead>
            <tr className="border-b" style={{ borderColor: "var(--line)" }}>
              {["Pollutant", "Category", "Concentration", "Sub-index", "Note"].map((h) => (
                <th key={h} className="eyebrow py-2 pr-4 text-left font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {breakpoints.map((b, i) => {
              const s = AQI_STYLES[b.category];
              return (
                <tr key={i} className="border-b" style={{ borderColor: "var(--line)" }}>
                  <td className="py-2 pr-4 font-medium text-ink">{POLLUTANT_LABEL[b.pollutant] ?? b.pollutant}</td>
                  <td className="py-2 pr-4">
                    <span className="inline-flex items-center gap-1.5">
                      <span aria-hidden className={cn("pat h-3 w-3 rounded-[3px]", s.pattern)} style={{ backgroundColor: s.color }} />
                      <span className="text-ink-soft">{b.category}</span>
                    </span>
                  </td>
                  <td className="tabular py-2 pr-4 text-ink-mute">
                    {b.conc_low} to {b.conc_high} {b.unit}
                  </td>
                  <td className="tabular py-2 pr-4 text-ink-mute">
                    {b.index_low} to {b.index_high}
                  </td>
                  <td className="py-2 pr-4 text-xs text-ink-dim">{b.extrapolated ? "extrapolated" : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {severeNote && <p className="text-xs leading-snug text-ink-dim">{severeNote}</p>}
    </div>
  );
}
