# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")
RT = TypeVar("RT")


class _ClassPropertyDescriptor[T, RT]:
    def __init__(self, fget: Callable[[type[T]], RT]) -> None:
        self.fget = fget

    def __get__(self, instance: T | None, owner: type[T] | None = None, /) -> RT:
        if owner is None:
            if instance is None:
                raise ValueError
            owner = type(instance)
        return self.fget(owner)


def classproperty[T, RT](func: Callable[[T], RT]) -> _ClassPropertyDescriptor[T, RT]:
    return _ClassPropertyDescriptor(func)  # type: ignore[arg-type]
