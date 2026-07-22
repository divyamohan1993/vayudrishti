import type { StageEffect } from "@/lib/schemas";
import { fmtCI, fmtNum } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";

function verdict(e: StageEffect) {
  const straddlesZero = e.ci_low <= 0 && e.ci_high >= 0;
  return { detectable: !straddlesZero && e.placebo_pass, straddlesZero };
}

/**
 * Event-study results per GRAP transition on the weather-normalized series.
 * Honesty-by-design: a stage whose CI spans zero, or that fails its placebo
 * test, is published as a "no detectable effect" accountability finding.
 */
export function StageEffects({ effects }: { effects: StageEffect[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {effects.map((e, i) => {
        const { detectable, straddlesZero } = verdict(e);
        const reduced = e.effect_ugm3 < 0;
        return (
          <div key={i} className="rounded-[var(--radius-md)] border p-3.5" style={{ borderColor: "var(--line)" }}>
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-ink">{e.stage_transition}</p>
              <Badge tone={e.placebo_pass ? "good" : "warn"}>
                {e.placebo_pass ? "placebo passed" : "placebo failed"}
              </Badge>
            </div>
            {detectable ? (
              <p
                className="tabular mt-2 text-lg font-semibold"
                style={{ color: reduced ? "var(--color-div-neg-1)" : "var(--color-div-pos-1)" }}
              >
                {reduced ? "cut" : "raised"} PM2.5 by {fmtNum(Math.abs(e.effect_ugm3), 1)}
                <span className="ml-1 text-xs font-normal text-ink-mute">µg/m³</span>
              </p>
            ) : (
              <p className="mt-2 text-base font-semibold text-ember">No detectable effect</p>
            )}
            <p className="tabular mt-1 text-xs text-ink-mute">
              95% CI {fmtCI(e.ci_low, e.ci_high, 1)} µg/m³ · n = {e.n_days} days
            </p>
            {!detectable && (
              <p className="mt-1.5 text-[0.72rem] leading-snug text-ink-dim">
                Accountability finding: the confidence interval spans zero
                {!e.placebo_pass ? " and the placebo test failed" : ""}. Published, not hidden.
              </p>
            )}
            <p className="mt-2 text-[0.72rem] leading-snug text-ink-dim">{e.method_notes}</p>
          </div>
        );
      })}
    </div>
  );
}
