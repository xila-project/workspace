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
