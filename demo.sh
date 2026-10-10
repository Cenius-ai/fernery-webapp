#!/usr/bin/env bash
# Non-interactive, end-to-end demonstration of Fernery.
#
# Every command below is a real invocation of the tool; nothing is faked and
# nothing waits for input. The demo works inside a throwaway directory so it
# never touches your own fernery.json.

set -eu
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
# Prefer the console command installed by install.sh; fall back to the file.
if command -v fernery >/dev/null 2>&1; then
    FERNERY=(fernery)
else
    FERNERY=("$PYTHON" "$PWD/fernery.py")
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

banner() {
    echo
    echo "=============================================================="
    echo "$1"
    echo "=============================================================="
}

run() {
    echo "\$ fernery $*"
    "${FERNERY[@]}" "$@"
    echo
}

show_failure() {
    echo "\$ fernery $*"
    "${FERNERY[@]}" "$@" || echo "(exit code $?)"
    echo
}

banner "Fernery - one file, three plant logs, no network"
"${FERNERY[@]}" --version
echo
echo "Working in an empty directory: $WORK"

banner "1. The empty states name the command that fills them"
run frond list
run spore list
run rhizome list

banner "2. Frond unfurling tracker (five stages)"
run frond add --date 2026-01-04 --stage tight --notes "first crozier of the season"
run frond add --date 2026-01-18 --stage crook
run frond add --date 2026-02-02 --stage partly --notes "still tight at the base"
run frond add --date 2026-02-20 --stage unfurled --notes "midrib straight, pinnae even"
run frond add --date 2026-03-06 --stage flat --notes "fully hardened; ready for the reference book"
run frond list

banner "3. Spore print index (eight print colours)"
run spore add --species "Dryopteris filix-mas" --date 2026-02-11 --color brown --notes "print on white cartridge paper"
run spore add --species "Asplenium scolopendrium" --date 2026-02-15 --color cream --notes "spores shed overnight"
run spore add --species "Polystichum setiferum" --date 2026-02-22 --color rust --notes "warm rust, no green tint"
run spore list

banner "4. Rhizome division log, with a per-plant filter"
run rhizome add --plant "Bird's Nest" --date 2026-02-08 --divisions 3 --notes "three eyes, all firm"
run rhizome add --plant "Hart's Tongue" --date 2026-02-10 --divisions 1
run rhizome add --plant "Bird's Nest" --date 2026-03-01 --divisions 2 --notes "second round after repotting"
run rhizome list
run rhizome list --plant "Hart's Tongue"
run rhizome list --plant "Maidenhair"

banner "5. Rejections are one line, name the value, and exit non-zero"
show_failure frond add --date 2026-01-01 --stage half-open
show_failure spore add --species Amanita --date 2026-01-01 --color teal
show_failure rhizome add --plant A --date 2026-01-01 --divisions 0
show_failure rhizome add --plant A --date 2026-02-30 --divisions 1

banner "6. Scriptable output: records on stdout, --json for tooling"
run frond list --json

banner "7. The whole state is one readable file"
echo "\$ cat fernery.json"
head -n 24 "$WORK/fernery.json"
echo "..."
echo
"$PYTHON" - <<'PY'
import json
with open("fernery.json", encoding="utf-8") as handle:
    store = json.load(handle)
print("fronds:", len(store["fronds"]),
      " spores:", len(store["spores"]),
      " rhizomes:", len(store["rhizomes"]))
PY

banner "Done - the demo ran fully offline and left your own logs untouched"
