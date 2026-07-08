# CLAUDE.md

Guidance for agents working in `modern-di-fastapi` — the
[modern-di](https://modern-di.modern-python.org) integration for FastAPI.

## Workflow

Before making a change, follow the **Quick path** in
[`planning/README.md`](planning/README.md) — the authoritative planning
convention. Pick a lane (Full / Lightweight / Tiny), create the change file
under `planning/changes/` when the lane calls for one, and run
`just check-planning` before pushing.

## Architecture

[`architecture/`](architecture/) holds the living truth about what the system
does **now** — one file per capability, plus `glossary.md`. **When a change
alters a capability's behavior, update the matching
`architecture/<capability>.md` in the same PR**, alongside the code; the *why*
stays in the change file under `planning/changes/`.

## Build & checks

- `just lint` / `just lint-ci` — format, ruff, `ty`; `lint-ci` also runs
  `check-planning`.
- `just test` — pytest (100% coverage required via `just test-ci`).
- `just index` — print the generated planning index.
