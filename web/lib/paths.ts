/** All published data lives under /data (web/public/data). */
export const DATA_BASE = "/data";

/** URL for a manifest-declared relative path (e.g. "delhi/nowcast.json"). */
export function dataUrl(rel?: string | null): string | null {
  return rel ? `${DATA_BASE}/${rel}` : null;
}

/** Convention path for a per-city file (fallback when the manifest omits it). */
export function cityConventionUrl(cityId: string, file: string): string {
  return `${DATA_BASE}/${cityId}/${file}`;
}

export const MANIFEST_URL = `${DATA_BASE}/manifest.json`;
export const AGENTLOG_URL = `${DATA_BASE}/agentlog.json`;
export const RECEIPTS_URL = `${DATA_BASE}/receipts.json`;
