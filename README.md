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

The workspace orchestrates a daily and manually triggered source SBOM inventory at
[https://vulnerabilities.xila.dev/](https://vulnerabilities.xila.dev/). It scans the current
`main` of every public repository listed in `.gitmodules`, plus this workspace, as separate
Nanobom projects. This current-source inventory is separate from the pinned integration gate;
it never updates or commits gitlinks. The `.github` repository maps to project
`github-community`, because Nanobom project slugs must begin with a letter or digit.

Set up a **Whole organization**, **Upload and read** token in the Xila organization's
Nanobom **Settings → API tokens**, then store it with the GitHub CLI's hidden prompt:

```sh
gh secret set NANOBOM_TOKEN --org xila-project --visibility all
```

This is a Nanobom upload token, not a GitHub personal access token. GitHub organization owner
access is needed to create the organization Actions secret. Only this workspace workflow
currently consumes it; for narrower GitHub access use `--visibility selected --repos workspace`
instead of `--visibility all`.

The workflow defaults to the supplied instance URL and Nanobom organization slug
`xila-project`. If the instance uses a different slug, set the organization Actions variable
`NANOBOM_ORGANIZATION` to that slug. `NANOBOM_URL` optionally overrides the instance URL.
After merging the workflow and configuring the secret, run it once:

```sh
gh workflow run nanobom.yml --repo xila-project/workspace
```

Uploads run only on the schedule or explicit dispatch, never on pull requests. Each upload
records the scanned repository's actual commit rather than the workspace workflow commit.
The pinned Nanobom action generates CycloneDX JSON with Syft without running project code,
then uploads it and reports evaluation results in the Actions summary. An organization token
creates projects on their first upload.

Initially this is tracking only: existing CI and release gates are unchanged. Set the optional
organization Actions variable `NANOBOM_FAIL_ON` to `exploited`, `high`, or another threshold
supported by [nanobom-action](https://github.com/AlixANNERAUD/nanobom-action) to make the inventory
job fail on those findings. `wait: true` reports completed evaluations; failed uploads fail
the job, while evaluation status is also shown in the summary.

The source inventory captures dependencies visible to the SBOM generator (including supported
lockfiles). It is not a built firmware/container SBOM or a complete inventory of manually
vendored C libraries and downloaded assets. Product repositories remain responsible for
artifact-specific SBOMs. Private and archived repositories are excluded by the workspace's
public repository list. No deployment or database administration of Nanobom is performed here.

`mise run security:test` validates discovery offline. Live authenticated upload verification
requires the configured token and is performed by the first workflow run.

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
