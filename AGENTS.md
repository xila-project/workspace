# Project Overview

This is the Xila **multi-repository workspace**: it orchestrates the public `xila-project` repositories as Git submodules under `repositories/`, provides shared CI tooling (composite actions, reusable workflows, pinned tool versions), and runs cross-repository integration checks against the exact pinned submodule revisions. It contains no product source code of its own. Each submodule stays independently buildable, releasable and responsible for its own unit tests, and has its own `AGENTS.md` where present — follow that file when working inside a submodule.

Layout:

- `repositories/<name>/`: Git submodules, one per active public repository (`core`, `platforms`, `applications`, `package_manager`, `packages`, `website`, `brand`, `wasm_application_template`, `.github`). Private and archived repositories are deliberately excluded.
- `mise.toml`: workspace tasks. `mise/shared.toml`: version pins in `[vars]` and the Cargo wrapper; consumer repositories may include it from a pinned workspace revision, so treat its variables as a public interface.
- `scripts/validate_workspace.py`: offline validation of `.gitmodules`, gitlinks and CI invariants.
- `scripts/integration/check.sh`: cross-repository Cargo graph resolution (`metadata`) and native/Wasm builds (`check`), using Platforms' `tools/dev/local_overrides.py` to patch Cargo dependencies to the local submodule sources.
- `.github/workflows/ci.yml`: the workspace's own gate (quality → integration → `required`).
- `.github/workflows/quality.yml`: reusable `workflow_call` workflow for consumer repositories; it calls `ci:format-rust`, `ci:format-toml` and `ci:lint-workflows`, which the **caller** must define.
- `.github/actions/setup-rust/`, `.github/actions/setup-node/`: reusable composite actions for consumer repositories.

## Repository responsibilities

| Repository | Owns |
|---|---|
| `core` | Kernel subsystems and reusable libraries. |
| `applications` | All native and Wasm applications, the Wasm host/guest API, the on-device `package` install executable, and building/publishing Wasm application packages. |
| `platforms` | Platform drivers, per-platform examples and the seeded filesystem image; it is the integration point that assembles everything. |
| `package_manager` | Single source of truth for package build, manifest, signing, verification and registry logic: `no_std` libraries, reusable packaging workflows and the desktop `xila-package` CLI, which should expose every such feature. |
| `packages` | apt-like package registry: per-version declarations (archives stay in releases), signed by the repository key, plus the published developer keys. |

## Dependency direction

`A ← B` means B depends on A.

```
core            ← applications, platforms
package_manager ← applications, platforms
applications    ← platforms
platforms       ← core, applications (dev-dependencies only, for tests)
```

- `core` must not depend on another Xila repository, except Platforms test drivers as dev-dependencies. Known exception to remove later: `core/libraries/firmware_update` uses `xila-package-verification`.
- `package_manager` is a leaf: it must not depend on any Xila repository, so every consumer can reuse its verification code without cycles.
- Put new signing, verification, manifest or registry logic in `package_manager` (library + CLI), not in scripts in other repositories.

## Package trust model

- **Developer (publisher) key** signs each `.xpk` manifest and its SHA-256 file inventory.
- **Repository key** signs registry entries (identifier, version, archive SHA-256 and size, authorized developer key) and the developer-key list in `packages`.
- Devices trust the repository key; installation verifies repository key → developer key → package signature → file hashes. Keep the two keys separate, and never treat a developer key as a trust anchor.

# Build & Test Commands

- Validate workspace structure (no network, no submodules needed): `mise run workspace:validate`
- Lint GitHub Actions workflows: `mise run ci:lint-workflows`
- Initialize all submodules: `mise run repositories:initialize`; only those needed for integration: `mise run repositories:initialize-runtime`
- Show pinned revisions: `mise run repositories:status`
- Advance submodules to their tracked `main`: `mise run repositories:update` (prints a submodule log diff for review)
- Install native Linux build packages (delegates to Platforms): `mise run ci:packages-integration`
- Install locked Node dependencies for Platforms and Applications: `mise run ci:node-dependencies`
- Resolve the cross-repository Cargo graph: `mise run integration:metadata`
- Full integration build: `mise run integration:check` (slow; native check plus Wasm release builds of the demo applications)

All task names use `<namespace>:<command>`. Tasks declare their own tools, so running a task installs only what it needs.

# Architecture & Implementation Guidelines

- **Ownership boundary.** The workspace owns orchestration, shared CI tooling and integration checks only. Firmware, filesystem images, Wasm demos, package content, app sources, issue/PR templates (in `xila-project/.github`) and the native package list (in Platforms' `mise.ci.toml`) belong to their own repositories. Do not duplicate them here; delegate instead.
- **Native packages.** Never add `apt-get` to workflows or a `[bootstrap] packages` table to `mise/shared.toml`. `ci:packages-integration` must keep delegating to `cd repositories/platforms && mise -E ci run ci:packages-host`. `validate_workspace.py` enforces this and also checks that the pinned Platforms revision still provides that task and the required packages.
- **Submodule rules** (enforced by `validate_workspace.py`): each path is `repositories/<name>`, its URL is exactly `https://github.com/xila-project/<name>.git`, it tracks `branch = main`, and `.gitmodules` and the tracked gitlinks match one-to-one. `core`, `platforms`, `applications`, `package_manager` and `packages` are required for integration. When adding or removing a repository, update `.gitmodules`, the gitlink, `REQUIRED` in the validator (if relevant), `repositories:initialize-runtime`, the CI checkout step and the README together.
- **Pinned, not floating.** CI validates the specific committed gitlink combination. Updating submodules only moves the local checkout; the gitlink change must be reviewed and committed in this repository. Never push to a submodule's remote as a side effect of workspace work.
- **Do not repin to unmerged commits.** A gitlink on `main` must point to a commit reachable from that submodule's `main`. Temporary pins to PR branches are acceptable only in a draft PR and must be repinned to the merged SHA before merge.
- **Versions.** Tool versions live in `[vars]` in `mise/shared.toml` and are referenced as `{{ vars.<name> }}`; do not hard-code versions in tasks or workflows. Pin GitHub Actions to explicit versions, and tell consumers to reference workspace actions and workflows by full commit SHA.
- **Workflow style.** Step names follow `"<Phase> | <Description>"` (e.g. `Setup | …`, `Validate | …`, `Lint | …`, `Test | …`, `Gate | …`). Keep `permissions: contents: read`, `persist-credentials: false` on checkout, and a `timeout-minutes` on every job. Run commands through `mise run` tasks rather than inline scripts.
- **Build cache.** The integration job runs raw `cargo` from a shell script, so the mr-boxington cache stays disabled there (`cache-enabled: "false"`); enabling it only helps once the commands go through the mise Cargo wrapper (`XILA_MBX=1`).
- **Validator changes.** `validate_workspace.py` must remain runnable without network access and without initialized submodules (checks that need a submodule run only when it is present).

# Non-Negotiables

- Keep `.superpowers/`, `.mise/`, `target/` and `.dev-environment/` out of Git.
- Before updating submodules, confirm none has uncommitted local work. Never reset or discard changes inside a submodule without asking.
- After editing workflows, `.gitmodules`, `mise.toml` or `mise/shared.toml`, run `mise run workspace:validate` and `mise run ci:lint-workflows`. After changing integration scripts or repinning runtime submodules, run at least `mise run integration:metadata`, and `integration:check` when feasible; report what was actually run.
- Make changes to submodule code in the submodule's own repository and through its own PR, following its `AGENTS.md`; the workspace only records the resulting gitlink.
- Do not reintroduce a Docker development image; the workspace is native mise only.
