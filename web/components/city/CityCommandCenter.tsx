"use client";

import { useEffect, useMemo } from "react";
import { useResource } from "@/lib/hooks";
import { useUIStore } from "@/lib/store";
import {
  manifest as manifestSchema,
  nowcast as nowcastSchema,
  forecast as forecastSchema,
  enforcement as enforcementSchema,
  attribution as attributionSchema,
  advisories as advisoriesSchema,
  briefs as briefsSchema,
} from "@/lib/schemas";
import type { ManifestCity, NowcastWard } from "@/lib/schemas";
import { MANIFEST_URL, dataUrl } from "@/lib/paths";
import { AQI_ORDER, AQI_STYLES } from "@/lib/aqi";
import { LANGUAGE_NAMES } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { Panel } from "@/components/ui/Panel";
import { PanelBoundary } from "@/components/ui/PanelBoundary";
import { StatTile } from "@/components/ui/StatTile";
import { AqiChip } from "@/components/ui/AqiChip";
import { Badge } from "@/components/ui/Badge";
import { DataAge } from "@/components/ui/DataAge";
import { SampleDataBanner } from "@/components/ui/SampleDataBanner";
import { StatusNote } from "@/components/ui/StatusNote";
import { LoadingBlock, Skeleton } from "@/components/ui/Skeleton";
import { WardMap } from "@/components/map/WardMap";
import { ForecastTimeline } from "@/components/city/ForecastTimeline";
import { EnforcementQueue } from "@/components/city/EnforcementQueue";
import { ActionBriefs } from "@/components/city/ActionBriefs";
import { AttributionShares } from "@/components/city/AttributionShares";
import { AdvisoryCard } from "@/components/city/AdvisoryCard";

const TIER_META: Record<string, { label: string; tone: "accent" | "neutral" | "outline"; note: string }> = {
  deep: { label: "Deep coverage", tone: "accent", note: "All surfaces, full validation, replay" },
  standard: { label: "Standard", tone: "neutral", note: "Nowcast, forecast, advisories" },
  "config-only": { label: "Config-only", tone: "outline", note: "Pipeline live from one YAML" },
};

function summarise(wards: NowcastWard[]) {
  const counts = new Map<string, number>();
  let worst: NowcastWard | null = null;
  const subs: number[] = [];
  for (const w of wards) {
    counts.set(w.category, (counts.get(w.category) ?? 0) + 1);
    subs.push(w.subindex24h);
    if (!worst || w.subindex24h > worst.subindex24h) worst = w;
  }
  subs.sort((a, b) => a - b);
  const median = subs.length ? subs[Math.floor(subs.length / 2)] : 0;
  const poorPlus = wards.filter((w) => AQI_STYLES[w.category].order >= 3).length;
  return { counts, worst, median, poorPlus, total: wards.length };
}

