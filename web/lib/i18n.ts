import type {
  EnforcementAction,
  GrapStage,
  RiskLevel,
  SourceLabel,
} from "./schemas";

/**
 * Enum -> display labels. The enum keys are i18n keys (spec §8); web owns the
 * text. Advisory body text is authored upstream (advisories.langs) and rendered
 * as-is; this table covers the UI chrome enums only. Fallback is always English.
 */

export type Lang = "en" | "hi" | "mr";

export const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  hi: "हिन्दी",
  mr: "मराठी",
};

type LabelSet = { en: string; hi?: string; mr?: string };

function pick(set: LabelSet, lang: Lang): string {
  return set[lang] ?? set.en;
}

const ACTION_LABELS: Record<EnforcementAction, LabelSet> = {
  deploy_water_sprinkling: { en: "Deploy water sprinkling", hi: "पानी का छिड़काव तैनात करें" },
  halt_construction_dust: { en: "Halt construction dust", hi: "निर्माण धूल पर रोक लगाएँ" },
  intensify_mechanized_sweeping: {
    en: "Intensify mechanized sweeping",
    hi: "यंत्रीकृत सफाई बढ़ाएँ",
  },
  reroute_divert_heavy_traffic: { en: "Reroute heavy traffic", hi: "भारी यातायात का मार्ग बदलें" },
  inspect_industrial_emissions: {
    en: "Inspect industrial emissions",
    hi: "औद्योगिक उत्सर्जन का निरीक्षण करें",
  },
  ban_open_biomass_burning: { en: "Ban open biomass burning", hi: "खुले में बायोमास जलाने पर रोक" },
  issue_public_health_advisory: {
    en: "Issue public health advisory",
    hi: "सार्वजनिक स्वास्थ्य परामर्श जारी करें",
  },
  monitor_no_action: { en: "Monitor, no action yet", hi: "निगरानी करें, अभी कोई कार्रवाई नहीं" },
};

const SOURCE_LABELS: Record<SourceLabel, LabelSet> = {
  traffic: { en: "Traffic", hi: "यातायात" },
  industry: { en: "Industry", hi: "उद्योग" },
  biomass: { en: "Biomass burning", hi: "बायोमास दहन" },
  dust: { en: "Dust", hi: "धूल" },
  residential_other: { en: "Residential / other", hi: "आवासीय / अन्य" },
  mixed: { en: "Mixed", hi: "मिश्रित" },
};

const RISK_LABELS: Record<RiskLevel, LabelSet> = {
  low: { en: "Low", hi: "कम", mr: "कमी" },
  moderate: { en: "Moderate", hi: "मध्यम", mr: "मध्यम" },
  high: { en: "High", hi: "उच्च", mr: "उच्च" },
  severe: { en: "Severe", hi: "गंभीर", mr: "गंभीर" },
};

export function actionLabel(a: EnforcementAction, lang: Lang = "en"): string {
  return pick(ACTION_LABELS[a], lang);
}

export function sourceLabelText(s: SourceLabel, lang: Lang = "en"): string {
  return pick(SOURCE_LABELS[s], lang);
}

export function riskLabel(r: RiskLevel, lang: Lang = "en"): string {
  return pick(RISK_LABELS[r], lang);
}

const STAGE_ROMAN: Record<GrapStage, string> = {
  "GRAP-I": "I",
  "GRAP-II": "II",
  "GRAP-III": "III",
  "GRAP-IV": "IV",
};

export function stageLabel(s: GrapStage): string {
  return `GRAP Stage ${STAGE_ROMAN[s]}`;
}

export function stageShort(s: GrapStage): string {
  return STAGE_ROMAN[s];
}
