# Project Overview

This is the Xila **multi-repository workspace**: it orchestrates the public `xila-project` repositories as Git submodules under `repositories/`, provides shared CI tooling (composite actions, reusable workflows, pinned tool versions), and runs cross-repository integration checks against the exact pinned submodule revisions. It contains no product source code of its own. Each submodule stays independently buildable, releasable and responsible for its own unit tests, and has its own `AGENTS.md` where present — follow that file when working inside a submodule.

Layout:

- `repositories/<name>/`: Git submodules, one per active public repository (`core`, `platforms`, `applications`, `package_manager`, `registry`, `tools`, `website`, `brand`, `media`, `package-action`, `wasm_application_template`, `native_c_application_template`, `native_rust_application_template`, `.github`). Private and archived repositories are deliberately excluded.
- `mise.toml`: workspace tasks. `mise/shared.toml`: version pins in `[vars]` and the Cargo wrapper; consumer repositories may include it from a pinned workspace revision, so treat its variables as a public interface.
- `scripts/validate_workspace.py`: offline validation of `.gitmodules`, gitlinks and CI invariants.
- `scripts/integration/check.sh`: cross-repository Cargo graph resolution of Platforms and `tools` (`metadata`) and native/Wasm builds, including the `xila` command line (`check`), using Platforms' `tools/dev/local_overrides.py` to patch Cargo dependencies to the local submodule sources.
- `.github/workflows/ci.yml`: the workspace's own gate (quality → integration → `required`).
- `.github/workflows/quality.yml`: reusable `workflow_call` workflow for consumer repositories; it calls `ci:format-rust`, `ci:format-toml` and `ci:lint-workflows`, which the **caller** must define, plus the optional `extra-task` input (a caller task such as `ci:quality-extra`). Consumers must pin it to a commit on workspace `main`: Actions cannot load a reusable workflow from a commit that is only on a deleted branch.
- `.github/actions/setup-rust/`, `.github/actions/setup-node/`: reusable composite actions for consumer repositories.

## Repository responsibilities

| Repository | Owns |
|---|---|
| `core` | Kernel subsystems and reusable libraries. |
| `applications` | All native and Wasm applications, the Wasm host/guest API, the on-device `package` install executable, and building/publishing Wasm application packages. |
| `platforms` | Platform drivers, per-platform examples and the seeded filesystem image; it is the integration point that assembles everything. |
| `package_manager` | Single source of truth for package build, manifest, signing, verification and registry logic: `no_std` libraries, reusable packaging workflows and the desktop `xila-package` CLI, which should expose every such feature. |
| `registry` | Package registry (metadata only, like `crates.io-index`): per-version registry entries generated from signed archives, which stay in each project's releases, plus the published developer keys; signed by the repository key. |
| `tools` | The `xila` developer command line (Cargo package `xila-tools`): image building and packaging. It provides the file system image engine library (`xila-tools-image`), which Platforms links so that images match the firmware's Core, and `xila package`, which embeds `package_manager`'s command line. Image data (profiles, shortcuts, repositories) stays in Platforms. |

## Dependency direction

`A ← B` means B depends on A.

```
core            ← applications, platforms, tools
package_manager ← applications, platforms, tools
applications    ← platforms
tools           ← platforms
platforms       ← core, applications (dev-dependencies only, for tests)
```

- `core` must not depend on another Xila repository, except Platforms test drivers as dev-dependencies. Known exception to remove later: the standalone CI probe `core/tools/verification_probe` (outside the Core Cargo workspace) pins `package_manager`'s verification crate; it belongs in `package_manager`.
- Cross-repository Cargo git dependencies use `branch = "main"`, never `rev` or `tag`; `Cargo.lock` holds the exact commit, CI builds with `--locked`, and repinning is `cargo update -p <crate>`. Every repository must use the same reference so Cargo unifies Core, Applications and package_manager instead of resolving duplicate copies. Workflows that check out a matching repository read the locked commit (`tools/ci/locked_revision.py`) instead of hard-coding it.
- `package_manager` is a leaf: it must not depend on any Xila repository, so every consumer can reuse its verification code without cycles.
- `tools` depends on Core and `package_manager` only, never on Platforms or Applications (Platforms consumes it).
- Put new signing, verification, manifest or registry logic in `package_manager` (library + CLI), not in scripts in other repositories.

## Package trust model

- **Developer (publisher) key** signs each `.xpk` manifest and its SHA-256 file inventory.
- **Repository key** signs registry entries (identifier, version, archive SHA-256 and size, authorized developer key) and the developer-key list in `registry`.
- Devices trust the repository key; installation verifies repository key → developer key → package signature → file hashes. Keep the two keys separate, and never treat a developer key as a trust anchor.

