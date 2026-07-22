"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useResource, useWebGL2 } from "@/lib/hooks";
import { roadsGeojson as roadsSchema, wardsGeojson as wardsSchema } from "@/lib/schemas";
import type { ForecastWard, NowcastWard } from "@/lib/schemas";
import type { WardFC } from "@/lib/geo";
import { buildWardView } from "@/lib/wardView";
import { useUIStore, type SatelliteLayer } from "@/lib/store";
import { AqiChip } from "@/components/ui/AqiChip";
import { AqiLegend } from "@/components/ui/AqiLegend";
import { ConfidenceTag } from "@/components/ui/ConfidenceTag";
import { Segmented } from "@/components/ui/Segmented";
import { LoadingBlock } from "@/components/ui/Skeleton";
import { StatusNote } from "@/components/ui/StatusNote";
import { StaticChoropleth, type WardDatum } from "./StaticChoropleth";

const MapCanvas = dynamic(() => import("./MapCanvas"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center">
      <LoadingBlock label="Loading interactive map" lines={3} className="w-56" />
    </div>
  ),
});

const GIBS_OPTIONS: { value: SatelliteLayer; label: string }[] = [
  { value: "off", label: "None" },
  { value: "no2", label: "NO2" },
  { value: "aod", label: "AOD" },
  { value: "viirs", label: "VIIRS" },
];

export function WardMap({
  cityName,
  wardsUrl,
  roadsUrl,
  bbox,
  wards,
  forecast,
  wardsLoading,
}: {
  cityName: string;
  wardsUrl: string | null;
  roadsUrl?: string | null;
  bbox?: [number, number, number, number];
  wards: NowcastWard[] | undefined;
  forecast?: ForecastWard[];
  wardsLoading: boolean;
}) {
  const geo = useResource(wardsUrl, wardsSchema);
  const roads = useResource(roadsUrl ?? null, roadsSchema);
  const webgl2 = useWebGL2();

  const selectedWard = useUIStore((s) => s.selectedWardId);
  const hoveredWard = useUIStore((s) => s.hoveredWardId);
  const timelineH = useUIStore((s) => s.timelineH);
  const satellite = useUIStore((s) => s.satellite);
  const setSelected = useUIStore((s) => s.setSelectedWard);
  const setHovered = useUIStore((s) => s.setHoveredWard);
  const setSatellite = useUIStore((s) => s.setSatellite);

  // Default to the textured patterns view: it encodes AQI category with texture +
  // label (never colour-only, spec §7). The WebGL map + GIBS is a one-click,
  // opt-in enhancement.
  const [view, setView] = useState<"map" | "patterns">("patterns");
  const useMap = view === "map" && webgl2 === true;

  const viewById = useMemo(() => buildWardView(wards, forecast, timelineH), [wards, forecast, timelineH]);
  const datumById = useMemo(() => {
    const m = new Map<string, WardDatum>();
    for (const v of viewById.values()) m.set(v.ward_id, { category: v.category, subindex: v.subindex, name: v.name });
    return m;
  }, [viewById]);

  const options = useMemo(() => {
    if (geo.status !== "ready") return [] as { id: string; name: string }[];
    return geo.data.features
      .map((f) => ({ id: f.properties.ward_id, name: f.properties.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [geo]);

  const focus = viewById.get(hoveredWard ?? "") ?? viewById.get(selectedWard ?? "");
  const horizonLabel = timelineH === 0 ? "now" : `+${timelineH}h forecast`;
  const roadsFC = roads.status === "ready" ? (roads.data as unknown as WardFC) : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-ink-mute">
          <span className="eyebrow">Ward</span>
          <select
            value={selectedWard ?? ""}
            onChange={(e) => setSelected(e.target.value || null)}
            className="max-w-[13rem] rounded-[var(--radius-sm)] border bg-[var(--color-deep)] px-2 py-1.5 text-sm text-ink"
            style={{ borderColor: "var(--line)" }}
            aria-label={`Select a ${cityName} ward`}
          >
            <option value="">All wards</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </label>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Segmented
            ariaLabel="Map view"
            size="sm"
            value={view}
            onChange={(v) => setView(v as "map" | "patterns")}
            options={[
              { value: "map", label: "Map", disabled: webgl2 === false },
              { value: "patterns", label: "Patterns" },
            ]}
          />
          {useMap && (
            <Segmented
              ariaLabel="Satellite overlay"
              size="sm"
              value={satellite}
              onChange={(v) => setSatellite(v as SatelliteLayer)}
              options={GIBS_OPTIONS}
            />
          )}
        </div>
      </div>

      <div
        className="relative h-[440px] overflow-hidden rounded-[var(--radius-md)] border lg:h-[600px]"
        style={{ borderColor: "var(--line)", backgroundColor: "var(--color-void)" }}
      >
        {geo.status === "loading" || (geo.status === "idle" && wardsLoading) ? (
          <div className="grid h-full place-items-center p-8">
            <LoadingBlock label="Loading ward map" lines={3} className="w-56" />
          </div>
        ) : geo.status === "error" ? (
          <div className="grid h-full place-items-center p-6">
            <StatusNote tone="error" title="Ward map unavailable" message={geo.error} />
          </div>
        ) : geo.status === "ready" ? (
          <>
            {useMap && bbox ? (
              <MapCanvas
                fc={geo.data as unknown as WardFC}
                roads={roadsFC}
                viewById={viewById}
                bbox={bbox}
                satellite={satellite}
                selectedWard={selectedWard}
                onHover={setHovered}
                onSelect={setSelected}
              />
            ) : (
              <StaticChoropleth
                fc={geo.data as unknown as WardFC}
                roads={roadsFC}
                data={datumById}
                selectedWard={selectedWard}
                onSelect={setSelected}
                onHover={setHovered}
                cityName={cityName}
              />
            )}

            <div
              className="pointer-events-none absolute left-3 top-3 max-w-[15rem] rounded-[var(--radius-sm)] border px-3 py-2 text-xs backdrop-blur"
              style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--color-surface) 78%, transparent)" }}
              aria-live="polite"
            >
              {focus ? (
                <div className="flex flex-col gap-1.5">
                  <span className="truncate font-medium text-ink" title={focus.name}>{focus.name}</span>
                  <div className="flex items-center gap-2">
                    <AqiChip category={focus.category} value={focus.subindex} variant="solid" />
                    <ConfidenceTag level={focus.confidence} showLabel={false} />
                  </div>
                  <span className="tabular text-[0.7rem] text-ink-mute">
                    {horizonLabel} · p50 {Math.round(focus.pm25_p50)} · p90 {Math.round(focus.pm25_p90)} ug/m3
                  </span>
                </div>
              ) : (
                <span className="text-ink-mute">Showing {horizonLabel}. {useMap ? "Click" : "Hover or pick"} a ward.</span>
              )}
            </div>

            <div
              className="absolute bottom-3 left-3 rounded-[var(--radius-sm)] border px-3 py-2 backdrop-blur"
              style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--color-surface) 82%, transparent)" }}
            >
              <AqiLegend orientation="horizontal" />
            </div>
          </>
        ) : (
          <div className="grid h-full place-items-center p-6">
            <StatusNote tone="empty" title="No ward geometry" message="This city has no published ward map." />
          </div>
        )}
      </div>
    </div>
  );
}
