from collections.abc import Callable
from typing import Generic
from typing import TypeVar

T = TypeVar("T")
RT = TypeVar("RT")


class _ClassPropertyDescriptor(Generic[T, RT]):
    def __init__(self, fget: Callable[[type[T]], RT]) -> None:
        self.fget = fget

    def __get__(self, instance: T | None, owner: type[T] | None = None, /) -> RT:
        if owner is None:
            if instance is None:
                raise ValueError
            owner = type(instance)
        return self.fget(owner)


def classproperty(func: Callable[[T], RT]) -> _ClassPropertyDescriptor[T, RT]:
    return _ClassPropertyDescriptor(func)  # type: ignore[arg-type]