# Rules for every Xila repository

These apply in the workspace and in every submodule. A submodule's own `AGENTS.md` adds rules for that repository; when the two disagree, the submodule's file wins for code inside it.

| Repository | Instructions |
|---|---|
| `core` | [`core/AGENTS.md`](https://github.com/xila-project/core/blob/main/AGENTS.md) |
| `platforms` | [`platforms/AGENTS.md`](https://github.com/xila-project/platforms/blob/main/AGENTS.md) |
| `applications` | [`applications/AGENTS.md`](https://github.com/xila-project/applications/blob/main/AGENTS.md) |
| `package_manager` | [`package_manager/AGENTS.md`](https://github.com/xila-project/package_manager/blob/main/AGENTS.md) |
| `tools` | [`tools/AGENTS.md`](https://github.com/xila-project/tools/blob/main/AGENTS.md) |
| `website` | [`website/AGENTS.md`](https://github.com/xila-project/website/blob/main/AGENTS.md) |
| `brand` | [`brand/AGENTS.md`](https://github.com/xila-project/brand/blob/main/AGENTS.md) |
| `media` | [`media/AGENTS.md`](https://github.com/xila-project/media/blob/main/AGENTS.md) |
| `registry`, `package-action`, the application templates, `.github` | No file of their own: this file and their README apply |

- **Language.** Plain English in code, comments, documentation, commit messages, pull requests and issues. Spell words out in identifiers and text (`device`, not `dev`; `directory`, not `dir`; `configuration`, not `config`) unless an external API, format or existing path imposes the short form.
- **No tool attribution.** Commit messages, pull requests, issues, reviews, comments and documentation describe the change, never the tool or assistant that helped write it: no `Co-Authored-By` trailers for tools and no "Generated with" lines. Check `git log -1 --format=%B` after committing.
- **Commits and pull requests.** Conventional commit titles (`feat(scope): …`, `fix: …`, `docs: …`). One pull request per concern in each repository, against `main`, with green CI before merge; pull requests are squash-merged with the title as subject, unless the repository's own `AGENTS.md` defines another workflow (`media` commits directly to `main`). State in the description what was run to verify the change.
- **Cross-repository changes.** Land them upstream first, following the dependency direction above: Core and `package_manager`, then Applications and `tools`, then Platforms, then the workspace gitlinks. A downstream pull request stays a draft until the upstream one is merged, then relocks the lockfile with `cargo update -p <crate>` and builds with `--locked`.
- **Issues.** Track all work in issues; see [Issue tracking](#issue-tracking).
- **Compatibility.** Before 1.0, breaking changes are allowed: migrate or replace old formats and options instead of adding compatibility layers, and say so in the pull request. Never delete or rewrite published releases and tags.
- **Secrets and privacy.** Never commit secrets, local paths, device serial numbers, network names or personal data. Scripts take secret values from files passed as arguments and never print them.
- **Hardware.** Flashing and serial-port access to physical boards are done by the maintainer or a session they authorise, never by unattended automation.

## Issue tracking

Every bug, feature, follow-up, upstream problem and design decision gets an issue, even when it is fixed right away or deliberately left alone.

**Why.** Pull requests record what changed, not what was considered and rejected. Issues keep the reasoning: measurements, the options weighed, the tradeoffs and the conditions under which a choice should change. They let anyone:

- challenge a decision later, for example when an optimisation needs it, without measuring everything again;
- find the workaround to remove when an upstream fix lands;
- pick up paused work without the original context.

**What to file.**

- **Bugs and features:** in the repository that owns the code (see [Repository responsibilities](#repository-responsibilities)).
- **Follow-ups:** for review findings, deferred scope and known limitations left by a pull request, open an issue and link it from the pull request.
- **Design decisions and tradeoffs:** for choices with alternatives, such as a memory layout, a partition size, a feature left off a board or a rendering mode, open an issue even if nothing is left to do. It holds the numbers and the reason, and says what would make the decision worth revisiting.
- **Upstream problems:** for a bug or missing feature in a third-party project, open the issue upstream and a tracking issue in the Xila repository that depends on it. Describe the use case generically upstream, without the Xila name or links to Xila code. The tracking issue links the upstream one and names the workaround in Xila.

**How.**

- **Body structure:** Problem, Findings (measurements with dates and the setup they were taken on), Options with their tradeoffs, Decision and why, Status.
- **State in the description:** keep the state in the description, not in comments. Edit the body, tick task lists and update the Status section. Fold useful comment content into the body.
- **Links:** link related issues and pull requests both ways. Code that holds a workaround or a deliberate limitation names its issue in a comment.
- **Paused or rejected work:** don't close or forget an issue for work that is paused or rejected. Mark it paused or close it as not planned, with the reason in the Status section, so that the decision can be found and challenged.
- **Before an optimisation or redesign:** search the issues of the repositories involved for earlier decisions on the same area. Then reopen or update those issues instead of starting over.

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
- **Submodule rules** (enforced by `validate_workspace.py`): each path is `repositories/<name>`, its URL is exactly `https://github.com/xila-project/<name>.git`, it tracks `branch = main`, and `.gitmodules` and the tracked gitlinks match one-to-one. `core`, `platforms`, `applications`, `package_manager`, `registry` and `tools` are required for integration. When adding or removing a repository, update `.gitmodules`, the gitlink, `REQUIRED` in the validator (if relevant), `repositories:initialize-runtime`, the CI checkout step and the README together.
- **Pinned, not floating.** CI validates the specific committed gitlink combination. Updating submodules only moves the local checkout; the gitlink change must be reviewed and committed in this repository. Never push to a submodule's remote as a side effect of workspace work.
- **Do not repin to unmerged commits.** A gitlink on `main` must point to a commit reachable from that submodule's `main`. Temporary pins to PR branches are acceptable only in a draft PR and must be repinned to the merged SHA before merge.
- **Versions.** Tool versions live in `[vars]` in `mise/shared.toml` and are referenced as `{{ vars.<name> }}`; do not hard-code versions in tasks or workflows. Pin GitHub Actions to explicit versions, and tell consumers to reference workspace actions and workflows by full commit SHA.
- **Rust version.** Every Xila repository uses one Rust version, 1.97, as both the pinned toolchain (`rust_version` here, and in each repository's mise vars) and the declared MSRV (`rust-version`). It follows the esp-rs Xtensa toolchain base. Do not use language features or std/core APIs newer than 1.97. Raise it only when esp-rs publishes a new base, and then in every Xila repository at once. The nightly with `build-std` used for Rust native executables (core#687) is a separate exception.
- **Workflow style.** Step names follow `"<Phase> | <Description>"` (e.g. `Setup | …`, `Validate | …`, `Lint | …`, `Test | …`, `Gate | …`). Keep `permissions: contents: read`, `persist-credentials: false` on checkout, and a `timeout-minutes` on every job. Run commands through `mise run` tasks rather than inline scripts.
- **Build cache.** The mr-boxington cache is enabled in the integration job (`cache-generation: v1-workspace-integration`). `scripts/integration/check.sh` runs Cargo from a shell script, so it picks `mbx` or `cargo` itself the way the mise Cargo wrapper does (`XILA_MBX=1`, set by the setup-rust action); keep every Cargo call in that script going through its `cargo` function, or the cache becomes ineffective. It uses `cache-mode: objects`: the repository root has no `Cargo.toml`, and target mode's save step runs `cargo metadata` there and fails.
- **Validator changes.** `validate_workspace.py` must remain runnable without network access and without initialized submodules (checks that need a submodule run only when it is present).

# Non-Negotiables

- Keep `.superpowers/`, `.mise/`, `target/` and `.dev-environment/` out of Git.
- Before updating submodules, confirm none has uncommitted local work. Never reset or discard changes inside a submodule without asking.
- After editing workflows, `.gitmodules`, `mise.toml` or `mise/shared.toml`, run `mise run workspace:validate` and `mise run ci:lint-workflows`. After changing integration scripts or repinning runtime submodules, run at least `mise run integration:metadata`, and `integration:check` when feasible; report what was actually run.
- Make changes to submodule code in the submodule's own repository and through its own PR, following its `AGENTS.md`; the workspace only records the resulting gitlink.
- Do not reintroduce a Docker development image; the workspace is native mise only.

## Releases

Core, Platforms and Tools share the Xila version in their Cargo workspace
manifests. Before 1.0, a breaking change bumps the minor version and compatible
changes bump the patch. Review version bumps and changelog changes in release
pull requests. Record the merged commits in the workspace release pull request.
Keep dependencies on `main` and align each `Cargo.lock` with the workspace
gitlinks.

The workspace and all three repositories use `vX.Y.Z` on the selected commits.
Platforms hosts the release downloads, checksums and notes. Applications and
package_manager use independent versions and tags. Only the application SDK,
Tools and package_manager are intended for crates.io.

See [the Xila release policy](https://github.com/xila-project/core/issues/276).
