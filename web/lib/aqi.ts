import type { AqiCategory, Confidence, SourceLabel } from "./schemas";

/**
 * CPCB AQI category presentation. Category strings are byte-identical to the
 * contract (vayu/constants AQI_CATEGORIES). Every category pairs its official
 * CPCB colour with a distinct texture + label + numeric value so meaning is
 * NEVER carried by colour alone (spec §7, dataviz skill: the satisfactory/
 * moderate pair measures only ΔE 11.3 normal-vision, so texture is load-bearing).
 * Foreground colours are contrast-checked for AA on each fill.
 */

export interface AqiStyle {
  category: AqiCategory;
  color: string; // CSS var, for fills / chips
  fg: string; // AA-contrast text colour when text sits on the fill
  pattern: string; // texture class (globals.css)
  indexRange: string; // CPCB sub-index band
  order: number;
}

export const AQI_ORDER: readonly AqiCategory[] = [
  "Good",
  "Satisfactory",
  "Moderate",
  "Poor",
  "Very Poor",
  "Severe",
] as const;

export const AQI_STYLES: Record<AqiCategory, AqiStyle> = {
  Good: {
    category: "Good",
    color: "var(--color-aqi-good)",
    fg: "var(--color-void)",
    pattern: "pat-good",
    indexRange: "0-50",
    order: 0,
  },
  Satisfactory: {
    category: "Satisfactory",
    color: "var(--color-aqi-satisfactory)",
    fg: "var(--color-void)",
    pattern: "pat-satisfactory",
    indexRange: "51-100",
    order: 1,
  },
  Moderate: {
    category: "Moderate",
    color: "var(--color-aqi-moderate)",
    fg: "var(--color-void)",
    pattern: "pat-moderate",
    indexRange: "101-200",
    order: 2,
  },
  Poor: {
    category: "Poor",
    color: "var(--color-aqi-poor)",
    fg: "var(--color-void)",
    pattern: "pat-poor",
    indexRange: "201-300",
    order: 3,
  },
  "Very Poor": {
    category: "Very Poor",
    color: "var(--color-aqi-verypoor)",
    fg: "var(--color-void)",
    pattern: "pat-verypoor",
    indexRange: "301-400",
    order: 4,
  },
  Severe: {
    category: "Severe",
    color: "var(--color-aqi-severe)",
    fg: "var(--color-ink)",
    pattern: "pat-severe",
    indexRange: "401-500",
    order: 5,
  },
};

/** RGB tuples for canvas / deck.gl / SVG fills (kept in sync with the CSS vars). */
export const AQI_RGB: Record<AqiCategory, [number, number, number]> = {
  Good: [78, 167, 46],
  Satisfactory: [163, 200, 83],
  Moderate: [242, 209, 60],
  Poor: [242, 148, 52],
  "Very Poor": [229, 83, 60],
  Severe: [160, 44, 34],
};

/** CPCB category for a sub-index value (mirror of vayu/aqi.category_for_index). */
export function categoryForIndex(index: number | null | undefined): AqiCategory | null {
  if (index == null || Number.isNaN(index) || index < 0) return null;
  if (index <= 50) return "Good";
  if (index <= 100) return "Satisfactory";
  if (index <= 200) return "Moderate";
  if (index <= 300) return "Poor";
  if (index <= 400) return "Very Poor";
  return "Severe";
}

export function aqiStyle(category: AqiCategory): AqiStyle {
  return AQI_STYLES[category];
}

/* ---- Source attribution (validated CVD-safe categorical, fixed order) ---- */

export const SHARE_ORDER: readonly Exclude<SourceLabel, "mixed">[] = [
  "traffic",
  "industry",
  "biomass",
  "dust",
  "residential_other",
] as const;

export const SOURCE_COLOR: Record<SourceLabel, string> = {
  traffic: "var(--color-src-traffic)",
  industry: "var(--color-src-industry)",
  biomass: "var(--color-src-biomass)",
  dust: "var(--color-src-dust)",
  residential_other: "var(--color-src-residential)",
  mixed: "var(--color-src-mixed)",
};

/* ---- Confidence (identical encoding everywhere: colour + fill + label) ---- */

export const CONFIDENCE_META: Record<
  Confidence,
  { label: string; color: string; fill: number }
> = {
  high: { label: "High", color: "var(--color-airglow)", fill: 1 },
  med: { label: "Medium", color: "var(--color-airglow-dim)", fill: 0.62 },
  low: { label: "Low", color: "var(--color-ink-mute)", fill: 0.32 },
};

/* ---- Diverging effect scale (blue = reduced/good, red = increased/bad) ---- */

const DIVERGING_STOPS: Array<{ t: number; rgb: [number, number, number] }> = [
  { t: -1, rgb: [28, 92, 171] }, // strong reduction
  { t: -0.5, rgb: [62, 134, 224] },
  { t: 0, rgb: [71, 85, 93] }, // no detectable effect (neutral gray)
  { t: 0.5, rgb: [224, 106, 106] },
  { t: 1, rgb: [192, 57, 43] }, // strong increase
];

/**
 * Colour for a signed effect value. `t` is value / maxAbs, clamped to [-1, 1].
 * Negative (GRAP reduced PM2.5) -> blue; positive (increased) -> red; ~0 -> gray.
 */
export function divergingColor(t: number): [number, number, number] {
  const x = Math.max(-1, Math.min(1, t));
  for (let i = 0; i < DIVERGING_STOPS.length - 1; i++) {
    const a = DIVERGING_STOPS[i];
    const b = DIVERGING_STOPS[i + 1];
    if (x >= a.t && x <= b.t) {
      const f = b.t === a.t ? 0 : (x - a.t) / (b.t - a.t);
      return [
        Math.round(a.rgb[0] + f * (b.rgb[0] - a.rgb[0])),
        Math.round(a.rgb[1] + f * (b.rgb[1] - a.rgb[1])),
        Math.round(a.rgb[2] + f * (b.rgb[2] - a.rgb[2])),
      ];
    }
  }
  return DIVERGING_STOPS[x < 0 ? 0 : DIVERGING_STOPS.length - 1].rgb;
}

export function rgbCss([r, g, b]: [number, number, number], a = 1): string {
  return a === 1 ? `rgb(${r} ${g} ${b})` : `rgb(${r} ${g} ${b} / ${a})`;
}
