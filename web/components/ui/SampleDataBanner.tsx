import { cn } from "@/lib/cn";
import { formatIST } from "@/lib/format";

/**
 * Shown when a data envelope carries fixture:true (spec §8 fixture protocol).
 * Honesty-by-design: the UI states plainly that numbers are illustrative
 * fixtures, not live measurements. Ember tone (off-map warm signal).
 */
export function SampleDataBanner({
  generatedAt,
  className,
}: {
  generatedAt?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-wrap items-center gap-x-2 gap-y-1 rounded-[var(--radius-sm)] border px-3 py-1.5 text-xs",
        className,
      )}
      style={{
        borderColor: "color-mix(in oklab, var(--color-ember) 45%, transparent)",
        backgroundColor: "color-mix(in oklab, var(--color-ember) 10%, transparent)",
        color: "var(--color-ember)",
      }}
    >
      <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "var(--color-ember)" }} />
      <span className="font-semibold uppercase tracking-wide">Sample data</span>
      <span className="text-ink-mute">
        Illustrative fixtures, not live measurements.
        {generatedAt ? ` Generated ${formatIST(generatedAt)}.` : ""}
      </span>
    </div>
  );
}
