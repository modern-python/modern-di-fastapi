# modern-di-fastapi

The [`modern-di`](https://github.com/modern-python/modern-di) integration for FastAPI: it opens the
container across the app's lifespan, opens a scoped child container per connection, and resolves
declared dependencies into route and WebSocket parameters through FastAPI's own `Depends`.

## Language

A term is listed only when there is a synonym to reject, or a meaning subtle enough that code and
docs must agree on it. General programming vocabulary does not belong here, however heavily this
package uses it.

The domain terms are `modern-di`'s — `Container` (root and child), `Provider`, `Group`, `Scope`,
`Resolution`, `Override`, `Connection`. That project's `CONTEXT.md` is the authority for all of
them; nothing here redefines one. FastAPI's are FastAPI's: dependency, `Depends`, router, request,
WebSocket. The two below are this package's own.

**Per-connection container**:
The child container `build_di_container` opens for one connection and closes when it ends —
`REQUEST`-scoped for a `fastapi.Request`, `SESSION`-scoped for a `fastapi.WebSocket`. Every `FromDI`
parameter in one handler resolves from the same one.
_Avoid_: per-request container, request container. A WebSocket's is `SESSION`-scoped, so "request"
names one of the two kinds while reading as the wrong scope for the other.

**Composed lifespan**:
The app's own lifespan with the container's open/close nested inside it, installed by `setup_di`
onto `app.router.lifespan_context`. The original stays the outer context and its yielded state
passes through untouched.
_Avoid_: merged lifespan — "merge" is FastAPI's own word for the private helper this package
deliberately does not use, which also merges the two yielded states
([ADR-0001](docs/adr/0001-own-the-lifespan-composition.md)). Also avoid appended lifespan: the
container's open/close runs *inside* the app's, not after it.
