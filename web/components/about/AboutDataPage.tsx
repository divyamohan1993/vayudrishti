"use client";

import { useResource } from "@/lib/hooks";
import { agentLog as agentLogSchema, manifest as manifestSchema, receipts as receiptsSchema } from "@/lib/schemas";
import { AGENTLOG_URL, MANIFEST_URL, RECEIPTS_URL, dataUrl } from "@/lib/paths";
import { fmtCompact } from "@/lib/format";
import { Panel } from "@/components/ui/Panel";
import { PanelBoundary } from "@/components/ui/PanelBoundary";
import { Badge } from "@/components/ui/Badge";
import { LoadingBlock } from "@/components/ui/Skeleton";
import { MethodologyTable } from "@/components/receipts/MethodologyTable";

const SOURCES = [
  ["OpenAQ S3 archive", "CPCB hourly history: PM2.5, PM10, NO2, SO2, O3, CO, from Feb 2025", "None"],
  ["data.gov.in CPCB", "Live station snapshot", "Free key"],
  ["Open-Meteo, ERA5, CAMS", "Wind, temperature, humidity, precipitation, boundary-layer height. CAMS is a covariate only, never a validation target", "None"],
  ["NASA FIRMS", "VIIRS 375m active fires and fire radiative power", "None"],
  ["NASA GIBS WMTS", "Satellite raster overlays: Sentinel-5P NO2, MODIS AOD, VIIRS", "None"],
  ["Google Earth Engine", "Numeric satellite features (Sentinel-5P, MODIS MAIAC AOD) and WorldPop population", "Service account"],
  ["Datameet and OSM", "Ward boundaries, roads, built-up area, vulnerable sites", "None"],
  ["US Diplomatic Post (via OpenAQ)", "Independent validation network, never trained on", "Free key"],
];

const GAPS = [
  "Ward vintage is best-available and differs by city: Mumbai uses 24 BMC wards, Bengaluru 198 BBMP wards, Delhi 290 wards. Granularity is noted per city.",
  "Training data is a single winter (Feb 2025 onward). No multi-season generalization is claimed; this is stated on the receipts page.",
  "Live AQI is dull in the monsoon. The demo pairs it with a Nov 2025 replay window built from out-of-fold predictions.",
  "Stations and grid cells outside any ward polygon are kept as an unassigned bucket, never dropped.",
];

export function AboutDataPage() {
  const rc = useResource(RECEIPTS_URL, receiptsSchema);
  const mf = useResource(MANIFEST_URL, manifestSchema);
  // Prefer the manifest-declared path; else the global convention path (the
  // agent log is published globally, so the fallback resolves when present).
  const agentlogUrl = mf.status === "ready" ? (mf.data.agentlog ? dataUrl(mf.data.agentlog) : AGENTLOG_URL) : null;
  const al = useResource(agentlogUrl, agentLogSchema);

  const satNumeric = mf.status === "ready" ? mf.data.sat_numeric : undefined;

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6 px-4 py-6 sm:px-6">
      <header>
        <p className="eyebrow">Data and sources</p>
        <h1 className="mt-2 text-4xl sm:text-5xl">Every number, traced.</h1>
        <p className="mt-3 max-w-2xl text-ink-soft">
          VayuDrishti uses only real, free, public data. No synthetic values: gaps are filled by models
          with uncertainty bands and labels, never invented.
        </p>
      </header>

      <Panel eyebrow="Provenance" title="Sources" aria-label="Data sources">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-sm">
            <thead>
              <tr className="border-b" style={{ borderColor: "var(--line)" }}>
                {["Source", "What we use", "Auth"].map((h) => (
                  <th key={h} className="eyebrow py-2 pr-4 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SOURCES.map(([s, w, a]) => (
                <tr key={s} className="border-b align-top" style={{ borderColor: "var(--line)" }}>
                  <td className="py-2.5 pr-4 font-medium text-ink">{s}</td>
                  <td className="py-2.5 pr-4 text-ink-mute">{w}</td>
                  <td className="py-2.5 pr-4 text-xs text-ink-dim">{a}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel eyebrow="Honesty" title="Coverage and gaps" aria-label="Coverage and gaps">
          <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-ink-soft">
            {GAPS.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </Panel>

        <Panel eyebrow="Satellites" title="Numeric satellite path" aria-label="Satellite status">
          <div className="flex items-center gap-2">
            <Badge tone={satNumeric ? "good" : "outline"}>
              {satNumeric === undefined ? "checking" : satNumeric ? "numeric path active" : "visual path only"}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-ink-mute">
            Five real satellites: Sentinel-5P (TROPOMI), Terra and Aqua (MODIS MAIAC AOD), Suomi-NPP and
            NOAA-20 (VIIRS). Visuals come from zero-auth GIBS and are always on. Numeric features run
            through Google Earth Engine when the service account is live; parquet columns are always
            present, NaN when unavailable, so absence never blocks.
          </p>
        </Panel>
      </div>

      {al.status === "ready" && (
        <PanelBoundary label="Agent transparency">
          <Panel eyebrow="Agentic layer" title="Reasoning-agent transparency" aria-label="Agent transparency">
            <p className="mb-3 text-sm text-ink-mute">
              Judges see the machinery. Raw model thinking is never published; this is the redacted trace.
            </p>
            <div className="flex flex-wrap gap-6">
              {al.data.model && (
                <div>
                  <p className="eyebrow">Model</p>
                  <p className="tabular mt-1 text-sm text-ink">{al.data.model}</p>
                </div>
              )}
              {al.data.totals?.calls != null && (
                <div>
                  <p className="eyebrow">Calls</p>
                  <p className="tabular mt-1 text-sm text-ink">{al.data.totals.calls}</p>
                </div>
              )}
              {al.data.totals?.total != null && (
                <div>
                  <p className="eyebrow">Tokens</p>
                  <p className="tabular mt-1 text-sm text-ink">{fmtCompact(al.data.totals.total)}</p>
                </div>
              )}
            </div>
          </Panel>
        </PanelBoundary>
      )}

      <PanelBoundary label="Methodology">
        <Panel eyebrow="CPCB methodology" title="National AQI breakpoints" aria-label="CPCB methodology">
          {rc.status === "ready" && rc.data.methodology?.aqi_breakpoints ? (
            <MethodologyTable
              breakpoints={rc.data.methodology.aqi_breakpoints}
              headlineLabel={rc.data.methodology.headline_label}
              severeNote={rc.data.methodology.severe_note}
            />
          ) : (
            <LoadingBlock lines={6} />
          )}
        </Panel>
      </PanelBoundary>
    </div>
  );
}
