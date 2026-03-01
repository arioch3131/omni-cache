"""Helper functions for pool interfaces."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import TypeVar

T = TypeVar("T")

# pylint: disable=duplicate-code


@contextmanager
def _sync_borrow_logic(
    get_func: Callable[[float | None], T | None],
    put_func: Callable[[T, float | None], bool],
    timeout: float | None,
) -> Generator[T, None, None]:
    obj = get_func(timeout)
    if obj is None:
        raise RuntimeError("No object available from pool")
    try:
        yield obj
    finally:
        put_func(obj, None)


@asynccontextmanager
async def _async_borrow_logic(
    get_func: Callable[[float | None], Awaitable[T | None]],
    put_func: Callable[[T, float | None], Awaitable[bool]],
    timeout: float | None,
) -> AsyncGenerator[T, None]:
    obj = await get_func(timeout)
    if obj is None:
        raise RuntimeError("No object available from pool")
    try:
        yield obj
    finally:
        await put_func(obj, None)
