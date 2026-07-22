#!/usr/bin/env sh
# One-time developer setup after cloning: activate the committed git hooks.
# core.hooksPath is a LOCAL git setting (not committed), so a fresh clone has the
# hooks committed but inactive until this runs. CI enforces the same gates
# regardless, so this is only for local fast feedback. Idempotent.
set -eu
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
git config core.hooksPath .githooks
chmod +x .githooks/* scripts/*.sh 2>/dev/null || true
echo "VayuDrishti hooks active: core.hooksPath=.githooks"
echo "  pre-push  : secret scan (non-bypassable) then humanizer prose gate"
echo "  commit-msg: humanizer on the commit message"
echo "Bypass the humanizer once with: HUMANIZE_SKIP=1 git push"
