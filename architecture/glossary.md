# Glossary

The ubiquitous language of `modern-di-fastapi` — the domain terms that code,
specs, and capability pages share. Living prose, no frontmatter, dated by git.
Most names come from [`modern-di`](https://modern-di.modern-python.org); this
page pins only the terms whose *meaning in the FastAPI integration* needs to be
fixed.

**Root container**:
The app-level `modern_di.Container` stored on `app.state.di_container` by
`setup_di`. It owns `APP`-scoped state and is opened/closed by the app
[lifespan](container-lifecycle.md).
_Avoid_: global container, app container

**Child container**:
A scoped container derived from a parent via `build_child_container`. One is
built per *connection* inside `build_di_container`, and finer scopes
(`ACTION`) are reached by building further children from it.
_Avoid_: sub-container, request container (it is *a* child container, not a
distinct kind)

**Connection**:
A Starlette `HTTPConnection` — concretely a `fastapi.Request` (HTTP) or a
`fastapi.WebSocket`. The thing `build_di_container` keys its scope and context
off of.
_Avoid_: request (a request is only one kind of connection)

**Scope mapping**:
The fixed correspondence this integration imposes between a connection kind and
a `modern_di.Scope`: a `Request` opens a `REQUEST`-scoped child container; a
`WebSocket` opens a `SESSION`-scoped one. Any other `HTTPConnection` gets no
scope (`None`).
_Avoid_: scope resolution

**Context provider**:
A `providers.ContextProvider` that injects a runtime value into a scope rather
than constructing one. This package ships two — `fastapi_request_provider`
(`Request` → `REQUEST`) and `fastapi_websocket_provider` (`WebSocket` →
`SESSION`) — registered by `setup_di` so endpoints can resolve the live
connection object.

**Dependency marker**:
The value returned by `FromDI(...)` — a `fastapi.Depends` wrapping the
`Dependency` callable — placed in an endpoint's `Annotated[...]` signature to
declare "resolve this from DI". The unit of [dependency
resolution](dependency-resolution.md).
_Avoid_: injector, provider (a provider is what gets resolved; the marker is how
an endpoint asks for it)
