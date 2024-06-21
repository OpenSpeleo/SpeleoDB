from collections.abc import Callable
from typing import Any
from typing import Generic
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


class classproperty(Generic[T, R]):  # noqa: N801
    def __init__(self, func: Callable[[type[T]], R]) -> None:
        self.func = func

    def __get__(self, obj: Any, cls: type[T]) -> R:
        return self.func(cls)
