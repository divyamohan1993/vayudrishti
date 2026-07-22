import type { AqiCategory, Confidence, ForecastWard, NowcastWard } from "./schemas";
import type { TimelineH } from "./store";

/** Unified per-ward view at a timeline position (0 = nowcast, else forecast). */
export interface WardView {
  ward_id: string;
  name: string;
  category: AqiCategory;
  subindex: number;
  pm25_p50: number;
  pm25_p90: number;
  confidence: Confidence;
  horizon: TimelineH;
}

export function forecastPointAt(fw: ForecastWard | undefined, h: number) {
  return fw?.series.find((p) => p.h === h);
}

/**
 * Build the ward view map for a timeline position. The t=0 seam (spec §5.2):
 * "now" is the nowcast ward value; forecast series start at h=24. Wards without
 * a forecast point at the horizon fall back to their nowcast value.
 */
export function buildWardView(
  nowcast: NowcastWard[] | undefined,
  forecast: ForecastWard[] | undefined,
  h: TimelineH,
): Map<string, WardView> {
  const nowById = new Map<string, NowcastWard>();
  for (const w of nowcast ?? []) nowById.set(w.ward_id, w);

  const out = new Map<string, WardView>();
  if (h === 0) {
    for (const w of nowcast ?? [])
      out.set(w.ward_id, {
        ward_id: w.ward_id,
        name: w.name,
        category: w.category,
        subindex: w.subindex24h,
        pm25_p50: w.pm25_p50,
        pm25_p90: w.pm25_p90,
        confidence: w.confidence,
        horizon: 0,
      });
    return out;
  }
  for (const fw of forecast ?? []) {
    const p = forecastPointAt(fw, h);
    const now = nowById.get(fw.ward_id);
    if (p) {
      out.set(fw.ward_id, {
        ward_id: fw.ward_id,
        name: fw.name,
        category: p.category,
        subindex: p.subindex24h,
        pm25_p50: p.pm25_p50,
        pm25_p90: p.pm25_p90,
        confidence: p.confidence,
        horizon: h,
      });
    } else if (now) {
      out.set(fw.ward_id, {
        ward_id: fw.ward_id,
        name: fw.name,
        category: now.category,
        subindex: now.subindex24h,
        pm25_p50: now.pm25_p50,
        pm25_p90: now.pm25_p90,
        confidence: now.confidence,
        horizon: 0,
      });
    }
  }
  return out;
}

export function medianSubindex(views: Iterable<WardView>): number {
  const arr = [...views].map((v) => v.subindex).sort((a, b) => a - b);
  return arr.length ? arr[Math.floor(arr.length / 2)] : 0;
}
