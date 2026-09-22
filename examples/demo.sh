#!/usr/bin/env bash
# Deprecated reference example for new Claude Code integrations (2026-09-22).
set -euo pipefail
TOOL="$(cd "$(dirname "${BASH_SOURCE[0]}")/../bin" && pwd)/review-receipts"
fixture=$(mktemp -d "${TMPDIR:-/tmp}/review-receipts-demo.XXXXXX")
trap 'rm -rf -- "$fixture"' EXIT
trap 'exit 130' INT HUP TERM
mkdir "$fixture/project"
printf 'A bounded synthetic design.\n' > "$fixture/project/design.txt"
printf 'Review note: inspect the retry behavior.\n\n' > "$fixture/notes.txt"
"$TOOL" author --root "$fixture/project" --file design.txt --receipt "$fixture/review.json" \
  --reviewer 'Example reviewer' --label 'Design review' --verdict 'Needs changes' \
  --notes-file "$fixture/notes.txt" --evidence 'issue:example' --json >/dev/null
"$TOOL" check --root "$fixture/project" --file design.txt --receipt "$fixture/review.json" --json \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"]=="valid" and r["review"]["verdict"]=="Needs changes"'
printf 'Updated retry behavior.\n' >> "$fixture/project/design.txt"
if "$TOOL" check --root "$fixture/project" --file design.txt --receipt "$fixture/review.json" --json > "$fixture/stale.json"; then
  printf 'changed bytes incorrectly matched\n' >&2; exit 1
else
  [ "$?" -eq 3 ]
fi
python3 - "$fixture/stale.json" <<'PY'
import json,sys
with open(sys.argv[1]) as source:
    result=json.load(source)
assert result["status"]=="stale" and result["findings"][0]["path"]=="design.txt"
PY
printf 'PASS: review text retained, matching bytes recognized, changed bytes stale\n'
