"use client";

import { useMemo } from "react";
import { useResource } from "@/lib/hooks";
import { manifest as manifestSchema, nowcast as nowcastSchema } from "@/lib/schemas";
import type { ManifestCity, NowcastWard } from "@/lib/schemas";
import { MANIFEST_URL, dataUrl } from "@/lib/paths";
import { AQI_ORDER, AQI_STYLES } from "@/lib/aqi";
import { cn } from "@/lib/cn";
import { Panel } from "@/components/ui/Panel";
import { StatTile } from "@/components/ui/StatTile";
import { AqiChip } from "@/components/ui/AqiChip";
import { AqiLegend } from "@/components/ui/AqiLegend";
import { Badge } from "@/components/ui/Badge";
import { DataAge } from "@/components/ui/DataAge";
import { SampleDataBanner } from "@/components/ui/SampleDataBanner";
import { StatusNote } from "@/components/ui/StatusNote";
import { LoadingBlock, Skeleton } from "@/components/ui/Skeleton";
import { PanelBoundary } from "@/components/ui/PanelBoundary";
import { WardMap } from "@/components/map/WardMap";

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
    manifestState.status === "ready"
      ? manifestState.data.cities.find((c) => c.id === cityId)
      : undefined;

  const nowcastUrl = city ? dataUrl(city.files.nowcast) : null;
  const nowcastState = useResource(nowcastUrl, nowcastSchema);
  const wardsUrl = city ? dataUrl(city.files.wards) : null;

  const cityName = city?.name ?? cityId.charAt(0).toUpperCase() + cityId.slice(1);
  const tier = city ? TIER_META[city.tier] : undefined;

  const summary = useMemo(
    () => (nowcastState.status === "ready" ? summarise(nowcastState.data.wards) : null),
    [nowcastState],
  );

  if (manifestState.status === "error") {
    return (
      <div className="mx-auto w-full max-w-3xl px-6 py-16">
        <StatusNote
          tone="error"
          title="Could not load the city index"
          message="The manifest is unavailable. Check your connection and retry."
        />
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

  const isFixture =
    (nowcastState.status === "ready" && nowcastState.data.fixture) || city?.fixture;
  const generatedAt =
    nowcastState.status === "ready" ? nowcastState.data.generated_at : city?.generated_at;

  return (
    <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-4 px-4 py-4 sm:px-6">
      {/* City header bar */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow mb-1">Command center</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl sm:text-4xl">{cityName}</h1>
            {tier ? (
              <Badge tone={tier.tone} title={tier.note}>
                {tier.label}
              </Badge>
            ) : (
              <Skeleton className="h-5 w-24" />
            )}
          </div>
          {tier && <p className="mt-1 text-xs text-ink-mute">{tier.note}</p>}
        </div>
        <div className="flex items-center gap-3">
          {generatedAt && <DataAge generatedAt={generatedAt} fixture={isFixture} />}
        </div>
      </header>

      {isFixture && generatedAt && <SampleDataBanner generatedAt={generatedAt} />}

      {/* Primary grid: map area + panel column */}
      <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr] xl:grid-cols-[2fr_1fr]">
        <div className="flex min-w-0 flex-col gap-4">
          <PanelBoundary label="Ward map">
            <Panel eyebrow="Ward map" title={`${cityName} air quality`} aria-label={`${cityName} ward map`}>
              <WardMap
                cityName={cityName}
                wardsUrl={wardsUrl}
                wards={nowcastState.status === "ready" ? nowcastState.data.wards : undefined}
                wardsLoading={nowcastState.status === "loading"}
              />
            </Panel>
          </PanelBoundary>
        </div>

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
                    <StatTile
                      label="Median ward AQI"
                      value={summary.median}
                      tone="accent"
                      sub="PM2.5 sub-index (24h)"
                    />
                    <StatTile
                      label="Wards poor or worse"
                      value={summary.poorPlus}
                      unit={`/ ${summary.total}`}
                      tone={summary.poorPlus > summary.total / 2 ? "bad" : "neutral"}
                    />
                  </div>
                  {summary.worst && (
                    <div className="rounded-[var(--radius-sm)] border border-[var(--line)] p-3">
                      <p className="eyebrow mb-1.5">Worst ward now</p>
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm text-ink" title={summary.worst.name}>
                          {summary.worst.name}
                        </span>
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

          <Panel eyebrow="Reference" title="Air quality scale" aria-label="AQI legend">
            <AqiLegend orientation="horizontal" />
          </Panel>
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
            <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--color-deep)]">
              <span
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ width: `${(n / max) * 100}%`, backgroundColor: s.color, opacity: 0.85 }}
              />
            </span>
            <span className="tabular w-6 text-right text-ink-mute">{n}</span>
          </li>
        );
      })}
    </ul>
  );
}
