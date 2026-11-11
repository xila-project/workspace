<h1>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/brand/header-dark.svg">
  <img src=".github/brand/header-light.svg" alt="Xila Workspace — Shared tooling and cross-repository integration." width="1280">
</picture>
</h1>

[Documentation](https://www.xila.dev/docs/) ·
[Try Xila](https://platforms.xila.dev/) ·
[Community](https://matrix.to/#/#xila:anneraud.fr)

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
# On Debian/Ubuntu, install required native development libraries first:
mise run ci:packages-integration
mise run ci:node-dependencies
mise run integration:metadata
mise run integration:check
```

For a smaller checkout, clone normally and initialize only integration dependencies:

```sh
mise run repositories:initialize-runtime
```

The `repositories/` directory contains Git submodules of all currently active
**public** Xila organization repositories, including Core, Platforms,
Applications, the package manager, the package registry, website, brand, media and other tooling.
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
  submodules. Native dependencies are owned by Platforms' `mise.ci.toml` and
  applied through its `ci:packages-host` task from
  `mise run ci:packages-integration`; Workspace keeps no duplicate package list.
  Node tools and locked npm dependencies are installed through
  `mise run ci:node-dependencies`. Integration uses
  `platforms/tools/dev/local_overrides.py` to patch Cargo dependencies to
  locally checked-out sources.

The integration job initially disables the mr-boxington cache because it runs
raw Cargo commands from a shell script; enabling it before these commands use
the mise Cargo wrapper would create an ineffective cache. The shared action
does support it for consumer workflows whose Cargo tasks run through mise.

Default issue and PR templates are stored in the separate organization-wide
`xila-project/.github` repository. Do not duplicate them here.

## Vulnerability inventory

The workspace provides a reusable workflow (`.github/workflows/nanobom.yml`) that product
repositories call to upload source SBOMs to [https://vulnerabilities.xila.dev/](https://vulnerabilities.xila.dev/).
Each product repository runs its own caller workflow on push to `main`, a weekly schedule,
and manual `workflow_dispatch`. This per-repository model ensures evaluations appear
directly in each repository's Actions runs and associate findings with the commit that
introduced them.

The workflow uses the organization Actions secret `NANOBOM_TOKEN` (configured with whole-organization
upload-and-read permissions and visibility set to all repositories). It defaults to the instance URL
`https://vulnerabilities.xila.dev` and the organization slug `xila-project`. These can be overridden
via organization or repository Actions variables:

- `NANOBOM_URL`: overrides the Nanobom instance URL.
- `NANOBOM_ORGANIZATION`: overrides the organization slug.
- `NANOBOM_FAIL_ON`: optional finding severity threshold (`exploited`, `high`, etc.) supported by
  [nanobom-action](https://github.com/AlixANNERAUD/nanobom-action) to fail the job; defaults to empty
  (tracking only). Callers can also supply the `fail-on` input.

Product repositories add a caller workflow such as `.github/workflows/nanobom.yml`:

```yaml
name: Nanobom
on:
  push:
    branches: [main]
  schedule:
    - cron: "<pick per repo>"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  inventory:
    uses: xila-project/workspace/.github/workflows/nanobom.yml@<full workspace main SHA>
    secrets:
      NANOBOM_TOKEN: ${{ secrets.NANOBOM_TOKEN }}
```

Callers must pin the reusable workflow to a full commit SHA on workspace `main` and must
never trigger it on `pull_request` (forks cannot access secrets, and source inventories describe
accepted branch commits).

Repositories without dependency lockfiles (`registry`, `.github`, and the `workspace` orchestrator
itself) do not need to call the workflow. The source inventory captures dependencies visible to
the SBOM generator (such as `Cargo.lock` or `package-lock.json`). It is not a built
firmware/container SBOM or a complete inventory of manually vendored C libraries and downloaded
assets; product repositories remain responsible for artifact-specific SBOMs.

## Ownership

The workspace owns orchestration, shared CI tooling and integration checks.
Platform firmware, filesystem images, Wasm demos, package content and app
sources remain owned by their individual repositories. This repository does
not build or publish a Docker development image.

## Shared package bootstrap dependency

The integration task delegates native Linux package installation to the pinned
Platforms submodule (`mise -E ci run ci:packages-host`). The native package
list remains owned exclusively by Platforms. This workspace revision is paired
with Platforms' proposed mise bootstrap migration (platforms PR #37). Do not
merge this workspace PR while its `repositories/platforms` gitlink points to
an unmerged PR commit; after Platforms #37 merges, repin that gitlink to the
final `platforms/main` SHA and rerun the workspace integration gate.

<!-- xila:footer:start -->

---

Part of **[Xila](https://www.xila.dev/)** ·
[Repositories](https://github.com/xila-project) ·
[Community](https://matrix.to/#/#xila:anneraud.fr)

Special thanks to [Martin Legand](https://www.behance.net/martinlegand) for generously designing the Xila logo.

<!-- xila:footer:end -->
