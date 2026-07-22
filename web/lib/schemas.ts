import { z } from "zod";

/**
 * Zod mirrors of the frozen JSON contracts in config/schemas/*.json (spec §8, §13).
 * Handshaken against vayu-models' schemas on 2026-07-22.
 *
 * Resilience: objects intentionally strip unknown keys (default zod behaviour)
 * rather than .strict() — a field added upstream must never crash a panel. The
 * fetch layer safeParses and degrades one panel on failure (spec §6).
 */

/* ---- Shared enums / constants (byte-identical to the contract) ---- */

export const AQI_CATEGORIES = [
  "Good",
  "Satisfactory",
  "Moderate",
  "Poor",
  "Very Poor",
  "Severe",
] as const;
export const aqiCategory = z.enum(AQI_CATEGORIES);
export type AqiCategory = (typeof AQI_CATEGORIES)[number];

export const confidence = z.enum(["high", "med", "low"]);
export type Confidence = z.infer<typeof confidence>;

export const riskLevel = z.enum(["low", "moderate", "high", "severe"]);
export type RiskLevel = z.infer<typeof riskLevel>;

export const sourceLabel = z.enum([
  "traffic",
  "industry",
  "biomass",
  "dust",
  "residential_other",
  "mixed",
]);
export type SourceLabel = z.infer<typeof sourceLabel>;

export const enforcementAction = z.enum([
  "deploy_water_sprinkling",
  "halt_construction_dust",
  "intensify_mechanized_sweeping",
  "reroute_divert_heavy_traffic",
  "inspect_industrial_emissions",
  "ban_open_biomass_burning",
  "issue_public_health_advisory",
  "monitor_no_action",
]);
export type EnforcementAction = z.infer<typeof enforcementAction>;

export const cityTier = z.enum(["deep", "standard", "config-only"]);
export type CityTier = z.infer<typeof cityTier>;

export const grapStage = z.enum(["GRAP-I", "GRAP-II", "GRAP-III", "GRAP-IV"]);
export type GrapStage = z.infer<typeof grapStage>;

/* ---- manifest.json ---- */

export const cityFiles = z.object({
  nowcast: z.string().optional(),
  forecast: z.string().optional(),
  attribution: z.string().optional(),
  enforcement: z.string().optional(),
  advisories: z.string().optional(),
  wards: z.string().optional(),
  replay_index: z.string().optional(),
  interventions: z.string().optional(),
  ledger: z.string().optional(),
  briefs: z.string().optional(),
});
export type CityFiles = z.infer<typeof cityFiles>;

export const manifestCity = z.object({
  id: z.string(),
  name: z.string(),
  tier: cityTier,
  centroid: z.object({ lat: z.number(), lon: z.number() }),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  languages: z.array(z.string()),
  files: cityFiles,
  fixture: z.boolean().optional(),
  generated_at: z.string().optional(),
});
export type ManifestCity = z.infer<typeof manifestCity>;

export const manifest = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  sat_numeric: z.boolean(),
  agentlog: z.string().optional(),
  cities: z.array(manifestCity).min(1),
});
export type Manifest = z.infer<typeof manifest>;

/* ---- nowcast.json ---- */

export const gridMeta = z.object({
  lat0: z.number(),
  lon0: z.number(),
  cell_deg: z.number().positive(),
  crs: z.string(),
});
export type GridMeta = z.infer<typeof gridMeta>;

export const gridCell = z.object({
  cell_id: z.string(),
  row: z.number().int(),
  col: z.number().int(),
  pm25_p50: z.number(),
  pm25_p90: z.number(),
  subindex24h: z.number(),
  category: aqiCategory,
});
export type GridCell = z.infer<typeof gridCell>;

export const nowcastWard = z.object({
  ward_id: z.string(),
  name: z.string(),
  pm25_p50: z.number(),
  pm25_p90: z.number(),
  subindex24h: z.number(),
  category: aqiCategory,
  confidence,
});
export type NowcastWard = z.infer<typeof nowcastWard>;

export const nowcast = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  grid_meta: gridMeta,
  grid: z.array(gridCell),
  wards: z.array(nowcastWard),
});
export type Nowcast = z.infer<typeof nowcast>;

/* ---- forecast.json ---- */

export const forecastPoint = z.object({
  h: z.number().int(),
  pm25_p50: z.number(),
  pm25_p90: z.number(),
  subindex24h: z.number(),
  category: aqiCategory,
  confidence,
});
export type ForecastPoint = z.infer<typeof forecastPoint>;

export const forecastWard = z.object({
  ward_id: z.string(),
  name: z.string(),
  series: z.array(forecastPoint),
});
export type ForecastWard = z.infer<typeof forecastWard>;

export const forecast = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  horizons_h: z.array(z.number().int()),
  wards: z.array(forecastWard),
});
export type Forecast = z.infer<typeof forecast>;

/* ---- attribution.json ---- */

export const attributionShares = z.object({
  traffic: z.number(),
  industry: z.number(),
  biomass: z.number(),
  dust: z.number(),
  residential_other: z.number(),
});
export type AttributionShares = z.infer<typeof attributionShares>;

