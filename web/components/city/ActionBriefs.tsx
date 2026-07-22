"use client";

import type { ActionBrief } from "@/lib/schemas";
import { useUIStore } from "@/lib/store";
import { formatIST } from "@/lib/format";
import { actionLabel } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";

/**
 * Nemotron Action Briefs (spec §14): verified, evidence-cited "do this" items.
 * All strings are plain text (rendered escaped). Every claim carries an
 * evidence_ref resolving to a real published field; verified is verifier.passed.
 */
export function ActionBriefs({
  briefs,
  stale,
  nameById,
}: {
  briefs: ActionBrief[];
  stale?: boolean;
  nameById: Map<string, string>;
}) {
  const language = useUIStore((s) => s.language);
  const setSelected = useUIStore((s) => s.setSelectedWard);

  if (briefs.length === 0) {
    return <p className="text-sm text-ink-mute">No active briefs for this city right now.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {stale && (
        <p role="status" className="rounded-[var(--radius-sm)] border px-3 py-1.5 text-xs" style={{ borderColor: "color-mix(in oklab, var(--color-ember) 45%, transparent)", color: "var(--color-ember)" }}>
          Showing the last good briefs. The agent layer is refreshing.
        </p>
      )}
      {briefs.map((b) => (
        <article key={b.id} className="rounded-[var(--radius-md)] border p-3.5" style={{ borderColor: "var(--line)" }}>
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink">{b.headline}</h3>
            <Badge tone={b.verifier.passed ? "good" : "warn"} title={b.verifier.notes}>
              {b.verifier.passed ? "verified" : "unverified"}
            </Badge>
          </div>
          <p className="mt-1.5 text-xs leading-snug text-ink-mute">{b.situation}</p>
          <p className="mt-2 text-sm font-medium text-airglow">
            {b.action_code ? actionLabel(b.action_code, language) : b.action}
          </p>

          {b.target_wards.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {b.target_wards.slice(0, 6).map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setSelected(w)}
                  className="rounded-full border px-2 py-0.5 text-[0.7rem] text-ink-soft hover:text-ink"
                  style={{ borderColor: "var(--line)" }}
                >
                  {nameById.get(w) ?? w}
                </button>
              ))}
            </div>
          )}

          <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 text-[0.7rem]">
            <div>
              <dt className="text-ink-dim">Window</dt>
              <dd className="tabular text-ink-mute">
                {formatIST(b.trigger_window.start_utc)}
              </dd>
            </div>
            <div>
              <dt className="text-ink-dim">Owner</dt>
              <dd className="text-ink-mute">{b.owner}</dd>
            </div>
            {b.expected_effect && (
              <div className="col-span-2">
                <dt className="text-ink-dim">Expected effect</dt>
                <dd className="tabular text-ink-mute">
                  {b.expected_effect.ugm3} µg/m³ (CI {b.expected_effect.ci_low} to {b.expected_effect.ci_high})
                </dd>
              </div>
            )}
          </dl>

          {b.evidence_refs.length > 0 && (
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-ink-mute hover:text-ink">
                Evidence ({b.evidence_refs.length})
              </summary>
              <ul className="mt-1.5 flex flex-col gap-1">
                {b.evidence_refs.map((e, i) => (
                  <li key={i} className="flex items-start justify-between gap-2">
                    <span className="text-ink-soft">{e.label}</span>
                    <span className="tabular shrink-0 text-ink-dim" title={e.path}>
                      {e.value != null ? String(e.value) : "resolved"}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