export function CityCommandCenter({ cityId }: { cityId: string }) {
  const manifestState = useResource(MANIFEST_URL, manifestSchema);
  const city: ManifestCity | undefined =
    manifestState.status === "ready" ? manifestState.data.cities.find((c) => c.id === cityId) : undefined;

  const nowcastState = useResource(city ? dataUrl(city.files.nowcast) : null, nowcastSchema);
  const forecastState = useResource(city ? dataUrl(city.files.forecast) : null, forecastSchema);
  const enforcementState = useResource(city ? dataUrl(city.files.enforcement) : null, enforcementSchema);
  const attributionState = useResource(city ? dataUrl(city.files.attribution) : null, attributionSchema);
  const advisoriesState = useResource(city ? dataUrl(city.files.advisories) : null, advisoriesSchema);
  // Only fetch briefs when the manifest declares the file (avoids a probe 404).
  const briefsUrl = city?.files.briefs ? dataUrl(city.files.briefs) : null;
  const briefsState = useResource(briefsUrl, briefsSchema);

  const resetForCity = useUIStore((s) => s.resetForCity);
  useEffect(() => {
    resetForCity("en");
  }, [cityId, resetForCity]);
  const selectedWardId = useUIStore((s) => s.selectedWardId);

  const cityName = city?.name ?? cityId.charAt(0).toUpperCase() + cityId.slice(1);
  const tier = city ? TIER_META[city.tier] : undefined;

  const nowcastWards = nowcastState.status === "ready" ? nowcastState.data.wards : undefined;
  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const w of nowcastWards ?? []) m.set(w.ward_id, w.name);
    return m;
  }, [nowcastWards]);
  const selectedWardName = selectedWardId ? nameById.get(selectedWardId) : undefined;

  const regional = useMemo(() => {
    if (!city) return undefined;
    const code = city.languages.find((l) => l !== "en" && l !== "hi");
    return code ? { code, name: LANGUAGE_NAMES[code] ?? code } : undefined;
  }, [city]);

  const selAttribution =
    attributionState.status === "ready" && selectedWardId
      ? attributionState.data.wards.find((w) => w.ward_id === selectedWardId)
      : undefined;
  const selAdvisory =
    advisoriesState.status === "ready" && selectedWardId
      ? advisoriesState.data.wards.find((w) => w.ward_id === selectedWardId)
      : undefined;

  const summary = useMemo(() => (nowcastWards ? summarise(nowcastWards) : null), [nowcastWards]);

  if (manifestState.status === "error") {
    return (
      <div className="mx-auto w-full max-w-3xl px-6 py-16">
        <StatusNote tone="error" title="Could not load the city index" message="The manifest is unavailable." />
      </div>
    );
  }
  if (manifestState.status === "ready" && !city) {
    return (
      <div className="mx-auto w-full max-w-3xl px-6 py-16">
        <StatusNote tone="empty" title={`No coverage for "${cityId}" yet`} message="This city is not in the current manifest." />
      </div>
    );
  }

  const isFixture = (nowcastState.status === "ready" && nowcastState.data.fixture) || city?.fixture;
  const generatedAt = nowcastState.status === "ready" ? nowcastState.data.generated_at : city?.generated_at;

  return (
    <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-4 px-4 py-4 sm:px-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-1">Command center</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl sm:text-4xl">{cityName}</h1>
            {tier ? <Badge tone={tier.tone} title={tier.note}>{tier.label}</Badge> : <Skeleton className="h-5 w-24" />}
          </div>
          {tier && <p className="mt-1 text-xs text-ink-mute">{tier.note}</p>}
        </div>
        {generatedAt && <DataAge generatedAt={generatedAt} fixture={isFixture} />}
      </header>

      {isFixture && generatedAt && <SampleDataBanner generatedAt={generatedAt} />}

      <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr] xl:grid-cols-[2fr_1fr]">
        {/* Left: map, forecast, ward insight */}
        <div className="flex min-w-0 flex-col gap-4">
          <PanelBoundary label="Ward map">
            <Panel eyebrow="Ward map" title={`${cityName} air quality`} aria-label={`${cityName} ward map`}>
              <WardMap
                cityName={cityName}
                wardsUrl={city ? dataUrl(city.files.wards) : null}
                wards={nowcastWards}
                forecast={forecastState.status === "ready" ? forecastState.data.wards : undefined}
                wardsLoading={nowcastState.status === "loading"}
              />
            </Panel>
          </PanelBoundary>

          {forecastState.status === "ready" && (
            <PanelBoundary label="Forecast timeline">
              <Panel eyebrow="Forecast" title="24 to 72 hour outlook" aria-label="Forecast timeline">
                <ForecastTimeline
                  nowcast={nowcastWards}
                  forecast={forecastState.data.wards}
                  horizons={forecastState.data.horizons_h}
                  selectedWardName={selectedWardName}
                />
              </Panel>
            </PanelBoundary>
          )}

          {selectedWardId && (selAttribution || selAdvisory) && (
            <PanelBoundary label="Ward insight">
              <Panel eyebrow="Ward drilldown" title={selectedWardName ?? "Selected ward"} aria-label="Ward insight">
                <div className="grid gap-6 md:grid-cols-2">
                  {selAdvisory && (
                    <div>
                      <p className="eyebrow mb-2">Citizen advisory</p>
                      <AdvisoryCard advisory={selAdvisory} regional={regional} />
                    </div>
                  )}
                  {selAttribution && (
                    <div>
                      <p className="eyebrow mb-2">Source mix (labeled estimate)</p>
                      <AttributionShares ward={selAttribution} />
                    </div>
                  )}
                </div>
              </Panel>
            </PanelBoundary>
          )}
        </div>

        {/* Right: headline, enforcement, briefs */}
        <div className="flex min-w-0 flex-col gap-4">
          <PanelBoundary label="City headline">
            <Panel eyebrow="City status" title={`${cityName} right now`} aria-label="City headline">
              {nowcastState.status === "loading" || nowcastState.status === "idle" ? (
                <LoadingBlock lines={4} />
              ) : nowcastState.status === "error" ? (
                <StatusNote tone="error" title="Nowcast unavailable" message={nowcastState.error} />
              ) : summary ? (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-4">
                    <StatTile label="Median ward AQI" value={summary.median} tone="accent" sub="PM2.5 sub-index (24h)" />
                    <StatTile
                      label="Wards poor or worse"
                      value={summary.poorPlus}
                      unit={`/ ${summary.total}`}
                      tone={summary.poorPlus > summary.total / 2 ? "bad" : "neutral"}
                    />
                  </div>
                  {summary.worst && (
                    <div className="rounded-[var(--radius-sm)] border p-3" style={{ borderColor: "var(--line)" }}>
                      <p className="eyebrow mb-1.5">Worst ward now</p>
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm text-ink" title={summary.worst.name}>{summary.worst.name}</span>
                        <AqiChip category={summary.worst.category} value={summary.worst.subindex24h} variant="solid" />
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="eyebrow mb-2">Ward distribution</p>
                    <WardDistribution summary={summary} />
                  </div>
                </div>
              ) : null}
            </Panel>
          </PanelBoundary>

          {enforcementState.status === "ready" && enforcementState.data.ranked.length > 0 && (
            <PanelBoundary label="Enforcement queue">
              <Panel eyebrow="Decision support" title="Enforcement queue" aria-label="Enforcement queue">
                <p className="mb-3 text-xs text-ink-mute">
                  Ranked by measured signals. Source is a confidence-tagged label, not a rank multiplier.
                </p>
                <EnforcementQueue items={enforcementState.data.ranked} nameById={nameById} />
              </Panel>
            </PanelBoundary>
          )}

          {briefsState.status === "ready" && (
            <PanelBoundary label="Action briefs">
              <Panel
                eyebrow="Agentic layer"
                title="Action briefs"
                aria-label="Action briefs"
                actions={briefsState.data.model ? <span className="eyebrow">{briefsState.data.model}</span> : undefined}
              >
                <ActionBriefs briefs={briefsState.data.briefs} stale={briefsState.data.stale} nameById={nameById} />
              </Panel>
            </PanelBoundary>
          )}
        </div>
      </div>
    </div>
  );
}

function WardDistribution({ summary }: { summary: ReturnType<typeof summarise> }) {
  const max = Math.max(1, ...AQI_ORDER.map((c) => summary.counts.get(c) ?? 0));
  return (
    <ul className="flex flex-col gap-1.5">
      {AQI_ORDER.map((cat) => {
        const n = summary.counts.get(cat) ?? 0;
        const s = AQI_STYLES[cat];
        return (
          <li key={cat} className="flex items-center gap-2 text-xs">
            <span className="flex w-28 shrink-0 items-center gap-1.5">
              <span aria-hidden className={cn("pat h-3 w-3 rounded-[3px]", s.pattern)} style={{ backgroundColor: s.color }} />
              <span className="text-ink-soft">{cat}</span>
            </span>
            <span className="relative h-2.5 flex-1 overflow-hidden rounded-full" style={{ background: "var(--color-deep)" }}>
              <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${(n / max) * 100}%`, backgroundColor: s.color, opacity: 0.85 }} />
            </span>
            <span className="tabular w-6 text-right text-ink-mute">{n}</span>
          </li>
        );
      })}
    </ul>
  );
}
