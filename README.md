# VayuDrishti

### Did the pollution emergency actually work? Now you can check.

When Delhi's air turns toxic, the city triggers GRAP emergency measures: bans,
shutdowns, restrictions. Every winter, the same question goes unanswered. Did any
of it help? By how much? Which wards? What if it had started two days sooner?

VayuDrishti answers that. It is the first operational system that audits, ward by
ward and weather-adjusted, whether a city's emergency pollution measures actually
worked, and estimates what acting earlier would have saved in exposure and in
lives. Built on open data, with a receipt behind every number.

Live demo: **TBD** &nbsp;·&nbsp; The receipts: **TBD/receipts** &nbsp;·&nbsp; The pitch: **TBD/pitch**
<!-- URLs filled at integration once Vercel is wired -->

---

## The Intervention Ledger

This is the capability nobody else deploys. Academic teams have evaluated single
GRAP seasons in retrospect, city-wide. Forecasting systems predict tomorrow's air.
No fielded system does a continuous, ward-level, causal audit of the measures with
a mortality counterfactual. VayuDrishti does, and it shows its work:

1. **Weather normalization**: we strip out the weather so a wet week cannot be
   mistaken for a policy win (Grange and Carslaw meteorological normalization).
2. **Real intervention calendar**: every GRAP stage change from actual CAQM
   orders, each date carrying its source link. Zero invented dates.
3. **Causal effect**: an event study around each stage change on the
   weather-neutral series, with placebo tests on matched high-pollution days and
   bootstrap confidence intervals.
4. **Health translation**: GEMM exposure-response curves and WorldPop population
   turn avoided pollution into avoided premature deaths, per ward, with intervals.
5. **Timing engine**: shift a stage two days earlier in the model and read off the
   change in exposure and lives.

The demo line: "GRAP Stage III saved an estimated **TBD** lives in northwest Delhi.
Acting 48 hours earlier would have saved **TBD** more." Every figure is labeled a
modeled estimate, carries a confidence interval, and lists its assumptions.
<!-- Ledger numbers filled at integration from ledger.json -->

If a stage shows no measurable effect, the Ledger says so. A null finding on
public spending is itself a result worth publishing.

## The platform underneath

The Ledger stands on a full air-quality stack, each layer honest about its limits:

- **Nowcast**: fills the space between stations on a 1 km grid, with uncertainty bands, never invented numbers.
- **Forecast**: 24, 48, and 72 hour outlook at the ward level, the unit an officer can act on.
- **Source attribution**: a labeled estimate of what drives each ward's pollution, confidence stated.
- **Enforcement queue**: wards ranked by measured exceedance, trend, and who is exposed, each with evidence.
- **Advisories**: ward guidance in Indian languages, generated at publish time, safe to render as plain text.

## Reasoning agents, cited briefs

On top of the numbers sits a reasoning layer powered by NVIDIA Nemotron. It turns
the intelligence into verified, evidence-cited action briefs: for a priority ward
it drafts what to act on, why, and the exact measured signals behind it, each claim
linked back to the data it came from. The agents run at publish time, and the brief
step is best-effort by design, so a model hiccup never blocks the data refresh. No
brief invents a number; every figure traces to a receipt.

## Receipts, not vibes

Air quality dashboards are a crowded field. Our difference is honesty you can
check. Open `/receipts` and every model claim carries its validation number:

- Delhi 24h forecast skill vs persistence: **TBD** (rolling-origin backtest, embargo stated)
- Delhi nowcast vs IDW baseline, by distance to nearest station: **TBD**
- GRAP stage effects: weather-normalized, with placebo pass or fail per stage: **TBD**
- Training window: February 2025 to now, one winter. We say so, and scope every claim to it.
<!-- metrics filled at integration from receipts.json / interventions.json -->

## Science you can check

We do not hand you one number and hope. Every cell is estimated by four
independent methods: inverse-distance, kriging, a satellite AOD-to-PM model, and
gradient boosting. They are combined by a stacked model, with a disagreement index
that shows where the methods argue. Where they agree, trust it; where they
diverge, we say so.

- Validated against a network we never trained on: US embassy PM2.5 monitors, held out entirely. Error and bias per city on `/receipts`: **TBD**.
- Calibrated, and honest when it is not: the p50 to p90 band is checked against how often it actually covers, with a reliability diagram.
- A GRAP trigger watchdog: the probability of crossing each emergency stage in the next 48 hours, joined to the ledger's measured effect for that stage and a pre-positioning window. Forecast, trigger, effect, action, in one line.
- Fifteen satellite platforms feed the models, from Sentinel-5P to MODIS to VIIRS, with hourly geostationary coverage where keys allow.
<!-- numbers filled at integration from receipts.json -->

Full method equations, assumptions, and citations live on `/methods`, and the
hourly ensemble grid is downloadable for researchers to reuse.

## Three cities, one YAML away from more

- **Delhi**: the deep build. Every surface, the Ledger, full receipts, offline replay.
- **Mumbai**: the standard build. Nowcast, forecast, advisories, validated.
- **Bengaluru**: config only, live. The pipeline runs and the JSONs publish from a single city YAML. Adding a city is a config change, not a rewrite.

## Every number is real

No synthetic data. Gaps are filled by models with labels and error bars, never by
guesses dressed as facts. Sources, all free and public: OpenAQ S3 archive (CPCB
hourly history), data.gov.in CPCB live snapshot, Open-Meteo weather, NASA FIRMS
fire detections, NASA GIBS satellite overlays, Google Earth Engine numeric
satellite features and WorldPop population, OSM and Datameet ward boundaries.

## Architecture in one line

A `uv`-based `vayu` pipeline fetches, models, and publishes static JSON; a Next.js
static site on Vercel reads it at the edge; GitHub Actions refreshes the data every
six hours behind a content gate. Full diagram and decisions:
[docs/architecture.md](docs/architecture.md).

## Run it

```bash
# pipeline (Python, uv)
cd pipeline
cp ../.env.example ../.env   # add your free API keys, see comments in the file
uv run vayu publish --city delhi

# web (Next.js, pnpm)
cd web
pnpm install
pnpm dev
```

After cloning, run `sh scripts/setup.sh` once to activate the local git hooks: a
non-bypassable secret scan and a prose humanizer on push. CI enforces the same
gates regardless, so this is only for faster local feedback.

## Deploy

The web app is a static export served by Vercel with Cloudflare in front. Security
headers live in `web/vercel.json`. The scheduled refresh runs in GitHub Actions,
pinned by commit SHA, with secrets masked and a demo-freeze toggle for finale day.

## For judges

Open the Ledger first. In 30 seconds it makes the argument: a real emergency, a
weather-adjusted effect, a lives-saved counterfactual, every number sourced. Then
open `/receipts` for the validation, switch cities, and watch a new city appear
from one config file.
