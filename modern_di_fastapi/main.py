import contextlib
import dataclasses
import typing

import fastapi
from fastapi.routing import _merge_lifespan_context
from modern_di import Container, Scope, providers
from starlette.requests import HTTPConnection


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


@contextlib.asynccontextmanager
async def _lifespan_manager(app_: fastapi.FastAPI) -> typing.AsyncIterator[None]:
    # ``async with`` reopens the root container on each startup (``__aenter__``)
    # and closes it on shutdown, so a second lifespan cycle against the same
    # container works instead of raising ContainerClosedError.
    async with fetch_di_container(app_):
        yield


def setup_di(app: fastapi.FastAPI, container: Container) -> Container:
    app.state.di_container = container
    container.providers_registry.add_providers(*_CONNECTION_PROVIDERS)
    old_lifespan_manager = app.router.lifespan_context
    app.router.lifespan_context = _merge_lifespan_context(
        old_lifespan_manager,
        _lifespan_manager,
    )
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
        if isinstance(self.dependency, providers.AbstractProvider):
            return request_container.resolve_provider(self.dependency)
        return request_container.resolve(dependency_type=self.dependency)


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co], *, use_cache: bool = True) -> T_co:  # noqa: N802
    return typing.cast(T_co, fastapi.Depends(dependency=Dependency(dependency), use_cache=use_cache))
