# Architecture

The living truth about what `modern-di-fastapi` does **now**. One file per
capability, plus a single [`glossary.md`](glossary.md) (the ubiquitous
language) — living prose, no frontmatter, dated by git.

**Promotion rule:** when a change alters a capability's behavior, the
implementing PR hand-edits the matching `architecture/<capability>.md` in the
same diff, alongside the code. That hand-edit is what keeps this directory true;
the *why* lives in the change bundle under
[`planning/changes/`](../planning/changes/).

Capability files and `glossary.md` are authored lazily — each appears when the
first capability or term is worth pinning down.

## Capabilities

- [`container-lifecycle.md`](container-lifecycle.md) — wiring the container into
  the app, the lifespan, and per-connection scoped child containers.
- [`dependency-resolution.md`](dependency-resolution.md) — `FromDI` and how
  endpoints declare and receive resolved dependencies.
- [`glossary.md`](glossary.md) — the ubiquitous language.
