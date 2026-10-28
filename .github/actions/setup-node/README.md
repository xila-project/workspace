# Shared Node.js development setup

Use this composite action from a GitHub Actions job **after checkout** when
the calling repository declares a Node toolchain in `mise.toml`:

```toml
[tools]
node = "24.22.0"
```

```yaml
- uses: actions/checkout@v7
- uses: xila-project/workspace/.github/actions/setup-node@<IMMUTABLE_WORKSPACE_SHA>
- run: mise exec -- npm run check
```

The action runs `jdx/mise-action`, reuses the npm download cache keyed by the
caller repository's committed lockfile and installs dependencies with
`mise exec -- npm ci`. It never uses floating Node LTS, and its cache contains
npm downloads, not `node_modules`.

The optional `working-directory` and `cache-dependency-path` inputs support
subprojects. Set `install-dependencies: "false"` for a job that only
needs the pinned Node toolchain.

Use a **full commit SHA from workspace/main**, not a branch or tag, so
that consumers review updates before taking them.

## Integration with the workspace CI

This action is independent of Rust compilation. While the shared Node action is
reviewed, the Workspace PR is tested **against the mise-bootstrap changes in
Workspace #4**: they install the pinned Platforms npm dependencies required by
the existing Rust graphics integration job. Without those changes, the
workspace's `main` integration job fails before reaching tests relevant to
this action. Merge #4 first; then retarget this PR to `main`, wait for green
checks, and use the resulting immutable `main` SHA in consumers such as Website.
