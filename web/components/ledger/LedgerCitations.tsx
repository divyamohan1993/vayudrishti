import type { Citation } from "@/lib/schemas";
import { safeHref } from "@/lib/url";

export function LedgerCitations({
  citations,
  assumptions,
}: {
  citations: Citation[];
  assumptions?: string[];
}) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <p className="eyebrow mb-2">Peer-reviewed methods</p>
        <ul className="flex flex-col gap-1.5 text-xs">
          {citations.map((c, i) => {
            const href = safeHref(c.url);
            return (
              <li key={i}>
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-airglow">
                    {c.label} &#8599;
                  </a>
                ) : (
                  <span className="text-ink-soft">{c.label}</span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      {assumptions && assumptions.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Assumptions on record</p>
          <ul className="flex list-disc flex-col gap-1.5 pl-4 text-xs text-ink-mute">
            {assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
