"use client";

import { useMemo } from "react";
import type { CvBucket } from "@/lib/schemas";

const W = 540;
const H = 250;
const M = { l: 46, r: 14, t: 16, b: 42 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;

/**
 * Stratified LOSO cross-validation curve (acceptance 3): ensemble RMSE vs the
 * IDW baseline across distance-to-nearest-station buckets. Two series -> legend
 * + direct labels; the shaded gap is the improvement.
 */
export function LosoCurve({ buckets, baseline }: { buckets: CvBucket[]; baseline: string }) {
  const g = useMemo(() => {
    const pts = [...buckets].sort((a, b) => a.dist_km - b.dist_km);
    const xMin = Math.min(...pts.map((p) => p.dist_km));
    const xMax = Math.max(...pts.map((p) => p.dist_km));
    const yMax = Math.max(...pts.flatMap((p) => [p.model_rmse, p.idw_rmse])) * 1.12 || 1;
    const xOf = (v: number) => M.l + ((v - xMin) / (xMax - xMin || 1)) * PW;
    const yOf = (v: number) => M.t + PH - (v / yMax) * PH;
    const line = (pick: (p: CvBucket) => number) =>
      pts.map((p, i) => `${i ? "L" : "M"}${xOf(p.dist_km).toFixed(1)} ${yOf(pick(p)).toFixed(1)}`).join("");
    const area =
      pts.map((p, i) => `${i ? "L" : "M"}${xOf(p.dist_km).toFixed(1)} ${yOf(p.idw_rmse).toFixed(1)}`).join("") +
      pts.map((_, ri) => {
        const i = pts.length - 1 - ri;
        return `L${xOf(pts[i].dist_km).toFixed(1)} ${yOf(pts[i].model_rmse).toFixed(1)}`;
      }).join("") +
      "Z";
    return { pts, yMax, xOf, yOf, modelLine: line((p) => p.model_rmse), idwLine: line((p) => p.idw_rmse), area };
  }, [buckets]);

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Ensemble RMSE versus ${baseline} baseline by distance to nearest station`}>
        {[0, g.yMax / 2, g.yMax].map((v, i) => (
          <g key={i}>
            <line x1={M.l} x2={W - M.r} y1={g.yOf(v)} y2={g.yOf(v)} stroke="var(--line)" strokeWidth={1} />
            <text x={M.l - 6} y={g.yOf(v) + 3} textAnchor="end" fontSize={10} fill="var(--color-ink-dim)" className="tabular">
              {Math.round(v)}
            </text>
          </g>
        ))}
        <path d={g.area} fill="var(--color-airglow)" opacity={0.12} />
        <path d={g.idwLine} fill="none" stroke="var(--color-ink-dim)" strokeWidth={1.6} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
        <path d={g.modelLine} fill="none" stroke="var(--color-airglow)" strokeWidth={2.2} vectorEffect="non-scaling-stroke" />
        {g.pts.map((p) => (
          <g key={p.dist_km}>
            <circle cx={g.xOf(p.dist_km)} cy={g.yOf(p.idw_rmse)} r={2.6} fill="var(--color-ink-dim)" />
            <circle cx={g.xOf(p.dist_km)} cy={g.yOf(p.model_rmse)} r={3.2} fill="var(--color-airglow)" />
            <text x={g.xOf(p.dist_km)} y={H - M.b + 15} textAnchor="middle" fontSize={10} fill="var(--color-ink-dim)" className="tabular">
              {p.dist_km}
            </text>
          </g>
        ))}
        <text x={13} y={M.t + PH / 2} fontSize={10} fill="var(--color-ink-mute)" transform={`rotate(-90 13 ${M.t + PH / 2})`} textAnchor="middle">
          RMSE µg/m³
        </text>
        <text x={M.l + PW / 2} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--color-ink-mute)">
          km to nearest retained station
        </text>
      </svg>
      <figcaption className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-mute">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-[2px] w-4" style={{ background: "var(--color-airglow)" }} />
          Ensemble
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-[2px] w-4" style={{ background: "var(--color-ink-dim)", borderTop: "1px dashed" }} />
          {baseline} baseline
        </span>
      </figcaption>
    </figure>
  );
}
