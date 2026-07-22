"use client";

import { useMemo } from "react";
import type { AqiCategory } from "@/lib/schemas";
import { AQI_ORDER, AQI_RGB, rgbCss } from "@/lib/aqi";
import { cn } from "@/lib/cn";
import {
  featureBounds,
  geometryToPath,
  makeProjector,
  type WardFC,
} from "@/lib/geo";

export interface WardDatum {
  category: AqiCategory;
  subindex: number;
  name: string;
}

const DARK = "rgba(5,11,13,0.44)";

/** SVG texture defs (colour + distinct motif) — mirrors the CSS AQI patterns. */
function PatternDefs() {
  const motif = (cat: AqiCategory) => {
    const fill = rgbCss(AQI_RGB[cat]);
    switch (cat) {
      case "Good":
        return <path d="M0 4h8" stroke={DARK} strokeWidth={1.1} />;
      case "Satisfactory":
        return <circle cx={4} cy={4} r={1.1} fill={DARK} />;
      case "Moderate":
        return <path d="M0 8L8 0" stroke={DARK} strokeWidth={1.1} />;
      case "Poor":
        return (
          <>
            <path d="M0 8L8 0" stroke={DARK} strokeWidth={1} />
            <path d="M0 0L8 8" stroke={DARK} strokeWidth={1} />
          </>
        );
      case "Very Poor":
        return <path d="M0 0L8 8" stroke={DARK} strokeWidth={1.8} />;
      case "Severe":
        return (
          <>
            <path d="M4 0v8" stroke={DARK} strokeWidth={1.2} />
            <path d="M0 4h8" stroke={DARK} strokeWidth={1.2} />
          </>
        );
    }
    return (fill && null) as never;
  };
  return (
    <defs>
      {AQI_ORDER.map((cat) => (
        <pattern
          key={cat}
          id={`aqi-${cat.replace(/\s+/g, "")}`}
          width={8}
          height={8}
          patternUnits="userSpaceOnUse"
        >
          <rect width={8} height={8} fill={rgbCss(AQI_RGB[cat])} />
          {motif(cat)}
        </pattern>
      ))}
    </defs>
  );
}

/**
 * Accessible, dependency-free ward choropleth (spec acceptance 6 fallback + the
 * colour-blind-safe patterned view). Textured fills so category is never carried
 * by colour alone. Keyboard/SR selection is handled by the ward picker; this SVG
 * is the visual layer with per-ward titles and pointer selection.
 */
export function StaticChoropleth({
  fc,
  roads,
  data,
  selectedWard,
  onSelect,
  onHover,
  className,
  cityName,
}: {
  fc: WardFC;
  roads?: WardFC;
  data: Map<string, WardDatum>;
  selectedWard: string | null;
  onSelect: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  className?: string;
  cityName: string;
}) {
  const { paths, roadDs, width, height } = useMemo(() => {
    const bounds = featureBounds(fc);
    const [minLon, minLat, maxLon, maxLat] = bounds;
    const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const w = 1000;
    const h = Math.max(
      300,
      Math.round((w * (maxLat - minLat)) / ((maxLon - minLon) * kx)),
    );
    const proj = makeProjector(bounds, w, h, 10);
    const paths = fc.features.map((f) => ({
      id: f.properties.ward_id,
      name: f.properties.name,
      d: geometryToPath(f.geometry, proj),
    }));
    const roadDs = (roads?.features ?? [])
      .map((f) => geometryToPath(f.geometry, proj))
      .filter(Boolean);
    return { paths, roadDs, width: w, height: h };
  }, [fc, roads]);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className={cn("h-full w-full", className)}
      role="img"
      aria-label={`${cityName} ward choropleth, coloured and textured by PM2.5 sub-index category. Use the ward selector to inspect a ward.`}
      onMouseLeave={() => onHover?.(null)}
    >
      <PatternDefs />
      <g>
        {paths.map((p) => {
          const d = data.get(p.id);
          const selected = p.id === selectedWard;
          const fill = d ? `url(#aqi-${d.category.replace(/\s+/g, "")})` : "var(--color-surface-2)";
          return (
            <path
              key={p.id}
              d={p.d}
              fill={fill}
              stroke={selected ? "var(--color-airglow)" : "rgba(8,20,24,0.85)"}
              strokeWidth={selected ? 2.4 : 0.5}
              vectorEffect="non-scaling-stroke"
              style={{ cursor: "pointer", transition: "stroke-width 120ms" }}
              onClick={() => onSelect(selected ? null : p.id)}
              onMouseEnter={() => onHover?.(p.id)}
            >
              <title>
                {d ? `${p.name}: ${d.category}, AQI ${d.subindex}` : `${p.name}: no data`}
              </title>
            </path>
          );
        })}
      </g>
      {roadDs.length > 0 && (
        <g aria-hidden pointerEvents="none">
          {roadDs.map((d, i) => (
            <path key={i} d={d} fill="none" stroke="rgba(244,239,228,0.5)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
          ))}
        </g>
      )}
    </svg>
  );
}
