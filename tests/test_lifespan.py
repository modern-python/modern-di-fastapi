import contextlib
import typing

import fastapi
import modern_di
from starlette import status
from starlette.testclient import TestClient

import modern_di_fastapi
from modern_di_fastapi import FromDI, fetch_di_container
from tests.dependencies import Dependencies, SimpleCreator


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
    async def user_lifespan(app_: fastapi.FastAPI) -> typing.AsyncIterator[dict[str, str]]:
        assert isinstance(app_, fastapi.FastAPI)
        events.append("startup")
        yield {"marker": "from-user-lifespan"}
        events.append("shutdown")

    app = fastapi.FastAPI(lifespan=user_lifespan)
    container = modern_di.Container(groups=[Dependencies], validate=True)
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
