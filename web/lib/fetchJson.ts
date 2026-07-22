import type { ZodType } from "zod";

/**
 * Client-side JSON fetch + schema validation. A bad or missing file degrades a
 * single panel (spec §6) — callers show an error state, never crash the app.
 * Static assets are CDN-cached (default fetch cache) so replay works offline
 * once loaded.
 */

export type FetchResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

export async function fetchJson<T>(
  url: string,
  schema: ZodType<T>,
  signal?: AbortSignal,
): Promise<FetchResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, { signal });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") return { ok: false, error: "aborted" };
    return { ok: false, error: "network error" };
  }
  if (!res.ok) {
    return { ok: false, error: `not available (${res.status})`, status: res.status };
  }
  let json: unknown;
  try {
    json = await res.json();
  } catch {
    return { ok: false, error: "invalid JSON" };
  }
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    return { ok: false, error: "data did not match the expected shape" };
  }
  return { ok: true, data: parsed.data };
}

/** True when a data envelope is fixture/sample data (drives the sample banner). */
export function isFixture(v: { fixture?: boolean } | null | undefined): boolean {
  return v?.fixture === true;
}
