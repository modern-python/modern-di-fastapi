# The lifespan composition is ours; FastAPI's `_merge_lifespan_context` is not used

**Decision:** `setup_di` installs the container's open/close onto the public
`app.router.lifespan_context` through this package's own `_compose_lifespan`. It does not call
`fastapi.routing._merge_lifespan_context`, which it used until 2.8.0.

The obvious objection is that FastAPI already ships lifespan composition, so writing our own is
duplicated work over a name that has been stable for years. Two things answer it.

**It is private, and the supported FastAPI range is enormous.** `pyproject.toml` pins
`fastapi>=0.100,<1`. A leading-underscore name in `fastapi.routing` carries no compatibility
promise across that range, and the failure mode is an `ImportError` at `setup_di` time — every app
using this package, at startup, on a routine FastAPI upgrade.

**It does not do what we need anyway.** `_merge_lifespan_context` composes two *lifespans* —
`Callable[[App], AsyncContextManager]` — and yields `{**nested, **original}` from their two states.
A `Container` is a bare async context manager yielding nothing, so it would first have to be wrapped
in a lifespan-shaped callable, which is most of `_compose_lifespan` already; and the merge path
would then replace the original lifespan's own passthrough — its `None` or its mapping, verbatim —
with a freshly built dict. That is a behaviour change to the user's lifespan in exchange for
borrowing seven lines.

What `_compose_lifespan` owns beyond wrapping is the one thing neither helper would give us: it
enters the container with `async with` rather than a one-shot open, so a second lifespan cycle
against the same container reopens it instead of raising `ContainerClosedError` — the case
`test_lifespan_reopens_container_across_cycles` covers, and the reason repeated `TestClient`
contexts work against one container.

**Revisit trigger:** Starlette or FastAPI publishes a *public* lifespan-composition helper whose
state handling is passthrough rather than merge. At that point the wrapper is borrowable and
`_compose_lifespan` should shrink to the `async with` that reopens the container.
