#!/usr/bin/env sh
# secret-scan: one gate, run identically by the pre-push hook and by CI.
# Acceptance 7: no keys in the bundle, repo history, or published JSONs.
#
# Two layers, defence in depth:
#   1. Custom pattern grep (zero deps, always runs). Targets the leak the design
#      warns about: data.gov.in puts its key in the query string, so any secret
#      named query param in web/public/data/**.json is a hard fail, plus known
#      credential formats (PEM keys, Google/AWS keys, GitHub tokens, JWTs, the
#      GEE service-account JSON fields, FIRMS map key baked into a path).
#   2. gitleaks (SHA/checksum-pinned, run when present). Broad rule + entropy
#      net over the working tree and, in CI, the whole commit history.
#
# Degrades gracefully: if grep or the shell lack a feature we still fail closed
# on the custom patterns. Missing gitleaks is a warning, never a hard error, so
# a developer without it can still push (CI runs the pinned binary regardless).
#
# Usage:
#   scripts/secret-scan.sh              scan working tree + published JSONs
#   SCAN_HISTORY=1 scripts/secret-scan.sh   also scan git history via gitleaks
#
# Exit 0 = clean, exit 1 = a secret was found (or a scan error we refuse to skip).
set -u

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT" || exit 1
DATA_DIR="web/public/data"
FAIL=0

red()  { printf '\033[31m%s\033[0m\n' "$1"; }
grn()  { printf '\033[32m%s\033[0m\n' "$1"; }
yel()  { printf '\033[33m%s\033[0m\n' "$1"; }

# --- Layer 1a: published-data JSON scan (the acceptance-7 core) ---------------
# Query-string secrets: ?api-key=... &token=... etc. Nothing keyed should ever
# reach published data; lineage stores base_url + resource_id only.
QS_PAT='[?&](api[_-]?key|apikey|access[_-]?token|auth|map[_-]?key|key|token|secret|password|passwd|pwd)=[^&"'"'"' 	]{6,}'
# FIRMS bakes its MAP_KEY into the URL path, not a query string.
FIRMS_PAT='firms\.modaps\.eosdis\.nasa\.gov/api/[a-z_]+/(csv|kml|shp|json)/[0-9A-Za-z]{16,}'
# GEE service-account JSON fields leaking into published data.
GSA_PAT='"(private_key|private_key_id|client_secret)"[[:space:]]*:'
# Bare credential formats that must never appear in published data OR the tree:
# PEM key blocks, Google/AWS keys, GitHub tokens, JWTs, NVIDIA NIM (nvapi-) keys.
CRED_FMT='-----BEGIN[A-Z ]*PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|(ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{30,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}|nvapi-[A-Za-z0-9_-]{20,}'

scan_data() {
  [ -d "$DATA_DIR" ] || { yel "secret-scan: no $DATA_DIR yet (skipping data scan)."; return 0; }
  # Capture each grep separately (a piped `| head` would mask grep's exit code and
  # its empty output, so test the captured text for emptiness instead).
  # -I skip binary, -n line numbers, -E extended, -r recursive, -o match-only (redacts context).
  hits=$(
    grep -rInoE -e "$QS_PAT"    --include='*.json' "$DATA_DIR" 2>/dev/null
    grep -rInoE -e "$FIRMS_PAT" --include='*.json' "$DATA_DIR" 2>/dev/null
    grep -rInE  -e "$GSA_PAT"   --include='*.json' "$DATA_DIR" 2>/dev/null
    grep -rInoE -e "$CRED_FMT"  --include='*.json' "$DATA_DIR" 2>/dev/null
  )
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | head -n 40
    red "secret-scan: SECRET-SHAPED CONTENT in published JSON ($DATA_DIR). Strip query strings; publish base_url + resource_id only."
    FAIL=1
  fi
}

