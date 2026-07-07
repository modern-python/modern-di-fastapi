import contextlib
import dataclasses
import typing

import fastapi
from modern_di import Container, Scope, providers
from starlette.requests import HTTPConnection
from starlette.types import Lifespan


T_co = typing.TypeVar("T_co", covariant=True)


fastapi_request_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=fastapi.Request)
fastapi_websocket_provider = providers.ContextProvider(scope=Scope.SESSION, context_type=fastapi.WebSocket)

# The single source of the connection-kind mapping. Each provider pairs a connection
# type (``context_type``) with the scope its child container opens at; ``setup_di``
# registers them and ``build_di_container`` dispatches off them. Add a connection
# kind by adding its provider here — nothing else changes.
_CONNECTION_PROVIDERS = (fastapi_request_provider, fastapi_websocket_provider)


def fetch_di_container(app_: fastapi.FastAPI) -> Container:
    return typing.cast(Container, app_.state.di_container)


def _compose_lifespan(original: Lifespan[fastapi.FastAPI]) -> Lifespan[fastapi.FastAPI]:
    """Wrap ``original`` so the root container opens/closes around it.

    The original lifespan stays the outer context and its yielded state passes
    straight through; the container is opened inside it. ``async with`` reopens the
    container on each startup and closes it on shutdown, so a second lifespan cycle
    against the same container works instead of raising ``ContainerClosedError``.
    """

    @contextlib.asynccontextmanager
    async def composed(app_: fastapi.FastAPI) -> typing.AsyncIterator[typing.Mapping[str, typing.Any] | None]:
        async with original(app_) as state, fetch_di_container(app_):
            yield state

    # ``Lifespan`` is a union of CM[None] | CM[Mapping]; it can't express our
    # CM[Mapping | None], though that is exactly what a lifespan may yield.
    return typing.cast(Lifespan[fastapi.FastAPI], composed)


def setup_di(app: fastapi.FastAPI, container: Container) -> Container:
    app.state.di_container = container
    container.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    return container


async def build_di_container(connection: HTTPConnection) -> typing.AsyncIterator[Container]:
    context: dict[type[typing.Any], typing.Any] = {}
    scope = None
    for provider in _CONNECTION_PROVIDERS:
        if isinstance(connection, provider.context_type):
            context[provider.context_type] = connection
            scope = provider.scope
            break
    container = fetch_di_container(connection.app).build_child_container(context=context, scope=scope)
    try:
        yield container
    finally:
        await container.close_async()


@dataclasses.dataclass(slots=True, frozen=True)
class Dependency(typing.Generic[T_co]):
    dependency: providers.AbstractProvider[T_co] | type[T_co]

    async def __call__(
        self, request_container: typing.Annotated[Container, fastapi.Depends(build_di_container)]
    ) -> T_co:
        return request_container.resolve_dependency(self.dependency)


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co], *, use_cache: bool = True) -> T_co:  # noqa: N802
    return typing.cast(T_co, fastapi.Depends(dependency=Dependency(dependency), use_cache=use_cache))
