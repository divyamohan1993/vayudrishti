"use client";

import { useMemo, useState } from "react";
import type { LedgerWard } from "@/lib/schemas";
import type { WardFC } from "@/lib/geo";
import { featureBounds, geometryToPath, makeProjector } from "@/lib/geo";
import { divergingColor, rgbCss } from "@/lib/aqi";
import { fmtCI, fmtSigned } from "@/lib/format";

/**
 * Per-ward weather-adjusted GRAP effect. Diverging blue<->red (blue = GRAP cut
 * PM2.5). Never colour-only: sign is also carried by hatch direction (reduction
 * = "/", increase = "\") and by the hover readout with its CI.
 */
export function EffectMap({
  fc,
  wards,
  cityName,
}: {
  fc: WardFC;
  wards: LedgerWard[];
  cityName: string;
}) {
  const byId = useMemo(() => {
    const m = new Map<string, LedgerWard>();
    for (const w of wards) m.set(w.ward_id, w);
    return m;
  }, [wards]);
  const maxAbs = useMemo(() => Math.max(1, ...wards.map((w) => Math.abs(w.effect_ugm3))), [wards]);

  const { paths, width, height } = useMemo(() => {
    const b = featureBounds(fc);
    const [minLon, minLat, maxLon, maxLat] = b;
    const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const w = 1000;
    const h = Math.max(300, Math.round((w * (maxLat - minLat)) / ((maxLon - minLon) * kx)));
    const proj = makeProjector(b, w, h, 10);
    return {
      paths: fc.features.map((f) => ({
        id: f.properties.ward_id,
        name: f.properties.name,
        d: geometryToPath(f.geometry, proj),
      })),
      width: w,
      height: h,
    };
  }, [fc]);

  const [hover, setHover] = useState<string | null>(null);
  const focus = hover ? byId.get(hover) : null;
  const focusName = hover ? paths.find((p) => p.id === hover)?.name : null;

  return (
    <div className="flex flex-col gap-3">
      <div
        className="relative min-h-[340px] overflow-hidden rounded-[var(--radius-md)] border"
        style={{ borderColor: "var(--line)", backgroundColor: "var(--color-void)" }}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
          role="img"
          aria-label={`${cityName} per-ward weather-adjusted GRAP effect on PM2.5, diverging scale with sign texture.`}
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <pattern id="eff-reduce" width={7} height={7} patternUnits="userSpaceOnUse">
              <path d="M0 7L7 0" stroke="rgba(244,239,228,0.17)" strokeWidth={0.8} />
            </pattern>
            <pattern id="eff-increase" width={7} height={7} patternUnits="userSpaceOnUse">
              <path d="M0 0L7 7" stroke="rgba(244,239,228,0.17)" strokeWidth={0.8} />
            </pattern>
          </defs>
          {paths.map((p) => {
            const w = byId.get(p.id);
            const sel = p.id === hover;
            const fill = w ? rgbCss(divergingColor(w.effect_ugm3 / maxAbs)) : "var(--color-surface-2)";
            return (
              <g key={p.id}>
                <path
                  d={p.d}
                  fill={fill}
                  stroke={sel ? "var(--color-ink)" : "rgba(8,20,24,0.8)"}
                  strokeWidth={sel ? 2.2 : 0.4}
                  vectorEffect="non-scaling-stroke"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHover(p.id)}
                >
                  <title>{w ? `${p.name}: ${fmtSigned(w.effect_ugm3, 1)} ug/m3` : `${p.name}: no data`}</title>
                </path>
                {w && <path d={p.d} fill={`url(#${w.effect_ugm3 < 0 ? "eff-reduce" : "eff-increase"})`} pointerEvents="none" />}
              </g>
            );
          })}
        </svg>
        {focus && (
          <div
            className="pointer-events-none absolute left-3 top-3 rounded-[var(--radius-sm)] border px-3 py-2 text-xs backdrop-blur"
            style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--color-surface) 80%, transparent)" }}
          >
            <div className="font-medium text-ink">{focusName}</div>
            <div className="tabular" style={{ color: focus.effect_ugm3 < 0 ? "var(--color-div-neg-1)" : "var(--color-div-pos-1)" }}>
              {fmtSigned(focus.effect_ugm3, 1)} µg/m³ {focus.effect_ugm3 < 0 ? "(GRAP cut)" : "(increase)"}
            </div>
            <div className="tabular text-ink-mute">CI {fmtCI(focus.effect_ci_low, focus.effect_ci_high, 1)}</div>
          </div>
        )}
      </div>
      <DivergingLegend maxAbs={maxAbs} />
    </div>
  );
}

function DivergingLegend({ maxAbs }: { maxAbs: number }) {
  const stops = [-1, -0.5, 0, 0.5, 1].map((t) => rgbCss(divergingColor(t)));
  return (
    <div className="text-xs">
      <p className="eyebrow mb-1.5">Weather-adjusted effect · µg/m³ · sign also textured</p>
      <div className="flex items-center gap-2">
        <span className="tabular text-ink-mute">{fmtSigned(-maxAbs, 0)}</span>
        <span className="h-3 flex-1 rounded" style={{ background: `linear-gradient(90deg, ${stops.join(",")})` }} />
        <span className="tabular text-ink-mute">{fmtSigned(maxAbs, 0)}</span>
      </div>
      <div className="mt-1 flex justify-between text-[0.7rem] text-ink-dim">
        <span>GRAP cut PM2.5</span>
        <span>no effect</span>
        <span>increased</span>
      </div>
    </div>
  );
}