# --- Layer 1c: built web bundle scan (acceptance 7: no keys in the bundle) ----
# Only runs after a build (web/out exists). Catches a secret inlined into the
# client JS/HTML, e.g. a NEXT_PUBLIC_ slip. Scans .js/.html/.json for query-string
# keys and bare credential formats (incl. nvapi- and JWTs).
BUNDLE_DIR="${VAYU_BUNDLE_DIR:-web/out}"
scan_bundle() {
  [ -d "$BUNDLE_DIR" ] || return 0
  hits=$(
    grep -rInoE -e "$QS_PAT"   --include='*.js' --include='*.html' --include='*.json' "$BUNDLE_DIR" 2>/dev/null
    grep -rInoE -e "$CRED_FMT" --include='*.js' --include='*.html' --include='*.json' "$BUNDLE_DIR" 2>/dev/null
  )
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | head -n 40
    red "secret-scan: SECRET-SHAPED CONTENT in the built bundle ($BUNDLE_DIR). A key was inlined into the client."
    FAIL=1
  fi
}

# --- Layer 1b: credential-format scan across the tracked tree ----------------
# Catches a key committed ANYWHERE, not only in data. Case-sensitive formats.
# Only git-TRACKED files are scanned here, so the gitignored .env (where real
# local secrets legitimately live) is never flagged. .env.example (dummy values)
# is excluded too. PEM key blocks, Google/AWS keys, GitHub tokens, JWTs.
scan_tree() {
  CRED="$CRED_FMT"
  # -e guards against the pattern's leading '-----' being parsed as grep options.
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    hits=$(git grep -InE -e "$CRED" -- . \
      ':(exclude).env.example' ':(exclude)scripts/secret-scan.sh' \
      ':(exclude)*.lock' ':(exclude)pnpm-lock.yaml' ':(exclude)uv.lock' 2>/dev/null)
  else
    EXC_DIR='--exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=out --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=.vercel'
    EXC_FILE='--exclude=.env --exclude=.env.* --exclude=secret-scan.sh --exclude=*.lock --exclude=pnpm-lock.yaml --exclude=uv.lock'
    # shellcheck disable=SC2086
    hits=$(grep -rInE $EXC_DIR $EXC_FILE -e "$CRED" . 2>/dev/null)
  fi
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | head -n 40
    red "secret-scan: CREDENTIAL-SHAPED STRING in a tracked file. Remove it, rotate the key."
    FAIL=1
  fi
}

# --- Layer 2: gitleaks (pinned binary when available) ------------------------
# .gitleaks.toml allowlists deps, build output, the local .env, and test
# fixtures. Scans are scoped so gitleaks never crawls node_modules locally.
scan_gitleaks() {
  if ! command -v gitleaks >/dev/null 2>&1; then
    yel "secret-scan: gitleaks not on PATH (custom grep still ran). CI runs the pinned binary."
    return 0
  fi
  CFG=""
  [ -f "$ROOT/.gitleaks.toml" ] && CFG="--config=$ROOT/.gitleaks.toml"
  # Published data may be uncommitted at publish time: scoped dir scan (fast).
  if [ -d "$DATA_DIR" ] && gitleaks dir --help >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    gitleaks dir "$DATA_DIR" $CFG --no-banner --redact || { red "secret-scan: gitleaks flagged published data ($DATA_DIR)."; FAIL=1; }
  fi
  # Full history + tracked tree (git-aware: skips untracked node_modules/.venv).
  # Deep mode only (CI passes SCAN_HISTORY=1). 'git' subcommand is gitleaks v8.19+.
  if [ "${SCAN_HISTORY:-0}" = "1" ]; then
    if gitleaks git --help >/dev/null 2>&1; then
      # shellcheck disable=SC2086
      gitleaks git . $CFG --no-banner --redact || { red "secret-scan: gitleaks flagged git history/tree."; FAIL=1; }
    else
      # shellcheck disable=SC2086
      gitleaks detect --source . $CFG --no-banner --redact || { red "secret-scan: gitleaks flagged history/tree."; FAIL=1; }
    fi
  fi
}

scan_data
scan_bundle
scan_tree
scan_gitleaks

if [ "$FAIL" -eq 0 ]; then grn "secret-scan: clean."; fi
exit "$FAIL"
