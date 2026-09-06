import fastapi
import modern_di
import pytest
from modern_di import Scope, providers
from starlette.requests import HTTPConnection

from modern_di_fastapi import build_di_container, main, setup_di
from tests.dependencies import Dependencies


class StubConnection(HTTPConnection):
    """A connection kind this package does not know about."""


async def test_a_connection_kind_is_added_by_its_provider_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """INVARIANT: a connection kind's scope and context come from its ContextProvider, nowhere else.

    Broken by re-stating a connection kind anywhere outside ``_CONNECTION_PROVIDERS`` — an
    isinstance ladder in ``build_di_container``, or naming the two providers literally in
    ``setup_di``. Either duplicate keeps working until the pair drifts, and then a connection
    resolves at the wrong scope or with an empty context, which no other test would notice
    because both existing kinds are hardcoded to the same values the tuple holds. The tuple
    being the single source is what makes "add a connection kind" a one-line change rather
    than an edit to two dispatches that must agree.
    """
    stub_provider = providers.ContextProvider(scope=Scope.ACTION, context_type=StubConnection)
    monkeypatch.setattr(main, "_CONNECTION_PROVIDERS", (*main._CONNECTION_PROVIDERS, stub_provider))  # noqa: SLF001

    app = fastapi.FastAPI()
    setup_di(app, modern_di.Container(groups=[Dependencies]))
    connection = StubConnection({"type": "http", "app": app, "headers": []})

    async with app.state.di_container:
        async for container in build_di_container(connection):
            assert container.scope is Scope.ACTION
            assert container.resolve(StubConnection) is connection