export const attributionWard = z.object({
  ward_id: z.string(),
  shares: attributionShares,
  confidence,
  method_notes: z.string(),
});
export type AttributionWard = z.infer<typeof attributionWard>;

export const attribution = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  wards: z.array(attributionWard),
});
export type Attribution = z.infer<typeof attribution>;

/* ---- enforcement.json ---- */

export const enforcementItem = z.object({
  ward_id: z.string(),
  source_label: sourceLabel,
  confidence,
  priority_score: z.number(),
  evidence: z.object({
    trend_72h: z.array(z.number()),
    persistence_days: z.number().int(),
    exceedance_pct: z.number(),
  }),
  action: enforcementAction,
});
export type EnforcementItem = z.infer<typeof enforcementItem>;

export const enforcement = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  ranked: z.array(enforcementItem),
});
export type Enforcement = z.infer<typeof enforcement>;

/* ---- advisories.json ---- */

export const advisoryWard = z.object({
  ward_id: z.string(),
  risk_level: riskLevel,
  langs: z.object({
    en: z.string(),
    hi: z.string(),
    regional: z.string().optional(),
  }),
});
export type AdvisoryWard = z.infer<typeof advisoryWard>;

export const advisories = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  wards: z.array(advisoryWard),
});
export type Advisories = z.infer<typeof advisories>;

/* ---- interventions.json (Delhi flagship, spec §13) ---- */

export const grapCalendarEntry = z.object({
  stage: grapStage,
  start_utc: z.string(),
  end_utc: z.string().nullable().optional(),
  source_url: z.string(),
});
export type GrapCalendarEntry = z.infer<typeof grapCalendarEntry>;

export const ribbonPoint = z.object({
  ts_utc: z.string(),
  pm25_raw: z.number(),
  pm25_normalized: z.number(),
  pm25_normalized_p90: z.number().optional(),
});
export type RibbonPoint = z.infer<typeof ribbonPoint>;

export const stageEffect = z.object({
  stage_transition: z.string(),
  effect_ugm3: z.number(),
  ci_low: z.number(),
  ci_high: z.number(),
  placebo_pass: z.boolean(),
  n_days: z.number().int(),
  method_notes: z.string(),
});
export type StageEffect = z.infer<typeof stageEffect>;

export const interventions = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  calendar: z.array(grapCalendarEntry).min(1),
  series: z.array(ribbonPoint).min(1),
  effects: z.array(stageEffect),
});
export type Interventions = z.infer<typeof interventions>;

/* ---- ledger.json (Delhi flagship, spec §13/§16/§17) ---- */

export const ledgerTotals = z.object({
  avoided_exposure_pugh: z.number(),
  avoided_deaths: z.number(),
  ci_low: z.number(),
  ci_high: z.number(),
});
export type LedgerTotals = z.infer<typeof ledgerTotals>;

export const ledgerWard = z.object({
  ward_id: z.string(),
  avoided_exposure_pugh: z.number(),
  avoided_deaths: z.number(),
  ci_low: z.number(),
  ci_high: z.number(),
  effect_ugm3: z.number(),
  effect_ci_low: z.number(),
  effect_ci_high: z.number(),
  by_stage: z
    .array(z.object({ stage_transition: z.string(), effect_ugm3: z.number() }))
    .optional(),
});
export type LedgerWard = z.infer<typeof ledgerWard>;

export const counterfactual = z.object({
  scenario: z.string(),
  shift_hours: z.number().int(),
  delta_exposure: z.number(),
  delta_deaths: z.number(),
  ci_low: z.number(),
  ci_high: z.number(),
});
export type Counterfactual = z.infer<typeof counterfactual>;

export const citation = z.object({ label: z.string(), url: z.string() });
export type Citation = z.infer<typeof citation>;

export const ledger = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  totals: ledgerTotals,
  wards: z.array(ledgerWard),
  counterfactuals: z.array(counterfactual),
  citations: z.array(citation).min(1),
  assumptions: z.array(z.string()).optional(),
});
export type Ledger = z.infer<typeof ledger>;

/* ---- receipts.json (global) ---- */

export const cvBucket = z.object({
  dist_km: z.number(),
  model_rmse: z.number(),
  idw_rmse: z.number(),
  n: z.number().int(),
});
export type CvBucket = z.infer<typeof cvBucket>;

export const forecastMetric = z.object({
  rmse: z.number(),
  mae: z.number(),
  persistence_rmse: z.number(),
  seasonal_naive_rmse: z.number(),
  skill_pct: z.number(),
  n: z.number().int(),
  embargo_h: z.number().int(),
});
export type ForecastMetric = z.infer<typeof forecastMetric>;

export const directionalCheck = z.object({
  check_name: z.string(),
  expected: z.union([z.string(), z.number()]),
  observed: z.union([z.string(), z.number()]),
  pass: z.boolean(),
  notes: z.string().optional(),
});
export type DirectionalCheck = z.infer<typeof directionalCheck>;

export const ablation = z.object({
  note: z.string().optional(),
  metric: z.string().optional(),
  with_sat: z.number().optional(),
  without_sat: z.number().optional(),
  delta_pct: z.number().optional(),
});
export type Ablation = z.infer<typeof ablation>;

