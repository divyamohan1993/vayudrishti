"use client";

import { useMemo } from "react";
import type { ForecastWard, NowcastWard } from "@/lib/schemas";
import { useUIStore, type TimelineH } from "@/lib/store";
import { buildWardView, type WardView } from "@/lib/wardView";
import { AQI_RGB, categoryForIndex, rgbCss } from "@/lib/aqi";
import type { AqiCategory } from "@/lib/schemas";
import { AqiChip } from "@/components/ui/AqiChip";
import { ConfidenceTag } from "@/components/ui/ConfidenceTag";
import { Segmented } from "@/components/ui/Segmented";

interface TrajPoint {
  h: TimelineH;
  subindex: number;
  p50: number;
  p90: number;
  category: AqiCategory;
  confidence: WardView["confidence"] | null;
}

function median(nums: number[]): number {
  if (!nums.length) return 0;
  const a = [...nums].sort((x, y) => x - y);
  return a[Math.floor(a.length / 2)];
}

function trajAt(
  nowcast: NowcastWard[] | undefined,
  forecast: ForecastWard[] | undefined,
  h: TimelineH,
  wardId: string | null,
): TrajPoint {
  const view = buildWardView(nowcast, forecast, h);
  if (wardId && view.get(wardId)) {
    const v = view.get(wardId)!;
    return { h, subindex: v.subindex, p50: v.pm25_p50, p90: v.pm25_p90, category: v.category, confidence: v.confidence };
  }
  const vals = [...view.values()];
  const subindex = median(vals.map((v) => v.subindex));
  return {
    h,
    subindex,
    p50: median(vals.map((v) => v.pm25_p50)),
    p90: median(vals.map((v) => v.pm25_p90)),
    category: categoryForIndex(subindex) ?? "Moderate",
    confidence: null,
  };
}

export function ForecastTimeline({
  nowcast,
  forecast,
  horizons,
  selectedWardName,
}: {
  nowcast: NowcastWard[] | undefined;
  forecast: ForecastWard[] | undefined;
  horizons: number[];
  selectedWardName?: string;
}) {
  const timelineH = useUIStore((s) => s.timelineH);
  const setTimelineH = useUIStore((s) => s.setTimelineH);
  const selectedWard = useUIStore((s) => s.selectedWardId);

  const steps = useMemo<TimelineH[]>(() => {
    const hs = ([24, 48, 72] as TimelineH[]).filter((h) => horizons.includes(h));
    return [0, ...hs];
  }, [horizons]);

  const traj = useMemo(
    () => steps.map((h) => trajAt(nowcast, forecast, h, selectedWard)),
    [steps, nowcast, forecast, selectedWard],
  );

  const active = traj.find((t) => t.h === timelineH) ?? traj[0];
  const scope = selectedWard && selectedWardName ? selectedWardName : "City median";

  // sparkline geometry
  const W = 100, H = 42, pad = 3;
  const ys = traj.flatMap((t) => [t.p50, t.p90]);
  const min = Math.min(...ys) * 0.9;
  const max = Math.max(...ys) * 1.08 || 1;
  const x = (i: number) => pad + (i * (W - 2 * pad)) / Math.max(1, steps.length - 1);
  const y = (v: number) => H - pad - ((v - min) / (max - min || 1)) * (H - 2 * pad);
  const p50Line = traj.map((t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(t.p50).toFixed(1)}`).join("");
  const ribbon =
    traj.map((t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(t.p90).toFixed(1)}`).join("") +
    traj.map((t, i) => `L${x(traj.length - 1 - i).toFixed(1)} ${y(traj[traj.length - 1 - i].p50).toFixed(1)}`).join("") +
    "Z";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          ariaLabel="Forecast horizon"
          value={String(timelineH)}
          onChange={(v) => setTimelineH(Number(v) as TimelineH)}
          options={steps.map((h) => ({ value: String(h), label: h === 0 ? "Now" : `+${h}h` }))}
        />
        <div className="flex items-center gap-2">
          <AqiChip category={active.category} value={active.subindex} variant="solid" />
          {active.confidence && <ConfidenceTag level={active.confidence} showLabel={false} />}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-14 flex-1" preserveAspectRatio="none" aria-hidden>
          <path d={ribbon} fill="var(--color-airglow)" opacity={0.14} />
          <path d={p50Line} fill="none" stroke="var(--color-airglow)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" />
          {traj.map((t, i) => (
            <circle
              key={t.h}
              cx={x(i)}
              cy={y(t.p50)}
              r={t.h === timelineH ? 2.6 : 1.7}
              fill={rgbCss(AQI_RGB[t.category])}
              stroke={t.h === timelineH ? "var(--color-ink)" : "var(--color-void)"}
              strokeWidth={0.7}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
        <dl className="w-32 shrink-0 text-xs">
          <dt className="eyebrow">{scope}</dt>
          <dd className="tabular mt-1 text-ink">
            PM2.5 {Math.round(active.p50)}
            <span className="text-ink-mute"> ({Math.round(active.p90)} p90)</span>
          </dd>
        </dl>
      </div>

      <p className="text-[0.7rem] leading-snug text-ink-dim">
        Ward-level forecast. &ldquo;Now&rdquo; is the nowcast value; the forecast series begins at +24h
        (seam per method). Bands are p50 with the p90 envelope.
      </p>
    </div>
  );
}
