# The lifespan composition is ours

`setup_di` installs the container's open/close onto the public `app.router.lifespan_context` through
this package's own `_compose_lifespan`, not through `fastapi.routing._merge_lifespan_context`, which
it used until 2.8.0. That helper is private while `pyproject.toml` pins `fastapi>=0.100,<1`, so a
rename anywhere in that range is an `ImportError` at `setup_di` time, at startup, for every app on a
routine FastAPI upgrade. It also composes two lifespans and merges their yielded states, while a
`Container` is a bare async context manager yielding nothing: wrapping it into lifespan shape is
most of `_compose_lifespan` already, and the merge would rebuild the user's state as a fresh dict
rather than pass it through. Our wrapper also enters the container with `async with`, so a second
lifespan cycle reopens it instead of raising `ContainerClosedError`.
