"use client";

import { useResource } from "@/lib/hooks";
import { receipts as receiptsSchema } from "@/lib/schemas";
import { RECEIPTS_URL, cityConventionUrl } from "@/lib/paths";
import { safeHref } from "@/lib/url";
import { Panel } from "@/components/ui/Panel";

const GAP_COVER: [string, string][] = [
  ["Sparse stations", "Satellite AOD-to-PM regression plus kriging spatial structure"],
  ["Satellite cloud gaps (monsoon)", "Ground kriging plus meteorology features and compositing; GEMS hourly when keyed"],
  ["One overpass per day (low-earth-orbit)", "GEMS geostationary diurnal (keyed) plus diurnal ML priors"],
  ["Model bias drift", "Independent embassy-network validation plus calibration receipts"],
  ["Bad station data", "Station trust scores down-weight fusion inputs, weights on record"],
  ["Point estimates hide risk", "Quantiles plus per-ward exceedance probabilities"],
];

const METHODS: [string, string][] = [
  ["Ensemble gap-fill", "Four independent estimators (IDW, ordinary kriging, satellite AOD-to-PM, LightGBM) combined by stacked generalization (Wolpert) trained only on leave-one-station-out folds. Published per cell: p50 and p90, per-method weights, and a method-disagreement index as honest epistemic uncertainty."],
  ["Weather normalization", "Grange and Carslaw meteorological normalization: resample the meteorology and predict a weather-neutral PM2.5 series, so a drop is the policy and not the rain."],
  ["Causal effect estimation", "Event-study around each GRAP transition on the normalized series, with placebo tests on matched high-pollution non-intervention days and block-bootstrap confidence intervals."],
  ["Trajectory attribution", "Kinematic 48h back-trajectories and concentration-weighted trajectory fields (Hsu 2003), overlapped with FIRMS fires and Sentinel-5P NO2 columns. CPF gives direction; CWT gives geography."],
  ["Health translation", "GEMM exposure-response (Burnett 2018) with WorldPop 100m population, aggregated per ward to avoided exposure and avoided premature deaths, always labeled a modeled estimate."],
];

const EQUATIONS: [string, string][] = [
  ["CPCB sub-index (linear interpolation)", "Ip = (IHi - ILo) / (BPHi - BPLo) * (Cp - BPLo) + ILo"],
  ["Inverse-distance weighting baseline", "c(x) = sum(wi * ci) / sum(wi),  wi = 1 / d(x, xi)^p"],
  ["Weather normalization", "c_norm(t) = mean over resampled meteorology of f(meteo*, calendar(t))"],
  ["GEMM attributable mortality", "deaths = population * baseline_rate * (1 - 1 / RR(exposure))"],
];

const EXTRA_CITATIONS = [
  "van Donkelaar et al., satellite AOD to surface PM2.5 (two-stage)",
  "Wolpert 1992, stacked generalization",
  "Hsu et al. 2003, concentration-weighted trajectory",
  "Wackernagel, ordinary kriging (multivariate geostatistics)",
];

export function MethodsPage() {
  const rc = useResource(RECEIPTS_URL, receiptsSchema);
  const methodCitations = rc.status === "ready" ? rc.data.ledger?.method_citations ?? [] : [];

  const products = [
    ["Hourly nowcast grid + ward rollups", cityConventionUrl("delhi", "nowcast.json"), "JSON now; Parquet and GeoTIFF from the publish pipeline"],
    ["Ward forecast (24 to 72h, p50/p90)", cityConventionUrl("delhi", "forecast.json"), "JSON"],
    ["Intervention Ledger (effects + mortality)", cityConventionUrl("delhi", "ledger.json"), "JSON"],
    ["Validation receipts", RECEIPTS_URL, "JSON"],
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6 px-4 py-6 sm:px-6">
      <header>
        <p className="eyebrow">Methods</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Gaps, closed in pairs.</h1>
        <p className="mt-3 max-w-2xl text-ink-soft">
          Existing air-quality systems share known gaps: single-method estimates with hidden
          uncertainty, no independent validation, unmonitored data quality, one-overpass blindness,
          reactive alerts. Each gap here is closed by a pair of peer-reviewed techniques that cover each
          other&rsquo;s failure modes.
        </p>
      </header>

      <Panel eyebrow="The core claim" title="Gap-cover matrix" aria-label="Gap-cover matrix">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="border-b" style={{ borderColor: "var(--line)" }}>
                <th className="eyebrow py-2 pr-4 text-left font-medium">Failure mode</th>
                <th className="eyebrow py-2 pr-4 text-left font-medium">Covered by</th>
              </tr>
            </thead>
            <tbody>
              {GAP_COVER.map(([f, c]) => (
                <tr key={f} className="border-b align-top" style={{ borderColor: "var(--line)" }}>
                  <td className="py-2.5 pr-4 font-medium text-ink">{f}</td>
                  <td className="py-2.5 pr-4 text-ink-mute">{c}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel eyebrow="Method stack" title="How each layer works" aria-label="Method stack">
        <ol className="flex flex-col gap-4">
          {METHODS.map(([n, d], i) => (
            <li key={n} className="flex gap-4">
              <span className="tabular shrink-0 text-airglow">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <p className="font-medium text-ink">{n}</p>
                <p className="mt-0.5 text-sm text-ink-mute">{d}</p>
              </div>
            </li>
          ))}
        </ol>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel eyebrow="Formulas" title="Key equations" aria-label="Key equations">
          <ul className="flex flex-col gap-3">
            {EQUATIONS.map(([label, eq]) => (
              <li key={label}>
                <p className="text-xs text-ink-mute">{label}</p>
                <pre className="tabular mt-1 overflow-x-auto rounded-[var(--radius-sm)] border p-2.5 text-xs text-airglow" style={{ borderColor: "var(--line)", background: "var(--color-void)" }}>
                  {eq}
                </pre>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel eyebrow="Reuse" title="Downloadable data products" aria-label="Downloadable data products">
          <p className="mb-3 text-sm text-ink-mute">
            Researchers can reuse the outputs. Published products, with lineage on the receipts page:
          </p>
          <ul className="flex flex-col gap-2">
            {products.map(([label, url, fmt]) => (
              <li key={label} className="flex items-center justify-between gap-3 border-b pb-2 text-sm" style={{ borderColor: "var(--line)" }}>
                <a href={url} download className="text-airglow">{label}</a>
                <span className="text-xs text-ink-dim">{fmt}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel eyebrow="On the record" title="Peer-reviewed methods" aria-label="Citations">
        <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
          {methodCitations.map((c, i) => {
            const href = safeHref(c.url);
            return (
              <li key={`m${i}`}>
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-airglow">{c.label} &#8599;</a>
                ) : (
                  <span className="text-ink-soft">{c.label}</span>
                )}
                {c.used_for && <span className="text-ink-mute"> · {c.used_for}</span>}
              </li>
            );
          })}
          {EXTRA_CITATIONS.map((label, i) => (
            <li key={`e${i}`} className="text-ink-soft">{label}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
