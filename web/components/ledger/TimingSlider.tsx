"use client";

import { useMemo, useState } from "react";
import type { Counterfactual } from "@/lib/schemas";
import { fmtCI, fmtNum } from "@/lib/format";
import { Segmented } from "@/components/ui/Segmented";

/**
 * Counterfactual timing engine: "acting N hours earlier would have saved M more
 * lives" (spec §17). Snaps to the modeled shift points only — no fabricated
 * intermediates.
 */
export function TimingSlider({ counterfactuals }: { counterfactuals: Counterfactual[] }) {
  const points = useMemo(() => {
    const base: Counterfactual = {
      scenario: "as_it_happened",
      shift_hours: 0,
      delta_exposure: 0,
      delta_deaths: 0,
      ci_low: 0,
      ci_high: 0,
    };
    const sorted = [...counterfactuals].sort((a, b) => b.shift_hours - a.shift_hours);
    return [base, ...sorted];
  }, [counterfactuals]);

  const [shift, setShift] = useState<number>(points.length > 1 ? points[1].shift_hours : 0);
  const active = points.find((p) => p.shift_hours === shift) ?? points[0];
  const earlier = Math.abs(active.shift_hours);

  return (
    <div className="flex flex-col gap-4">
      <Segmented
        ariaLabel="Counterfactual intervention timing"
        value={String(shift)}
        onChange={(v) => setShift(Number(v))}
        options={points.map((p) => ({
          value: String(p.shift_hours),
          label: p.shift_hours === 0 ? "As it happened" : `${Math.abs(p.shift_hours)}h earlier`,
        }))}
      />
      {active.shift_hours === 0 ? (
        <div className="rounded-[var(--radius-md)] border p-4 text-sm text-ink-mute" style={{ borderColor: "var(--line)" }}>
          The stage fired on its actual CAQM date. Choose an earlier trigger to model acting sooner.
        </div>
      ) : (
        <div className="rounded-[var(--radius-md)] border p-4" style={{ borderColor: "var(--line)" }} aria-live="polite">
          <p className="text-sm text-ink-soft">
            Acting <span className="font-semibold text-ink">{earlier}h earlier</span> would have saved an estimated
          </p>
          <p className="tabular mt-1 text-3xl font-semibold" style={{ color: "var(--color-div-neg-1)" }}>
            {fmtNum(active.delta_deaths, 0)}
            <span className="ml-1.5 text-sm font-normal text-ink-mute">more lives</span>
          </p>
          <p className="tabular mt-1 text-xs text-ink-mute">95% CI {fmtCI(active.ci_low, active.ci_high, 0)} · modeled estimate (GEMM)</p>
          <p className="tabular mt-2 text-xs text-ink-dim">
            Avoided exposure delta {fmtNum(active.delta_exposure, 0)} person-µg/m³-hours
          </p>
        </div>
      )}
      <p className="text-[0.7rem] text-ink-dim">
        Snaps to modeled scenarios only. Intermediate timings are not interpolated.
      </p>
    </div>
  );
}
