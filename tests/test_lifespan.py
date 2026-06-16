import typing

import fastapi
from starlette import status
from starlette.testclient import TestClient

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
