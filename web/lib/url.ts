/**
 * Only allow http(s) URLs as hrefs for data-derived links (CAQM orders,
 * citations, evidence). Defense in depth against a javascript:/data: URL that
 * slipped past publish-time sanitization. Returns undefined for anything else.
 */
export function safeHref(url: string | undefined | null): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    if (u.protocol === "http:" || u.protocol === "https:") return u.href;
  } catch {
    // not a valid absolute URL
  }
  return undefined;
}
