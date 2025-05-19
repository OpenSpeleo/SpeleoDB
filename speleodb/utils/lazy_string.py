from collections import UserString
from collections.abc import Callable
from typing import Any


class LazyString(UserString):
    _func: Callable[..., str]
    _value: str | None = None

    def __new__(cls, seq: Callable[..., str] | str | None = None) -> Any:
        if isinstance(seq, str):
            # Many UserString's functions like `lower`, `__add__` and so on wrap
            # returned values with a call to `self.__class__(...)` to ensure the
            # result is of the same type as the original class.
            # However, as the result of all of such methods is always a string,
            # there's no need to create a new instance of a `LazyString`
            return seq

        return super().__new__(cls)

    def __init__(self, seq: Callable[..., str]) -> None:
        self._func = seq

    @property
    def data(self) -> str:
        if self._value is None:
            self._value = self._func()
        return self._value

    @data.setter
    def data(self, value: str) -> None:
        self._value = value
