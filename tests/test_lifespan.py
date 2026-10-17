import collections.abc
import contextlib
import typing

import fastapi
import modern_di
from modern_di import Group, Scope, providers
from starlette import status
from starlette.testclient import TestClient

import modern_di_fastapi
from modern_di_fastapi import FromDI, build_di_container, fetch_di_container
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


def test_lifespan_reopens_container_across_cycles(app: fastapi.FastAPI) -> None:
    @app.get("/")
    async def read_root(instance: typing.Annotated[SimpleCreator, FromDI(Dependencies.app_factory)]) -> None:
        assert isinstance(instance, SimpleCreator)

    container = fetch_di_container(app)

    # First lifespan cycle: shutdown closes the root container.
    with TestClient(app=app) as client:
        assert client.get("/").status_code == status.HTTP_200_OK
    assert container.closed

    # Second cycle must reopen the same container instead of raising ContainerClosedError.
    with TestClient(app=app) as client:
        assert client.get("/").status_code == status.HTTP_200_OK


def test_setup_di_composes_with_existing_lifespan() -> None:
    events: list[str] = []

    @contextlib.asynccontextmanager
    async def user_lifespan(app_: fastapi.FastAPI) -> collections.abc.AsyncGenerator[dict[str, str]]:
        assert isinstance(app_, fastapi.FastAPI)
        events.append("startup")
        yield {"marker": "from-user-lifespan"}
        events.append("shutdown")

    app = fastapi.FastAPI(lifespan=user_lifespan)
    container = modern_di.Container(groups=[Dependencies])
    modern_di_fastapi.setup_di(app, container)

    @app.get("/")
    async def read_marker(request: fastapi.Request) -> str:
        return typing.cast(str, request.state.marker)

    with TestClient(app=app) as client:
        # original lifespan started; our container opened; its yielded state passes through
        assert events == ["startup"]
        assert not container.closed
        assert client.get("/").json() == "from-user-lifespan"
    # shutdown ran the original lifespan and closed our container
    assert events == ["startup", "shutdown"]
    assert container.closed


def _unmanaged_app(finalized: list[str]) -> tuple[fastapi.FastAPI, modern_di.Container]:
    class Finalized(Group):
        value = providers.Factory(
            scope=Scope.APP,
            creator=lambda: "app",
            bound_type=str,
            cache=providers.CacheSettings(finalizer=finalized.append),
        )

    app = fastapi.FastAPI()
    container = modern_di.Container(groups=[Dependencies, Finalized])
    modern_di_fastapi.setup_di(app, container, manage_lifespan=False)
    return app, container


def test_manage_lifespan_false_leaves_the_root_open() -> None:
    finalized: list[str] = []
    app, container = _unmanaged_app(finalized)
    request_containers: list[modern_di.Container] = []

    @app.get("/")
    async def read_root(
        value: typing.Annotated[str, FromDI(str)],
        instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
        request_container: typing.Annotated[modern_di.Container, fastapi.Depends(build_di_container)],
    ) -> str:
        assert isinstance(instance, DependentCreator)
        request_containers.append(request_container)
        return value

    with TestClient(app=app) as client:
        assert client.get("/").json() == "app"

    assert not container.closed
    assert finalized == []
    assert [c.scope for c in request_containers] == [modern_di.Scope.REQUEST]
    assert request_containers[0].closed


async def test_manage_lifespan_false_lets_the_user_own_the_root() -> None:
    finalized: list[str] = []
    app, container = _unmanaged_app(finalized)

    @app.get("/")
    async def read_root(value: typing.Annotated[str, FromDI(str)]) -> str:
        return value

    async with container:
        with TestClient(app=app) as client:
            assert client.get("/").json() == "app"
        assert finalized == []

    assert finalized == ["app"]


def test_user_lifespan_runs_inside_the_open_root() -> None:
    events: list[str] = []

    class Finalized(Group):
        value = providers.Factory(
            scope=Scope.APP,
            creator=lambda: "app",
            bound_type=str,
            cache=providers.CacheSettings(finalizer=lambda value: events.append(f"{value} finalized")),
        )

    container = modern_di.Container(groups=[Dependencies, Finalized])

    @contextlib.asynccontextmanager
    async def user_lifespan(_: fastapi.FastAPI) -> collections.abc.AsyncGenerator[None]:
        events.append(f"startup {container.resolve(str)}")
        yield
        events.append(f"shutdown {container.resolve(str)}")

    app = fastapi.FastAPI(lifespan=user_lifespan)
    modern_di_fastapi.setup_di(app, container)

    cycles = 2
    for _ in range(cycles):
        with TestClient(app=app):
            pass

    assert events == ["startup app", "shutdown app", "app finalized"] * cycles
