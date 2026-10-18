import collections.abc
import contextlib
import dataclasses
import logging
import typing

import anyio
import fastapi
from modern_di import Container, Scope, integrations, providers
from starlette.requests import HTTPConnection
from starlette.routing import BaseRoute, Host, Mount
from starlette.types import Lifespan


T_co = typing.TypeVar("T_co", covariant=True)


fastapi_request_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=fastapi.Request)
fastapi_websocket_provider = providers.ContextProvider(scope=Scope.SESSION, context_type=fastapi.WebSocket)

# The single source of the connection-kind mapping. Each provider pairs a connection
# type (``context_type``) with the scope its child container opens at; ``setup_di``
# registers them and ``build_di_container`` dispatches off them. Add a connection
# kind by adding its provider here — nothing else changes.
_CONNECTION_PROVIDERS = (fastapi_request_provider, fastapi_websocket_provider)
_CHILD_CLOSE_TIMEOUT = 10.0
_logger = logging.getLogger(__name__)


def fetch_di_container(app_: fastapi.FastAPI) -> Container:
    try:
        return typing.cast(Container, app_.state.di_container)
    except AttributeError:
        msg = (
            "No modern-di container found on the app. "
            "Call setup_di(app, container) before using FromDI or fetch_di_container."
        )
        raise RuntimeError(msg) from None


def _managed_root(app_: fastapi.FastAPI) -> collections.abc.Iterator[Container]:
    container = getattr(app_.state, "di_container", None)
    if container is not None and getattr(app_.state, "di_manage_lifespan", True):
        yield container


def _mounted_containers(routes: collections.abc.Iterable[BaseRoute]) -> collections.abc.Iterator[Container]:
    for route in routes:
        if not isinstance(route, Mount | Host):
            continue
        # Mount(middleware=...) wraps route.app; Starlette keeps the unwrapped app on the private _base_app.
        app_ = getattr(route, "_base_app", route.app)
        if isinstance(app_, fastapi.FastAPI):
            yield from _managed_root(app_)
        yield from _mounted_containers(route.routes)


def _compose_lifespan(original: Lifespan[fastapi.FastAPI]) -> Lifespan[fastapi.FastAPI]:
    """Wrap ``original`` so the root container opens/closes around it.

    The container is the outer context: it opens before the original lifespan's
    startup code and closes after its shutdown code, so that code can resolve
    ``APP``-scoped dependencies. The original's yielded state passes straight
    through. ``async with`` reopens the container on each startup and closes it on
    shutdown, so a second lifespan cycle against the same container works instead
    of raising ``ContainerClosedError``.

    Starlette runs only the outermost app's lifespan, so the root containers of
    mounted apps that called ``setup_di`` are opened and closed here too. The
    routes are walked at startup, before the original's startup code, and each
    container is entered once. An app whose ``setup_di`` got
    ``manage_lifespan=False`` has its root left alone.
    """

    @contextlib.asynccontextmanager
    async def composed(app_: fastapi.FastAPI) -> collections.abc.AsyncGenerator[typing.Mapping[str, typing.Any] | None]:
        async with contextlib.AsyncExitStack() as stack:
            entered: list[Container] = []
            for container in (*_managed_root(app_), *_mounted_containers(app_.routes)):
                if not any(container is seen for seen in entered):
                    entered.append(container)
                    await stack.enter_async_context(container)
            async with original(app_) as state:
                yield state

    # ``Lifespan`` is a union of CM[None] | CM[Mapping]; it can't express our
    # CM[Mapping | None], though that is exactly what a lifespan may yield.
    return typing.cast(Lifespan[fastapi.FastAPI], composed)


def setup_di(app: fastapi.FastAPI, container: Container, *, manage_lifespan: bool = True) -> Container:
    app.state.di_container = container
    app.state.di_manage_lifespan = manage_lifespan
    container.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    return container


async def build_di_container(connection: HTTPConnection) -> typing.AsyncIterator[Container]:
    match = integrations.classify_connection(connection, _CONNECTION_PROVIDERS)
    container = fetch_di_container(connection.app).build_child_container(
        scope=match.scope if match else None,
        context=match.context if match else None,
    )
    try:
        yield container
    finally:
        with anyio.move_on_after(_CHILD_CLOSE_TIMEOUT, shield=True) as close_scope:
            await container.close_async()
        if close_scope.cancelled_caught:
            _logger.warning(
                "Closing the child container did not finish within %s s; its remaining finalizers did not run",
                _CHILD_CLOSE_TIMEOUT,
            )


@dataclasses.dataclass(slots=True, frozen=True)
class Dependency(typing.Generic[T_co]):
    marker: integrations.Marker[T_co]

    async def __call__(
        self, connection_container: typing.Annotated[Container, fastapi.Depends(build_di_container)]
    ) -> T_co:
        return self.marker.resolve(connection_container)


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co], *, use_cache: bool = True) -> T_co:  # noqa: N802
    return typing.cast(
        T_co, fastapi.Depends(dependency=Dependency(integrations.Marker(dependency)), use_cache=use_cache)
    )
