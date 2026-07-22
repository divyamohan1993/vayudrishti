# Changelog

All notable changes to VayuDrishti are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); grouped by date.

## [Unreleased]

### Added

- 2026-07-23 Agentic Actionable-Inference layer (spec 14, vayu-agents):
  - `config/schemas/briefs.schema.json` + `agentlog.schema.json`: the Action-Brief
    envelope (verified, evidence-cited) and the redacted transparency trace, frozen
    and validated. A `brief_type` field carries the spec 15 Depth-Pack types.
  - `pipeline/vayu/agents/`: the Nemotron NIM client (thinking-mode trace parse, tool
    calling), the deterministic dotted-path evidence resolver, eight read-only
    artifact tools, the compound-risk digest, and the four-role loop (Situation
    Analyst, Causal Strategist, Action Drafter, Adversarial Verifier) behind a
    bounded call budget with a two-repair gate.
  - `vayu briefs --city X`: builds verified briefs from published artifacts; any
    model failure keeps the previous briefs (stale banner) and exits zero, never
    blocking publish. A publish-time gate greps every emitted file for `</think>`
    and NVIDIA key material.
  - Sample `briefs.json` + `agentlog.json` published as fixtures for the web panel.
  - Every number in a brief resolves against a published artifact or its ref is
    pruned; the point effect and its confidence interval are grounded from the
    Intervention Ledger row. Verified live against Nemotron.

- 2026-07-23 Scientific Depth Pack alignment (spec v5, vayu-ops):
  - `.env.example`: optional expansion slots `GEMS_API_CREDENTIALS` (NIER),
    `MOSDAC_CREDENTIALS` (INSAT), and `AIRNOW_API_KEY` (embassy-validation
    fallback), each documented as optional so absence never blocks the pipeline.
  - `refresh.yml`: the publish step logs wall-clock time and warns past the
    15-minute budget.
  - `README.md` and `docs/demo-video-script.md`: the ensemble-of-methods estimate,
    validation against an independent network never trained on, the GRAP trigger
    watchdog, and the 15-platform satellite tier, all with placeholder numbers.
  - Secret scan and `.gitleaks.toml` now allowlist test directories, since the
    security unit tests embed fake token shapes on purpose. Published data and the
    built bundle stay fully scanned.
  - `refresh.yml`: added the reasoning-agents step `vayu briefs --city all` between
    publish and the gate, non-blocking with a 10-minute timeout, so the gate also
    validates `briefs.json` and `agentlog.json` and a Nemotron outage never blocks
    the refresh. Job timeout raised to 40 minutes.
  - Humanizer file scan (pre-push and CI) now excludes `web/public/data/**`, since
    those are model-generated data outputs gated by the content gate, not prose.

- 2026-07-22 Operations foundation (vayu-ops):
  - `refresh.yml`: scheduled data refresh every six hours plus manual dispatch.
    Job-level demo-freeze skip via the `DEMO_FREEZE` repository variable. GEE
    service-account key decoded to a restricted temp file with masked log output.
    Runs `vayu publish` then a required `vayu gate` content check, then a secret
    scan, then a first-party commit of only `web/public/data/**`. Every action
    pinned to a full commit SHA. Sole permission is `contents: write`.
  - `ci.yml`: parallel checks on every push and pull request. Secret scan with a
    pinned gitleaks over tree and history, humanizer prose gate, pipeline lint,
    type check, tests, and a must-fail step asserting the content gate rejects a
    poisoned fixture, plus web lint and build. Language jobs skip until their
    subtree lands.
  - `scripts/secret-scan.sh`: query-string key detection, FIRMS path-key
    detection, credential-format detection (PEM, Google, AWS, GitHub, JWT, and
    NVIDIA `nvapi-` keys) over published JSON, the built `web/out` bundle, and the
    tracked tree, plus a checksum-pinned gitleaks pass (config-driven allowlist)
    over the tree and full history in CI. Verified against planted leaks and a
    real gitleaks run (148 dependency false-positives to 0 with the config).
  - `.gitleaks.toml`: allowlists dependencies, build output, the local `.env`,
    and test fixtures so gitleaks flags only genuine leaks.
  - `scripts/setup.sh`: one-time hook activation after clone.
  - `.humanize-allow`: allowlists `robust` (a statistics term here) for the
    humanizer.
  - `.githooks/pre-push`: combined gate. A non-bypassable secret scan, then the
    humanizer prose check with `HUMANIZE_SKIP=1` as the recorded escape hatch.
    Wired through local `core.hooksPath`.
  - `.githooks/commit-msg`: humanizer gate on the commit message itself, scanning
    only the message. Same bypass and Node-free fallback.
  - `.humanize/`: the humanizer guard and fixer that block unicode dashes and
    AI-tell phrasing in shipped prose. Degrades to a dash-only check without Node.
  - `web/vercel.json`: static-export deploy config with all security headers,
    HSTS, `nosniff`, frame denial, referrer policy, a scoped permissions policy,
    and a strict Content-Security-Policy that enumerates the GIBS tile hosts.
  - `.env.example`: all source keys with registration links, including
    `NVIDIA_API_KEY` for the Nemotron reasoning agents, the two GEE credential
    paths, `GEE_PROJECT`, and the authoritative `VAYU_WEB_DATA_DIR` and
    `VAYU_DATA_DIR` paths.
  - `.gitattributes`: forces LF on scripts, hooks, and CI files so Windows
    checkouts do not break shell scripts on Linux runners.
  - `README.md`: leads with the Intervention Ledger, then the platform, the
    reasoning-agent briefs, and the receipts.
  - `docs/architecture.md`: system diagram and the security, refresh, Ledger, and
    reasoning-agent data flows.
  - `docs/demo-video-script.md`: three-minute script, Ledger first.

### Notes

- Metric placeholders in the README and demo script are filled at integration
  from `receipts.json`, `interventions.json`, and `ledger.json`. No invented
  numbers ship.
- Security header ownership sits entirely in `web/vercel.json`; the Next.js config
  emits none, since a static export ignores framework headers.
