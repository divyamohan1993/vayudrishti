"use client";

import { useMemo } from "react";
import { useResource } from "@/lib/hooks";
import { wardsGeojson as wardsSchema } from "@/lib/schemas";
import type { NowcastWard } from "@/lib/schemas";
import type { WardFC } from "@/lib/geo";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/cn";
import { AqiChip } from "@/components/ui/AqiChip";
import { AqiLegend } from "@/components/ui/AqiLegend";
import { ConfidenceTag } from "@/components/ui/ConfidenceTag";
import { LoadingBlock } from "@/components/ui/Skeleton";
import { StatusNote } from "@/components/ui/StatusNote";
import { StaticChoropleth, type WardDatum } from "./StaticChoropleth";

export function WardMap({
  cityName,
  wardsUrl,
  wards,
  wardsLoading,
}: {
  cityName: string;
  wardsUrl: string | null;
  wards: NowcastWard[] | undefined;
  wardsLoading: boolean;
}) {
  const geo = useResource(wardsUrl, wardsSchema);
  const selectedWard = useUIStore((s) => s.selectedWardId);
  const hoveredWard = useUIStore((s) => s.hoveredWardId);
  const setSelected = useUIStore((s) => s.setSelectedWard);
  const setHovered = useUIStore((s) => s.setHoveredWard);

  const byId = useMemo(() => {
    const m = new Map<string, NowcastWard>();
    for (const w of wards ?? []) m.set(w.ward_id, w);
    return m;
  }, [wards]);

  const datumById = useMemo(() => {
    const m = new Map<string, WardDatum>();
    for (const w of wards ?? [])
      m.set(w.ward_id, { category: w.category, subindex: w.subindex24h, name: w.name });
    return m;
  }, [wards]);

  const options = useMemo(() => {
    if (geo.status !== "ready") return [] as { id: string; name: string }[];
    return geo.data.features
      .map((f) => ({ id: f.properties.ward_id, name: f.properties.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [geo]);

  const focusWard = byId.get(hoveredWard ?? "") ?? byId.get(selectedWard ?? "");

  return (
    <div className="flex flex-col gap-3">
      {/* Control row: accessible ward picker (keyboard + screen reader path) */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-ink-mute">
          <span className="eyebrow">Ward</span>
          <select
            value={selectedWard ?? ""}
            onChange={(e) => setSelected(e.target.value || null)}
            className="max-w-[16rem] rounded-[var(--radius-sm)] border bg-[var(--color-deep)] px-2 py-1.5 text-sm text-ink"
            style={{ borderColor: "var(--line)" }}
            aria-label={`Select a ${cityName} ward`}
          >
            <option value="">All wards</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
        {selectedWard && (
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="rounded-[var(--radius-sm)] border px-2 py-1 text-xs text-ink-mute hover:text-ink"
            style={{ borderColor: "var(--line)" }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Map surface */}
      <div
        className="relative min-h-[380px] flex-1 overflow-hidden rounded-[var(--radius-md)] border lg:min-h-[520px]"
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
            <StaticChoropleth
              fc={geo.data as unknown as WardFC}
              data={datumById}
              selectedWard={selectedWard}
              onSelect={setSelected}
              onHover={setHovered}
              cityName={cityName}
            />
            {/* Live ward readout */}
            <div
              className="pointer-events-none absolute left-3 top-3 max-w-[15rem] rounded-[var(--radius-sm)] border px-3 py-2 text-xs backdrop-blur"
              style={{
                borderColor: "var(--line)",
                background: "color-mix(in oklab, var(--color-surface) 78%, transparent)",
              }}
              aria-live="polite"
            >
              {focusWard ? (
                <div className="flex flex-col gap-1.5">
                  <span className="truncate font-medium text-ink" title={focusWard.name}>
                    {focusWard.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <AqiChip category={focusWard.category} value={focusWard.subindex24h} variant="solid" />
                    <ConfidenceTag level={focusWard.confidence} showLabel={false} />
                  </div>
                  <span className="tabular text-[0.7rem] text-ink-mute">
                    PM2.5 p50 {Math.round(focusWard.pm25_p50)} · p90 {Math.round(focusWard.pm25_p90)} ug/m3
                  </span>
                </div>
              ) : (
                <span className="text-ink-mute">Hover or pick a ward</span>
              )}
            </div>
            {/* Legend */}
            <div
              className="absolute bottom-3 left-3 rounded-[var(--radius-sm)] border px-3 py-2 backdrop-blur"
              style={{
                borderColor: "var(--line)",
                background: "color-mix(in oklab, var(--color-surface) 78%, transparent)",
              }}
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
