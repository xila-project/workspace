# Xila workspace

This repository is the **multi-repository development and integration workspace**
for Xila. It replaces the legacy Docker-based development image with native
[mise](https://mise.jdx.dev/) tasks, Git submodules and shared GitHub Actions.

Each constituent repository remains independently buildable, releasable and
responsible for its own unit tests. Workspace CI validates *specific pinned
combinations* of repositories, not floating `main` branches.

## Get started

```sh
git clone --recurse-submodules https://github.com/xila-project/workspace.git
cd workspace
mise run workspace:validate
mise run integration:metadata
mise run integration:check
```

For a smaller checkout, clone normally and initialize only integration dependencies:

```sh
mise run repositories:initialize-runtime
```

The `repositories/` directory contains Git submodules of all currently active
**public** Xila organization repositories, including Core, Platforms,
Applications, the package manager, packages, website, brand and other tooling.
Private repositories (for example business plans) and archived repositories
are deliberately excluded. A normal clone does not automatically download
submodule content.

## Revisions and updates

All submodules are pinned by their tracked gitlink SHAs.
`mise run repositories:status` prints the current revisions.
`mise run repositories:update` explicitly checks out the latest configured
`main` revisions: **review the diff and commit the new gitlinks** after
validating compatibility. Updating a submodule does not push to that repository.

## CI architecture

- `.github/actions/setup-rust/`: reusable composite action for mise, pinned
  Rust toolchain and opt-in mr-boxington cache; the caller decides its cache
  generation/mode and retains its own `mise.ci.toml` tasks.
- `.github/workflows/quality.yml`: reusable formatting/actionlint workflow for
  Xila repositories, to be adopted as consumers are migrated.
- `.github/workflows/ci.yml`: workspace-only integration gate using pinned
  submodules. It uses `platforms/tools/dev/local_overrides.py` to patch Git
  Cargo dependencies to the locally checked-out Core and Applications sources.

The integration job initially disables the mr-boxington cache because it runs
raw Cargo commands from a shell script; enabling it before these commands use
the mise Cargo wrapper would create an ineffective cache. The shared action
does support it for consumer workflows whose Cargo tasks run through mise.

Default issue and PR templates are stored in the separate organization-wide
`xila-project/.github` repository. Do not duplicate them here.

## Ownership

The workspace owns orchestration, shared CI tooling and integration checks.
Platform firmware, filesystem images, Wasm demos, package content and app
sources remain owned by their individual repositories. This repository does
not build or publish a Docker development image.
