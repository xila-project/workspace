#!/usr/bin/env bash
# Integration of the exact Git submodule revisions, not arbitrary branch heads.
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
platforms="$workspace_root/repositories/platforms"
applications="$workspace_root/repositories/applications"
core="$workspace_root/repositories/core"
tools="$workspace_root/repositories/tools"
package_manager="$workspace_root/repositories/package_manager"

for repository in "$platforms" "$applications" "$core" "$tools" "$package_manager"; do
  if [[ ! -f "$repository/Cargo.toml" ]]; then
    echo "Missing initialized submodule: $repository" >&2
    echo "Run: mise run repositories:initialize-runtime" >&2
    exit 1
  fi
done

# Pick the Cargo front end the way the mise `[wrappers.cargo]` does: mr-boxington
# when XILA_MBX=1 (set by the setup-rust action when the cache is enabled), plain
# Cargo otherwise, so the build cache applies to every command below.
cargo() {
  if [[ "${XILA_MBX:-0}" == "1" ]]; then
    MBX_CARGO_SHIM_MODE=1 command mbx "$@"
  else
    command cargo "$@"
  fi
}

mode="${1:-metadata}"
if [[ "$mode" != "metadata" && "$mode" != "check" ]]; then
  echo "Usage: $0 [metadata|check]" >&2
  exit 2
fi

workdir="$(mktemp -d)"
# Local source patches make Cargo rewrite each checkout's lockfile; restore
# them so an integration run never leaves the submodules modified.
for repository in "$platforms" "$applications" "$tools"; do
  cp "$repository/Cargo.lock" "$workdir/$(basename "$repository").Cargo.lock"
done
restore() {
  for repository in "$platforms" "$applications" "$tools"; do
    cp "$workdir/$(basename "$repository").Cargo.lock" "$repository/Cargo.lock"
  done
  rm -rf "$workdir"
}
trap restore EXIT
patch="$workdir/xila-local.toml"
python3 "$platforms/tools/dev/local_overrides.py" \
  --core "$core" --platforms "$platforms" --applications "$applications" \
  --tools "$tools" --package-manager "$package_manager" --output "$patch"

# Platforms assembles every other repository; the tools workspace also builds
# the `xila` command line, which Platforms does not link.
for repository in "$platforms" "$tools"; do
  (
    cd "$repository"
    cargo metadata --config "$patch" --format-version 1 > "$workdir/metadata.json"
  )
  python3 - "$workdir/metadata.json" "$(basename "$repository")" <<'PY'
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
    raise SystemExit(sys.argv[2] + ": duplicate Xila package identities: " + repr(duplicates))
print(sys.argv[2] + ": Cargo dependency graph resolves without duplicate Xila package identities")
PY
done

if [[ "$mode" == "check" ]]; then
  (
    cd "$platforms"
    # xila-fs-image builds images with the tools library.
    cargo check --config "$patch" -p xila-native-example -p xila-fs-image
  )
  (
    cd "$tools"
    cargo check --config "$patch" --workspace
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
