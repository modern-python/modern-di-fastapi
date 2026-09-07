# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`modern-di-fastapi` is the FastAPI integration for
[`modern-di`](https://github.com/modern-python/modern-di); [`CONTEXT.md`](CONTEXT.md) opens with
what it does and owns the vocabulary — read it before naming a concept in code, a test name, or an
issue title. It is one of that project's integrations, each of which lives in a separate repository
and ships as a separate PyPI package.

## Commands

`just` (task runner) and `uv` (package manager). The [`justfile`](justfile) is the source of truth —
`just --list`, or read it. The one thing it does not say: a `ty` suppression is written
`# ty: ignore`, never `# type: ignore`.

## Architecture

All implementation is `modern_di_fastapi/main.py`, short enough to read whole. Read it.

### Testing patterns

`tests/dependencies.py` is the model every test builds on: one `Group` spanning four scopes, plus
two factories that read the live `Request` / `WebSocket` to exercise the context providers. Routes
are declared **inside the test body**, decorating the `app` fixture after `client` has already built
its `TestClient` — FastAPI picks them up, and it keeps each test's route next to its assertions.

## Workflow

Real work **not scheduled** becomes a GitHub issue.

An invariant is a test whose name is the claim, with a docstring opening `INVARIANT:` and a second
paragraph naming **what breaks it** — design rationale, not a report of what this one test catches.
Nothing enforces that docstring shape; it is read at review time.
