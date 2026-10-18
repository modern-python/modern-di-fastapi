import logging
import typing

import anyio
import fastapi
import pytest
from modern_di import Container, Group, Scope, providers

import modern_di_fastapi
from modern_di_fastapi import main


class _First: ...


class _Second: ...


def _app(log: list[str], *, second_finalizer_delay: float) -> fastapi.FastAPI:
    async def finalize_first(_: _First) -> None:
        await anyio.sleep(0.01)
        log.append("first")

    async def finalize_second(_: _Second) -> None:
        await anyio.sleep(second_finalizer_delay)
        log.append("second")

    class G(Group):
        first = providers.Factory(
            scope=Scope.REQUEST, creator=_First, cache=providers.CacheSettings(finalizer=finalize_first)
        )
        second = providers.Factory(
            scope=Scope.REQUEST, creator=_Second, cache=providers.CacheSettings(finalizer=finalize_second)
        )

    app = fastapi.FastAPI()
    modern_di_fastapi.setup_di(app, Container(groups=[G]), manage_lifespan=False)

    @app.get("/")
    async def endpoint(
        first: typing.Annotated[_First, modern_di_fastapi.FromDI(_First)],
        second: typing.Annotated[_Second, modern_di_fastapi.FromDI(_Second)],
    ) -> None:
        assert isinstance(first, _First)
        assert isinstance(second, _Second)
        await anyio.sleep_forever()

    return app


async def _call_cancelled_mid_handler(app: fastapi.FastAPI) -> None:
    async def receive() -> dict[str, typing.Any]:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }  # pragma: no cover -- GET handlers never read the body

    async def send(_: typing.Any) -> None: ...  # noqa: ANN401

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 1),
        "server": ("testserver", 80),
        "app": app,
    }
    with anyio.move_on_after(0.05):
        await app(scope, receive, send)


async def test_a_cancelled_request_still_runs_every_child_finalizer() -> None:
    log: list[str] = []

    await _call_cancelled_mid_handler(_app(log, second_finalizer_delay=0.01))

    assert log == ["second", "first"]


async def test_a_hung_child_finalizer_is_abandoned_after_the_bound(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(main, "_CHILD_CLOSE_TIMEOUT", 0.05)
    log: list[str] = []

    with anyio.fail_after(1), caplog.at_level(logging.WARNING, logger=main.__name__):
        await _call_cancelled_mid_handler(_app(log, second_finalizer_delay=10))

    assert log == []
    assert [record.getMessage() for record in caplog.records] == [
        "Closing the child container did not finish within 0.05 s; its remaining finalizers did not run"
    ]
