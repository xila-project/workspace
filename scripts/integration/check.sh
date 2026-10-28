#!/usr/bin/env bash
# Integration of the exact Git submodule revisions, not arbitrary branch heads.
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
platforms="$workspace_root/repositories/platforms"
applications="$workspace_root/repositories/applications"
core="$workspace_root/repositories/core"

for repository in "$platforms" "$applications" "$core"; do
  if [[ ! -f "$repository/Cargo.toml" ]]; then
    echo "Missing initialized submodule: $repository" >&2
    echo "Run: mise run repositories:initialize-runtime" >&2
    exit 1
  fi
done

mode="${1:-metadata}"
if [[ "$mode" != "metadata" && "$mode" != "check" ]]; then
  echo "Usage: $0 [metadata|check]" >&2
  exit 2
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
patch="$workdir/xila-local.toml"
python3 "$platforms/tools/dev/local_overrides.py" \
  --core "$core" --platforms "$platforms" --applications "$applications" --output "$patch"

(
  cd "$platforms"
  cargo metadata --config "$patch" --format-version 1 > "$workdir/metadata.json"
)
python3 - "$workdir/metadata.json" <<'PY'
import collections
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    metadata = json.load(handle)
sources = collections.defaultdict(set)
for package in metadata["packages"]:
    if package["name"] == "xila" or package["name"].startswith("xila-"):
        sources[package["name"]].add(package["id"])
duplicates = {name: ids for name, ids in sources.items() if len(ids) > 1}
if duplicates:
    raise SystemExit("Duplicate Xila package identities: " + repr(duplicates))
print("Cargo dependency graph resolves without duplicate Xila package identities")
PY

if [[ "$mode" == "check" ]]; then
  (
    cd "$platforms"
    cargo check --config "$patch" -p xila-native-example
  )
  (
    cd "$applications"
    cargo check --config "$patch" -p xila-command-line-shell --tests \
      --features xila/graphics_rendering_xrgb8888
    cargo build --config "$patch" --target wasm32-wasip1 \
      --profile release-wasm \
      -p xila-calculator -p xila-clock -p xila-weather \
      -p xila-pixel-painter -p xila-text-editor -p xila-synth
  )
fi