export const receiptsCity = z.object({
  nowcast_cv: z
    .object({ baseline: z.string(), buckets: z.array(cvBucket) })
    .optional(),
  forecast: z.record(z.string(), forecastMetric).optional(),
  attribution_directional_checks: z.array(directionalCheck).optional(),
  ablation: ablation.optional(),
  intervention_assumptions: z.array(z.string()).optional(),
});
export type ReceiptsCity = z.infer<typeof receiptsCity>;

export const aqiBreakpoint = z.object({
  pollutant: z.string(),
  unit: z.string(),
  category: aqiCategory,
  conc_low: z.number(),
  conc_high: z.number(),
  index_low: z.number(),
  index_high: z.number(),
  extrapolated: z.boolean(),
});
export type AqiBreakpoint = z.infer<typeof aqiBreakpoint>;

export const receiptsMethodology = z.object({
  headline_label: z.string().optional(),
  severe_note: z.string().optional(),
  aqi_breakpoints: z.array(aqiBreakpoint).optional(),
});
export type ReceiptsMethodology = z.infer<typeof receiptsMethodology>;

export const receiptsLedger = z.object({
  novelty_statement: z.string(),
  prior_art: z.array(citation),
  method_citations: z.array(
    z.object({ label: z.string(), url: z.string(), used_for: z.string().optional() }),
  ),
});
export type ReceiptsLedger = z.infer<typeof receiptsLedger>;

export const lineageEntry = z.object({
  source: z.string(),
  base_url: z.string(),
  resource_id: z.string(),
  fetched_at: z.string(),
  rows: z.number().int(),
});
export type LineageEntry = z.infer<typeof lineageEntry>;

export const receipts = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  honesty_notes: z.array(z.string()),
  methodology: receiptsMethodology.optional(),
  ledger: receiptsLedger.optional(),
  cities: z.record(z.string(), receiptsCity),
  lineage: z.array(lineageEntry),
});
export type Receipts = z.infer<typeof receipts>;

/* ---- replay/index.json (per city) ---- */

export const replayIndex = z.object({
  city: z.string(),
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  window: z.object({ start: z.string(), end: z.string() }),
  dates: z.array(z.string()).min(1),
  note: z.string().optional(),
});
export type ReplayIndex = z.infer<typeof replayIndex>;

/* ---- briefs.json (per city; owner: vayu-agents, spec §14) ---- */

export const evidenceRef = z.object({
  label: z.string(),
  artifact: z.string(),
  path: z.string(),
  value: z.union([z.string(), z.number(), z.boolean(), z.null()]).optional(),
  resolved: z.boolean().optional(),
});
export type EvidenceRef = z.infer<typeof evidenceRef>;

export const actionBrief = z.object({
  id: z.string(),
  headline: z.string(),
  situation: z.string(),
  action: z.string(),
  action_code: enforcementAction.nullable().optional(),
  target_wards: z.array(z.string()),
  trigger_window: z.object({ start_utc: z.string(), end_utc: z.string() }),
  expected_effect: z
    .object({
      ugm3: z.number(),
      ci_low: z.number(),
      ci_high: z.number(),
      basis_ref: z.string().optional(),
    })
    .nullable(),
  owner: z.string(),
  advisory_langs: z.array(z.string()).optional(),
  evidence_refs: z.array(evidenceRef),
  ledger_ref: z
    .object({ stage_transition: z.string().optional(), scenario: z.string().optional() })
    .optional(),
  verifier: z.object({ passed: z.boolean(), notes: z.string().optional() }),
});
export type ActionBrief = z.infer<typeof actionBrief>;

export const briefs = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  stale: z.boolean().optional(),
  model: z.string().optional(),
  briefs: z.array(actionBrief),
});
export type Briefs = z.infer<typeof briefs>;

/* ---- agentlog.json (global; owner: vayu-agents) ---- */

export const agentRun = z.object({
  role: z.string(),
  city: z.string().optional(),
  model: z.string().optional(),
  reasoning_budget: z.union([z.string(), z.number()]).optional(),
  tokens_in: z.number().optional(),
  tokens_out: z.number().optional(),
  duration_ms: z.number().optional(),
  repairs: z.number().optional(),
});

export const agentLog = z.object({
  generated_at: z.string(),
  fixture: z.boolean().optional(),
  stale: z.boolean().optional(),
  model: z.string().optional(),
  runs: z.array(agentRun).optional(),
  totals: z
    .object({
      tokens_in: z.number().optional(),
      tokens_out: z.number().optional(),
      total: z.number().optional(),
      calls: z.number().optional(),
    })
    .optional(),
});
export type AgentLog = z.infer<typeof agentLog>;

/* ---- wards.geojson (owner: vayu-data) ---- */

export const wardProperties = z.object({
  ward_id: z.string(),
  name: z.string(),
  ward_code: z.string().optional(),
  population: z.number().nullable().optional(),
});
export type WardProperties = z.infer<typeof wardProperties>;

export const wardsGeojson = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: z.unknown(),
      properties: wardProperties,
    }),
  ),
});
