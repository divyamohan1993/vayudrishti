"use client";

import type { AttributionWard } from "@/lib/schemas";
import { SHARE_ORDER, SOURCE_COLOR } from "@/lib/aqi";
import { sourceLabelText } from "@/lib/i18n";
import { useUIStore } from "@/lib/store";
import { ConfidenceTag } from "@/components/ui/ConfidenceTag";

/**
 * Per-ward source apportionment as a LABELED ESTIMATE (spec §5.3). Validated
 * CVD-safe categorical in fixed order, always with direct labels + percentages.
 * Never a claim of measured emissions.
 */
export function AttributionShares({ ward }: { ward: AttributionWard }) {
  const language = useUIStore((s) => s.language);
  const total = SHARE_ORDER.reduce((sum, k) => sum + ward.shares[k], 0) || 1;

  return (
    <div>
      <div className="flex h-4 w-full overflow-hidden rounded-full" style={{ background: "var(--color-deep)" }} role="img" aria-label="Source share bar">
        {SHARE_ORDER.map((k) => {
          const pct = (ward.shares[k] / total) * 100;
          if (pct <= 0) return null;
          return (
            <span
              key={k}
              style={{ width: `${pct}%`, backgroundColor: SOURCE_COLOR[k] }}
              title={`${sourceLabelText(k, language)} ${Math.round(pct)}%`}
            />
          );
        })}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        {SHARE_ORDER.map((k) => (
          <li key={k} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: SOURCE_COLOR[k] }} />
              <span className="text-ink-soft">{sourceLabelText(k, language)}</span>
            </span>
            <span className="tabular text-ink-mute">{Math.round((ward.shares[k] / total) * 100)}%</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-center gap-2">
        <span className="eyebrow">Confidence</span>
        <ConfidenceTag level={ward.confidence} />
      </div>
      <p className="mt-2 text-[0.72rem] leading-snug text-ink-dim">{ward.method_notes}</p>
      <p className="mt-1 text-[0.7rem] text-ink-dim">Labeled estimate (CPF plus land-use heuristics). Not a measurement of emissions.</p>
    </div>
  );
}
