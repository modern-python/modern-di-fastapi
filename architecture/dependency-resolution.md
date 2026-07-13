# Dependency resolution

How a route or WebSocket handler declares a dependency and receives the resolved
instance. Terms in *italics* are defined in the [glossary](glossary.md); the
scoped container this resolution runs against comes from the
[container lifecycle](container-lifecycle.md).

## The marker — `FromDI(dependency, *, use_cache=True)`

`FromDI` is what an endpoint puts in its signature:

```python
async def read_root(
    instance: typing.Annotated[SimpleCreator, FromDI(Dependencies.app_factory)],
) -> ...: ...
```

It accepts either a `providers.AbstractProvider` or a plain type, and returns a
`fastapi.Depends` wrapping a `Dependency` instance — the *dependency marker*.
`use_cache` is forwarded to `fastapi.Depends`, so FastAPI's per-request
dependency caching applies as usual. The return is `cast` to the dependency's
type, so the annotated parameter type stays accurate.

## The callable — `Dependency`

`Dependency` is a frozen, slotted, generic dataclass holding a
`modern_di.integrations.Marker` wrapping the requested dependency. Its
`__call__` is itself a FastAPI dependency: it depends on `build_di_container`,
so it receives the *child container* for the current connection, then resolves
against it via `self.marker.resolve(request_container)` — which calls
`request_container.resolve_dependency(marker.dependency)` internally. A
provider argument resolves by reference, a plain type resolves by type;
overrides, caching, and suggestions are inherited from whichever it dispatches
to.

Because resolution flows through `build_di_container`, every `FromDI`
dependency in a request shares that request's scoped container and its
registered *context providers* — so resolving e.g. a `REQUEST`-scoped factory
that reads the live `fastapi.Request` works without the endpoint threading the
connection through by hand.

## Scope reach

`FromDI` resolves at the scope of the container `build_di_container` produced
(`REQUEST` for HTTP, `SESSION` for WebSocket). To resolve an `ACTION`-scoped (or,
from a WebSocket, `REQUEST`-scoped) dependency, an endpoint takes the container
directly — `typing.Annotated[Container, fastapi.Depends(build_di_container)]` —
and builds a further child to resolve against.
