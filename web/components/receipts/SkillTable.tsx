import type { ForecastMetric } from "@/lib/schemas";
import { fmtNum, fmtSigned } from "@/lib/format";

/**
 * Forecast skill per horizon (acceptance 2). skill_pct vs persistence is the
 * committed target (>0 at 24h); 48/72h reported honestly whatever they are,
 * including negative skill.
 */
export function SkillTable({ forecast }: { forecast: Record<string, ForecastMetric> }) {
  const horizons = Object.keys(forecast).sort((a, b) => Number(a) - Number(b));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead>
          <tr className="border-b" style={{ borderColor: "var(--line)" }}>
            {["Horizon", "Ensemble RMSE", "Persistence RMSE", "Skill vs persistence", "Seasonal RMSE", "n", "Embargo"].map((h) => (
              <th key={h} className="eyebrow py-2 pr-4 text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {horizons.map((h) => {
            const m = forecast[h];
            const positive = m.skill_pct > 0;
            return (
              <tr key={h} className="border-b" style={{ borderColor: "var(--line)" }}>
                <td className="py-2.5 pr-4 font-medium text-ink">+{h}h</td>
                <td className="tabular py-2.5 pr-4 text-ink-soft">{fmtNum(m.rmse, 1)}</td>
                <td className="tabular py-2.5 pr-4 text-ink-mute">{fmtNum(m.persistence_rmse, 1)}</td>
                <td className="tabular py-2.5 pr-4 font-semibold" style={{ color: positive ? "var(--color-div-neg-1)" : "var(--color-ember)" }}>
                  {fmtSigned(m.skill_pct, 1)}%
                </td>
                <td className="tabular py-2.5 pr-4 text-ink-mute">{fmtNum(m.seasonal_naive_rmse, 1)}</td>
                <td className="tabular py-2.5 pr-4 text-ink-mute">{fmtNum(m.n, 0)}</td>
                <td className="tabular py-2.5 pr-4 text-ink-mute">{m.embargo_h}h</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
