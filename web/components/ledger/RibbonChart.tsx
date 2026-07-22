"use client";

import { useMemo, useRef, useState } from "react";
import type { GrapCalendarEntry, RibbonPoint } from "@/lib/schemas";
import { formatISTDate } from "@/lib/format";
import { stageShort } from "@/lib/i18n";

const W = 880;
const H = 320;
const M = { l: 48, r: 16, t: 20, b: 46 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;
const STAGES = ["GRAP-I", "GRAP-II", "GRAP-III", "GRAP-IV"];

/**
 * Hero chart: raw vs weather-normalized PM2.5 over the GRAP window. The
 * normalized line (Grange & Carslaw deweathering) is the policy signal; the gap
 * to raw is the weather contribution. Single y-axis (same unit), honest p90
 * envelope, GRAP stage bands annotated (dates cite CAQM orders in the list
 * below). Crosshair hover per dataviz guidance.
 */
export function RibbonChart({
  series,
  calendar,
}: {
  series: RibbonPoint[];
  calendar: GrapCalendarEntry[];
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const g = useMemo(() => {
    const times = series.map((s) => new Date(s.ts_utc).getTime());
    const t0 = Math.min(...times);
    const t1 = Math.max(...times);
    const yMax =
      Math.max(...series.map((s) => Math.max(s.pm25_raw, s.pm25_normalized, s.pm25_normalized_p90 ?? 0))) * 1.06 || 1;
    const xOf = (t: number) => M.l + ((t - t0) / (t1 - t0 || 1)) * PW;
    const yOf = (v: number) => M.t + PH - (v / yMax) * PH;
    const xi = (i: number) => xOf(times[i]);
    const line = (pick: (s: RibbonPoint) => number) =>
      series.map((s, i) => `${i ? "L" : "M"}${xi(i).toFixed(1)} ${yOf(pick(s)).toFixed(1)}`).join("");
    const areaBetween = (top: (s: RibbonPoint) => number, bot: (s: RibbonPoint) => number) => {
      const up = series.map((s, i) => `${i ? "L" : "M"}${xi(i).toFixed(1)} ${yOf(top(s)).toFixed(1)}`).join("");
      const down = series
        .map((_, ri) => {
          const i = series.length - 1 - ri;
          return `L${xi(i).toFixed(1)} ${yOf(bot(series[i])).toFixed(1)}`;
        })
        .join("");
      return `${up}${down}Z`;
    };
    const hasP90 = series.every((s) => s.pm25_normalized_p90 != null);
    const bands = calendar
      .map((c) => {
        const s = new Date(c.start_utc).getTime();
        const e = c.end_utc ? new Date(c.end_utc).getTime() : t1;
        const x1 = Math.max(M.l, xOf(s));
        const x2 = Math.min(M.l + PW, xOf(e));
        return { stage: c.stage, x1, w: Math.max(0, x2 - x1) };
      })
      .filter((b) => b.w > 0);
    const yTicks = [0, yMax / 2, yMax].map((v) => ({ v, y: yOf(v) }));
    const xTicks = Array.from({ length: 5 }, (_, k) => {
      const t = t0 + ((t1 - t0) * k) / 4;
      return { t, x: xOf(t) };
    });
    return {
      times,
      xi,
      yOf,
      xOf,
      rawLine: line((s) => s.pm25_raw),
      normLine: line((s) => s.pm25_normalized),
      p90Area: hasP90 ? areaBetween((s) => s.pm25_normalized_p90 as number, (s) => s.pm25_normalized) : "",
      weatherArea: areaBetween((s) => s.pm25_raw, (s) => s.pm25_normalized),
      bands,
      yTicks,
      xTicks,
    };
  }, [series, calendar]);

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) * (W / r.width);
    let best = 0;
    let bd = Infinity;
    g.times.forEach((t, i) => {
      const d = Math.abs(g.xOf(t) - px);
      if (d < bd) {
        bd = d;
        best = i;
      }
    });
    setHover(best);
  }

  const hp = hover != null ? series[hover] : null;
  const hx = hover != null ? g.xi(hover) : 0;

  return (
    <figure className="m-0">
      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Raw versus weather-normalized PM2.5 over the GRAP window, with stage bands and a p90 envelope."
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {g.yTicks.map((t, i) => (
            <g key={i}>
              <line x1={M.l} x2={W - M.r} y1={t.y} y2={t.y} stroke="var(--line)" strokeWidth={1} />
              <text x={M.l - 6} y={t.y + 3} textAnchor="end" fontSize={10} fill="var(--color-ink-dim)" className="tabular">
                {Math.round(t.v)}
              </text>
            </g>
          ))}
          {g.bands.map((b, i) => (
            <g key={i}>
              <rect x={b.x1} y={M.t} width={b.w} height={PH} fill="var(--color-cov-2)" opacity={0.09 + 0.035 * STAGES.indexOf(b.stage)} />
              <line x1={b.x1} x2={b.x1} y1={M.t} y2={M.t + PH} stroke="var(--color-cov-3)" strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
              <text x={b.x1 + 4} y={M.t + 11} fontSize={9} fill="var(--color-cov-4)" className="tabular">
                {stageShort(b.stage)}
              </text>
            </g>
          ))}
          {g.p90Area && <path d={g.p90Area} fill="var(--color-airglow)" opacity={0.1} />}
          <path d={g.weatherArea} fill="var(--color-ink-mute)" opacity={0.1} />
          <path d={g.rawLine} fill="none" stroke="var(--color-ink-dim)" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
          <path d={g.normLine} fill="none" stroke="var(--color-airglow)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          {g.xTicks.map((t, i) => (
            <text key={i} x={t.x} y={H - M.b + 16} textAnchor="middle" fontSize={10} fill="var(--color-ink-dim)">
              {formatISTDate(new Date(t.t).toISOString()).replace(/ \d{4}$/, "")}
            </text>
          ))}
          <text x={13} y={M.t + PH / 2} fontSize={10} fill="var(--color-ink-mute)" transform={`rotate(-90 13 ${M.t + PH / 2})`} textAnchor="middle">
            PM2.5 µg/m³
          </text>
          {hp && (
            <g>
              <line x1={hx} x2={hx} y1={M.t} y2={M.t + PH} stroke="var(--color-ink-mute)" strokeWidth={1} strokeDasharray="2 2" />
              <circle cx={hx} cy={g.yOf(hp.pm25_raw)} r={3} fill="var(--color-ink-dim)" />
              <circle cx={hx} cy={g.yOf(hp.pm25_normalized)} r={3.5} fill="var(--color-airglow)" />
            </g>
          )}
        </svg>
        {hp && (
          <div
            className="pointer-events-none absolute right-2 top-2 rounded-md border px-2.5 py-1.5 text-xs backdrop-blur"
            style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--color-surface) 84%, transparent)" }}
          >
            <div className="tabular text-ink-soft">{formatISTDate(hp.ts_utc)}</div>
            <div className="tabular text-airglow">normalized {Math.round(hp.pm25_normalized)}</div>
            <div className="tabular text-ink-mute">raw {Math.round(hp.pm25_raw)}</div>
          </div>
        )}
      </div>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-mute">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-[2px] w-4" style={{ background: "var(--color-airglow)" }} />
          Weather-normalized (policy signal)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-[2px] w-4" style={{ background: "var(--color-ink-dim)" }} />
          Raw observed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--color-airglow)", opacity: 0.25 }} />
          p90 band
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--color-cov-2)", opacity: 0.35 }} />
          GRAP stage active
        </span>
      </figcaption>
    </figure>
  );
}
