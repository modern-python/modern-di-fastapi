# Container lifecycle

How a `modern_di.Container` is wired into a FastAPI app and how scoped child
containers are opened and closed around each connection. Terms in *italics* are
defined in the [glossary](glossary.md).

## Installation — `setup_di(app, container)`

`setup_di` attaches a caller-built *root container* to the app and is the single
entry point an application calls at startup. It does three things:

1. Stores the container on `app.state.di_container` (read back by
   `fetch_di_container(app)`).
2. Registers the two *context providers*
   (`fastapi_request_provider`, `fastapi_websocket_provider`) via
   `container.add_providers(...)`, so the live `Request` / `WebSocket` can be
   resolved.
3. Composes the container's open/close onto the app's existing
   `lifespan_context` via `_compose_lifespan`, preserving any lifespan the app
   already had (its startup/shutdown still run and its yielded state passes
   through). The composition is our own — no dependency on FastAPI internals.

It returns the same container for convenience. The application owns container
construction (groups, overrides); `setup_di` only wires it in.

## Lifespan — open/close across cycles

The composed lifespan keeps the original as the outer context and opens the
container inside it with `async with fetch_di_container(app):` — the root
container's `__aenter__` opens it on startup and `__aexit__` closes it on
shutdown. Using `async with` (rather than a one-shot open) means a **second
lifespan cycle against the same container reopens it** instead of raising
`ContainerClosedError`. This is what lets an app be started, stopped, and
started again (e.g. repeated `TestClient` contexts in tests) against one
container instance.

## Per-connection containers — `build_di_container(connection)`

`build_di_container` is an async FastAPI dependency that yields a *child
container* scoped to the current *connection*, then closes it:

- It applies the *scope mapping* via `modern_di.integrations.classify_connection`,
  which walks the registered *context providers* (`_CONNECTION_PROVIDERS`): the
  first whose `context_type` the connection is an instance of supplies both the
  scope and the context key. So a `fastapi.Request` → `Scope.REQUEST` with the
  request placed in `context[fastapi.Request]`; a `fastapi.WebSocket` →
  `Scope.SESSION` with the socket in `context[fastapi.WebSocket]`. Any other
  `HTTPConnection` matches no provider and yields a child with `scope=None`. The
  providers are the single source — adding a connection kind is adding a
  provider, with no change to this dispatch. The isinstance-over-tuple dispatch
  itself lives in modern-di's integration kit, not here.
- The child is opened as an `async with` block —
  `Container.build_child_container(scope=..., context=...)` returns a container
  that is already open, so entering it is a no-op.
- Exiting the block closes the child container (`close_async`), including on
  the exception path, tearing down anything opened in that scope.

Finer scopes are reached by building further children from this one: an HTTP
endpoint can `build_child_container()` again for `ACTION` scope, and a WebSocket
handler (whose injected container is `SESSION`-scoped) builds a child for
`REQUEST` scope.

## Accessor — `fetch_di_container(app)`

Returns the root container off `app.state` (cast to `Container`). Used
internally by the lifespan and `build_di_container`, and available to
application code that needs the root container directly.
