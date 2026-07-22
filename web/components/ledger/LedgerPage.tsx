"use client";

import { useResource } from "@/lib/hooks";
import {
  interventions as interventionsSchema,
  ledger as ledgerSchema,
  receipts as receiptsSchema,
  wardsGeojson as wardsSchema,
} from "@/lib/schemas";
import type { WardFC } from "@/lib/geo";
import { cityConventionUrl, RECEIPTS_URL } from "@/lib/paths";
import { fmtCI, fmtNum } from "@/lib/format";
import { Panel } from "@/components/ui/Panel";
import { PanelBoundary } from "@/components/ui/PanelBoundary";
import { StatusNote } from "@/components/ui/StatusNote";
import { LoadingBlock } from "@/components/ui/Skeleton";
import { SampleDataBanner } from "@/components/ui/SampleDataBanner";
import { DataAge } from "@/components/ui/DataAge";
import { Badge } from "@/components/ui/Badge";
import { RibbonChart } from "./RibbonChart";
import { GrapOrders } from "./GrapOrders";
import { StageEffects } from "./StageEffects";
import { EffectMap } from "./EffectMap";
import { TimingSlider } from "./TimingSlider";
import { LedgerCitations } from "./LedgerCitations";

export function LedgerPage({ cityId }: { cityId: string }) {
  const iv = useResource(cityConventionUrl(cityId, "interventions.json"), interventionsSchema);
  const lg = useResource(cityConventionUrl(cityId, "ledger.json"), ledgerSchema);
  const wards = useResource(cityConventionUrl(cityId, "wards.geojson"), wardsSchema);
  const rc = useResource(RECEIPTS_URL, receiptsSchema);

  const fixture =
    (iv.status === "ready" && iv.data.fixture) || (lg.status === "ready" && lg.data.fixture);
  const generatedAt = lg.status === "ready" ? lg.data.generated_at : iv.status === "ready" ? iv.data.generated_at : undefined;
  const novelty = rc.status === "ready" ? rc.data.ledger?.novelty_statement : undefined;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 py-6 sm:px-6">
      {/* Hero */}
      <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">Intervention Ledger · Delhi</p>
            <Badge tone="accent">World-first capability</Badge>
          </div>
          <h1 className="mt-3 text-4xl sm:text-5xl">Did Delhi&rsquo;s emergency measures actually work?</h1>
          <p className="mt-3 max-w-xl text-ink-soft">
            The first operational, weather-adjusted, ward-by-ward audit of whether GRAP stages cut
            pollution, and what acting earlier would have saved. Every number carries a confidence
            interval. Every date cites a CAQM order. When a stage shows no effect, we say so.
          </p>
          {generatedAt && <DataAge className="mt-3" generatedAt={generatedAt} fixture={fixture} />}
        </div>
        <PanelBoundary label="Avoided mortality">
          <div className="shrink-0 rounded-[var(--radius-lg)] border p-5" style={{ borderColor: "var(--line-airglow)", background: "var(--color-airglow-ghost)" }}>
            {lg.status === "ready" ? (
              <>
                <p className="eyebrow">Avoided premature deaths, this winter</p>
                <p className="tabular mt-1 text-5xl font-semibold" style={{ color: "var(--color-div-neg-1)" }}>
                  {fmtNum(lg.data.totals.avoided_deaths, 0)}
                </p>
                <p className="tabular mt-1 text-xs text-ink-mute">
                  95% CI {fmtCI(lg.data.totals.ci_low, lg.data.totals.ci_high, 0)} · modeled estimate (GEMM)
                </p>
                <p className="tabular mt-2 text-xs text-ink-dim">
                  {fmtNum(lg.data.totals.avoided_exposure_pugh, 0)} person-µg/m³-hours avoided
                </p>
              </>
            ) : (
              <LoadingBlock lines={3} className="w-52" />
            )}
          </div>
        </PanelBoundary>
      </header>

      {fixture && generatedAt && <SampleDataBanner generatedAt={generatedAt} />}

      {novelty && (
        <blockquote className="rounded-[var(--radius-md)] border-l-2 py-2 pl-4 text-sm text-ink-soft" style={{ borderColor: "var(--color-airglow)" }}>
          {novelty}{" "}
          <a href="/receipts/" className="text-airglow">
            See prior art and method receipts.
          </a>
        </blockquote>
      )}

      {/* Ribbon */}
      <PanelBoundary label="Weather-normalized ribbon">
        <Panel eyebrow="Deweathered signal" title="Raw vs weather-normalized PM2.5 over the GRAP window">
          {iv.status === "ready" ? (
            <div className="flex flex-col gap-4">
              <RibbonChart series={iv.data.series} calendar={iv.data.calendar} />
              <div>
                <p className="eyebrow mb-2">GRAP stage orders (public record)</p>
                <GrapOrders calendar={iv.data.calendar} />
              </div>
            </div>
          ) : iv.status === "error" ? (
            <StatusNote tone="error" title="Ledger series unavailable" message={iv.error} />
          ) : (
            <LoadingBlock lines={6} />
          )}
        </Panel>
      </PanelBoundary>

      {/* Stage effects */}
      <PanelBoundary label="Stage effects">
        <Panel eyebrow="Causal audit" title="Did each stage work? Event-study with placebo tests">
          {iv.status === "ready" ? (
            <StageEffects effects={iv.data.effects} />
          ) : (
            <LoadingBlock lines={4} />
          )}
        </Panel>
      </PanelBoundary>

      {/* Effect map + timing */}
      <div className="grid gap-6 lg:grid-cols-2">
        <PanelBoundary label="Effect map">
          <Panel eyebrow="Where it worked" title="Per-ward weather-adjusted effect">
            {lg.status === "ready" && wards.status === "ready" ? (
              <EffectMap fc={wards.data as unknown as WardFC} wards={lg.data.wards} cityName="Delhi" />
            ) : lg.status === "error" || wards.status === "error" ? (
              <StatusNote tone="error" title="Effect map unavailable" />
            ) : (
              <LoadingBlock lines={6} />
            )}
          </Panel>
        </PanelBoundary>
        <PanelBoundary label="Counterfactual timing">
          <Panel eyebrow="What if we acted sooner" title="Counterfactual timing">
            {lg.status === "ready" ? (
              <TimingSlider counterfactuals={lg.data.counterfactuals} />
            ) : (
              <LoadingBlock lines={4} />
            )}
          </Panel>
        </PanelBoundary>
      </div>

      {/* Citations */}
      {lg.status === "ready" && (
        <PanelBoundary label="Citations">
          <Panel eyebrow="On the record" title="Methods, citations, and assumptions">
            <LedgerCitations citations={lg.data.citations} assumptions={lg.data.assumptions} />
          </Panel>
        </PanelBoundary>
      )}
    </div>
  );
}
