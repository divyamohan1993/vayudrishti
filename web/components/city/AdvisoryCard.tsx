"use client";

import type { AdvisoryWard, RiskLevel } from "@/lib/schemas";
import { useUIStore } from "@/lib/store";
import { LANGUAGE_NAMES, riskLabel, type Lang } from "@/lib/i18n";
import { Segmented } from "@/components/ui/Segmented";
import { Badge } from "@/components/ui/Badge";

const RISK_TONE: Record<RiskLevel, "good" | "warn" | "bad"> = {
  low: "good",
  moderate: "warn",
  high: "warn",
  severe: "bad",
};

/**
 * Citizen advisory for a ward (spec §5.5). Text is DATA, rendered as plain text
 * only (React escapes it; no dangerouslySetInnerHTML). Language switch offers en
 * + hi, and the city's regional language when the advisory carries it.
 */
export function AdvisoryCard({
  advisory,
  regional,
}: {
  advisory: AdvisoryWard;
  regional?: { code: string; name: string };
}) {
  const language = useUIStore((s) => s.language);
  const setLanguage = useUIStore((s) => s.setLanguage);

  const hasRegional = !!advisory.langs.regional && !!regional;
  const options = [
    { value: "en", label: LANGUAGE_NAMES.en },
    { value: "hi", label: LANGUAGE_NAMES.hi },
    ...(hasRegional ? [{ value: regional!.code, label: regional!.name }] : []),
  ];

  const text =
    language === "en"
      ? advisory.langs.en
      : language === "hi"
        ? advisory.langs.hi
        : (advisory.langs.regional ?? advisory.langs.en);

  const activeValue = options.some((o) => o.value === language) ? language : "en";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="eyebrow">Risk</span>
          <Badge tone={RISK_TONE[advisory.risk_level]}>{riskLabel(advisory.risk_level, language)}</Badge>
        </span>
        <Segmented
          ariaLabel="Advisory language"
          size="sm"
          value={activeValue}
          onChange={(v) => setLanguage(v as Lang)}
          options={options}
        />
      </div>
      <p lang={activeValue} className="text-sm leading-relaxed text-ink-soft">
        {text}
      </p>
    </div>
  );
}
