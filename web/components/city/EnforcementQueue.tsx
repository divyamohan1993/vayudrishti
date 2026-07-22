"use client";

import type { EnforcementItem } from "@/lib/schemas";
import { useUIStore } from "@/lib/store";
import { SOURCE_COLOR } from "@/lib/aqi";
import { actionLabel, sourceLabelText } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { Sparkline } from "@/components/ui/Sparkline";
import { ConfidenceTag } from "@/components/ui/ConfidenceTag";

/**
 * Ranked enforcement queue (spec §5.4). Ranked by MEASURED signals only
 * (exceedance persistence x trend x vulnerability). The dominant source is a
 * confidence-tagged label, never a rank multiplier. Labeled decision support.
 */
export function EnforcementQueue({
  items,
  nameById,
  max = 6,
}: {
  items: EnforcementItem[];
  nameById: Map<string, string>;
  max?: number;
}) {
  const language = useUIStore((s) => s.language);
  const selected = useUIStore((s) => s.selectedWardId);
  const setSelected = useUIStore((s) => s.setSelectedWard);
  const rows = items.slice(0, max);

  return (
    <ol className="flex flex-col gap-2">
      {rows.map((it, i) => {
        const isSel = it.ward_id === selected;
        return (
          <li key={it.ward_id}>
            <button
              type="button"
              onClick={() => setSelected(isSel ? null : it.ward_id)}
              className={cn(
                "w-full rounded-[var(--radius-md)] border p-3 text-left transition-colors hover:border-[var(--line-airglow)]",
              )}
              style={{ borderColor: isSel ? "var(--line-airglow)" : "var(--line)" }}
              aria-pressed={isSel}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="tabular text-xs text-ink-dim">#{i + 1}</span>
                  <span className="truncate text-sm font-medium text-ink" title={nameById.get(it.ward_id) ?? it.ward_id}>
                    {nameById.get(it.ward_id) ?? it.ward_id}
                  </span>
                </span>
                <Sparkline data={it.evidence.trend_72h} label="72 hour PM2.5 trend" />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs">
                  <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: SOURCE_COLOR[it.source_label] }} />
                  <span className="text-ink-soft">{sourceLabelText(it.source_label, language)}</span>
                </span>
                <ConfidenceTag level={it.confidence} showLabel={false} />
                <span className="tabular text-xs text-ink-mute">
                  {it.evidence.persistence_days}d over limit · {Math.round(it.evidence.exceedance_pct)}% exceedance
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-airglow">{actionLabel(it.action, language)}</span>
                <span className="tabular text-[0.7rem] text-ink-dim">priority {Math.round(it.priority_score)}</span>
              </div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
