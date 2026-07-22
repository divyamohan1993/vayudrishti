/** Minimal class-name joiner (no dependency; falsy parts dropped). */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
