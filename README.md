# modern-di-fastapi

[![PyPI version](https://img.shields.io/pypi/v/modern-di-fastapi.svg)](https://pypi.org/project/modern-di-fastapi/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/modern-di-fastapi.svg)](https://pypi.org/project/modern-di-fastapi/)
[![Downloads](https://img.shields.io/pypi/dm/modern-di-fastapi.svg)](https://pypistats.org/packages/modern-di-fastapi)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/modern-python/modern-di-fastapi/actions/workflows/ci.yml)
[![CI](https://github.com/modern-python/modern-di-fastapi/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/modern-di-fastapi/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/modern-python/modern-di-fastapi.svg)](https://github.com/modern-python/modern-di-fastapi/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/modern-di-fastapi)](https://github.com/modern-python/modern-di-fastapi/stargazers)
[![Context7](https://img.shields.io/badge/Context7-docs-blue)](https://context7.com/modern-python/modern-di-fastapi)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

[Modern-DI](https://github.com/modern-python/modern-di) integration for [FastAPI](https://fastapi.tiangolo.com).

Usage example: [fastapi-sqlalchemy-template](https://github.com/modern-python/fastapi-sqlalchemy-template)

## Installation

```bash
uv add modern-di-fastapi      # or: pip install modern-di-fastapi
```

## Usage

`setup_di` registers the container and builds a per-request child container automatically; `FromDI` resolves a provider (or type) into a route parameter.

```python
import dataclasses

import fastapi
from modern_di import Container, Group, Scope, providers
from modern_di_fastapi import FromDI, setup_di


@dataclasses.dataclass(kw_only=True)
class Settings:
    debug: bool = True


@dataclasses.dataclass(kw_only=True)
class UserService:
    settings: Settings  # auto-injected by type


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    user_service = providers.Factory(scope=Scope.REQUEST, creator=UserService)


app = fastapi.FastAPI()
container = Container(groups=[Dependencies], validate=True)
setup_di(app, container)


@app.get("/")
async def index(user_service: UserService = FromDI(Dependencies.user_service)) -> dict[str, bool]:
    return {"debug": user_service.settings.debug}
```

The framework `Request` / `WebSocket` are resolvable within DI via the pre-built `fastapi_request_provider` / `fastapi_websocket_provider` context providers.

## API

| Symbol | Description |
|---|---|
| `setup_di(app, container)` | Stores the container on `app.state` and appends a lifespan that closes it on shutdown (merges with any existing `lifespan=`) |
| `FromDI(provider, *, use_cache=True)` | FastAPI `Depends` that resolves a provider (or type) from the per-request child container |
| `fetch_di_container(app)` | Returns the app-scoped container from `app.state` |
| `build_di_container(connection)` | FastAPI `Depends` callable that yields the per-request child container — `REQUEST` scope for an HTTP request, `SESSION` scope for a WebSocket |
| `fastapi_request_provider` | `ContextProvider` for the current `fastapi.Request` |
| `fastapi_websocket_provider` | `ContextProvider` for the current `fastapi.WebSocket` |

## 📦 [PyPI](https://pypi.org/project/modern-di-fastapi)

## 📝 [License](LICENSE)

## Part of `modern-python`

Browse the full list of templates and libraries in
[`modern-python`](https://github.com/modern-python) — see the org profile for the categorized index.

## modern-di ecosystem

Built on [`modern-di`](https://github.com/modern-python/modern-di), a dependency-injection framework with IoC container and scopes. Integrations:

- [`modern-di-fastapi`](https://github.com/modern-python/modern-di-fastapi) — this package
- [`modern-di-litestar`](https://github.com/modern-python/modern-di-litestar) — Litestar
- [`modern-di-faststream`](https://github.com/modern-python/modern-di-faststream) — FastStream
- [`modern-di-typer`](https://github.com/modern-python/modern-di-typer) — Typer
- [`modern-di-pytest`](https://github.com/modern-python/modern-di-pytest) — pytest

