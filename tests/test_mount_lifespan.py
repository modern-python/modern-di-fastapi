import typing

import fastapi
from modern_di import Container, Group, Scope, providers
from starlette import status
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Host, Mount, Route
from starlette.testclient import TestClient

from modern_di_fastapi import FromDI, setup_di


class _CountingContainer(Container):
    closes = 0

    async def close_async(self) -> None:
        self.closes += 1
        await super().close_async()


def _container(label: str, events: list[str]) -> _CountingContainer:
    def create() -> str:
        events.append(f"{label} created")
        return label

    def finalize(value: str) -> None:
        events.append(f"{value} finalized")

    class Values(Group):
        value = providers.Factory(
            scope=Scope.APP,
            creator=create,
            bound_type=str,
            cache=providers.CacheSettings(finalizer=finalize),
        )

    return _CountingContainer(groups=[Values])


async def _view(value: typing.Annotated[str, FromDI(str)]) -> PlainTextResponse:
    return PlainTextResponse(value)


def _app(container: Container | None = None, routes: list[typing.Any] | None = None) -> fastapi.FastAPI:
    app = fastapi.FastAPI(routes=routes)
    app.add_api_route("/x", _view)
    if container is not None:
        setup_di(app, container)
    return app


def test_mounted_container_is_finalized_at_shutdown() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    outer = _app(_container("outer", events), [Mount("/sub", app=_app(inner_container))])

    with TestClient(outer) as client:
        assert client.get("/sub/x").text == "inner"
        assert "inner finalized" not in events

    assert "inner finalized" in events
    assert inner_container.closed


def test_container_mounted_two_levels_deep_is_closed() -> None:
    events: list[str] = []
    deep_container = _container("deep", events)
    middle = _app(routes=[Mount("/deep", app=_app(deep_container))])
    outer = _app(_container("outer", events), [Mount("/mid", app=middle)])

    with TestClient(outer) as client:
        assert client.get("/mid/deep/x").text == "deep"

    assert "deep finalized" in events
    assert deep_container.closes == 1


def test_host_mounted_container_is_closed() -> None:
    events: list[str] = []
    host_container = _container("host", events)
    outer = fastapi.FastAPI(routes=[Host("api.example.com", app=_app(host_container))])
    setup_di(outer, _container("outer", events))

    with TestClient(outer, base_url="http://api.example.com") as client:
        assert client.get("/x").text == "host"

    assert host_container.closes == 1


def test_app_mounted_twice_closes_its_container_once() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    inner = _app(inner_container)
    outer = _app(_container("outer", events), [Mount("/a", app=inner), Mount("/b", app=inner)])

    with TestClient(outer) as client:
        assert client.get("/a/x").text == "inner"

    assert inner_container.closes == 1


def test_mounts_sharing_a_container_close_it_once() -> None:
    events: list[str] = []
    shared = _container("shared", events)
    sharing_apps = [_app(), _app()]
    for app in sharing_apps:
        app.state.di_container = shared
    outer = _app(shared, [Mount("/a", app=sharing_apps[0]), Mount("/b", app=sharing_apps[1])])

    with TestClient(outer) as client:
        assert client.get("/a/x").text == "shared"

    assert shared.closes == 1


def test_mount_added_after_setup_di_is_closed() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    outer = _app(_container("outer", events))
    outer.mount("/sub", _app(inner_container))

    with TestClient(outer) as client:
        assert client.get("/sub/x").text == "inner"

    assert inner_container.closes == 1


def test_mounts_without_setup_di_are_ignored() -> None:
    async def raw_asgi(scope: typing.Any, receive: typing.Any, send: typing.Any) -> None:  # noqa: ANN401
        await PlainTextResponse("raw")(scope, receive, send)

    events: list[str] = []
    outer_container = _container("outer", events)
    outer = _app(
        outer_container,
        [
            Mount("/plain", app=_app()),
            Mount("/starlette", app=Starlette(routes=[Route("/x", PlainTextResponse("starlette"))])),
            Mount("/raw", app=raw_asgi),
            Mount("/routes", routes=[Route("/x", PlainTextResponse("routes"))]),
        ],
    )

    with TestClient(outer) as client:
        assert client.get("/raw").text == "raw"
        assert client.get("/starlette/x").text == "starlette"
        assert client.get("/x").text == "outer"

    assert outer_container.closes == 1


def test_mounted_container_reopens_across_lifespan_cycles() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    outer = _app(_container("outer", events), [Mount("/sub", app=_app(inner_container))])

    cycles = 2
    for _ in range(cycles):
        with TestClient(outer) as client:
            assert client.get("/sub/x").status_code == status.HTTP_200_OK

    assert events.count("inner finalized") == cycles
    assert inner_container.closes == cycles
