# Xila CI conventions

GitHub Actions has **jobs** and **steps**, not a GitLab-style native `stages`
keyword. Use the names below for a consistent experience in the Actions UI.
These are **Xila conventions**, not rules imposed by GitHub.

## Workflows, jobs and steps

- **Workflow `name`**: purpose-first, e.g. `CI`, `Integration`, `Release`.
- **Job IDs**: stable lowercase kebab-case (or existing short IDs); do not rename
  `required`, or other protected check contexts, as part of a cosmetic change.
- **Job display `name`**: `Domain / Target`, e.g. `Build / Native`,
  `Build / WASI guests`, `Test / ABI (${{ matrix.memory }})`,
  `Quality / Rust`, `Integration / Cross-repository`. Retain the **exact
  existing display name** of the final branch-protection check (`Required` or
  `required`, depending on the repository).
- **Step display `name`**: `Category | Verb + object` in English:
  `Setup | Checkout sources`, `Setup | Rust and build cache`,
  `Lint | Rust formatting`, `Lint | Native drivers`,
  `Test | Firmware simulator`, `Build | WASI guests`,
  `Package | Assemble application archive`, `Report | Upload evidence`.
- **Step `id`**: stable and short, only when used by outputs/conditions
  (e.g. `locales`); unlike `name`, IDs are part of the workflow API.
- Use `name` on all meaningful checkout, setup, test, build, publish and
  artifact-upload steps; do not let the UI display raw shell commands or action
  repository identifiers.
- Matrices must include their discriminator in the job display name.
- Avoid changing jobs to `needs: quality` simply to mimic a stage graph;
  independent jobs should run concurrently unless there is a real dependency.
- Keep default workflow permissions read-only. Do not move release/deploy
  permissions into broadly reusable quality workflows.

## Shared primitives

- A **reusable workflow** is appropriate for an identical job (e.g. the
  `quality.yml` workflow shared by Platforms and Applications). It renders
  its steps separately in GitHub's job logs.
- A **composite action** is appropriate for common setup within a larger job,
  e.g. `setup-rust` or `setup-node`; it appears as one caller step.
- **mise tasks** own platform-/application-specific commands and OS package
  manifests. They must remain usable locally and must not be duplicated in
  cross-repository workflow YAML.
- Call shared workflows/actions from an **immutable SHA reachable on
  `workspace/main`** after they have merged. Feature-branch pins in dependent
  draft PRs are temporary and must be replaced before merging.
- Run code policy checks in the caller repository with the caller checkout;
  called workflow checkout resolves the caller, not Workspace.

## Required checks and migration

Keep a final job whose ID is `required`, `if: always()`, and whose `needs`
list includes every mandatory validation job. Preserve matrix coverage, cache
modes, artifact paths and release gating. Display-name changes can alter
GitHub required-check contexts, so verify the repository ruleset before
merging. Do not rename the final required-check context without an explicit
branch-protection migration.

### Reusable quality contract

`.github/workflows/quality.yml` requires these **caller-local** mise tasks:

- `ci:format-rust`
- `ci:format-toml`
- `ci:lint-workflows`
- `ci:quality-extra` (or another task supplied through `extra-task`)

The extra task includes repository-owned tests, manifest or localization checks.
The workflow intentionally keeps these as separate visible steps, rather than
collapsing the entire job into an opaque script.

## References

- GitHub Actions workflow syntax:
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub reusable workflows versus composite actions:
  https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations

## Adoption order

1. Merge the prerequisite Workspace integration/bootstrap changes in #4.
2. Merge this shared naming/quality workflow PR after its CI is green on top of #4.
3. Update Core, Platforms and Applications consumers to pin the **final merged
   `workspace/main` commit SHA**. Do not merge consumers using the temporary
   pre-merge quality workflow SHA.
4. Confirm each repository's configured required status checks, then merge
   consumers independently.
