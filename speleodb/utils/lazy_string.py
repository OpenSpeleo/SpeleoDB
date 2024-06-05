# MIT License

# Copyright (c) 2020 Oleksandr Oblovatnyi

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Original Software: https://github.com/o3bvv/lazy-string/

# Deactivate Code Linter
# ruff: noqa

import sys

if sys.version_info >= (3, 9):
    from collections.abc import Callable
    from collections.abc import Mapping

    List = list
    Tuple = tuple

else:
    from typing import Callable
    from typing import List
    from typing import Mapping
    from typing import Tuple

from collections import UserString
from typing import Any
from typing import TypeVar
from typing import Union

LazyString = TypeVar("LazyString")


class LazyString(UserString):
    """
    A string with delayed evaluation.

    :param func:   Callable (e.g., function) returning a string.
    :param args:   Optional positional arguments which will be passed to the ``func``.
    :param kwargs: Optional keyword arguments which will be passed to the ``func``.

    """

    __slots__ = (
        "_func",
        "_args",
    )

    def __new__(
        cls, func: Union[Callable, str], *args: Tuple, **kwargs: Mapping
    ) -> object:
        if isinstance(func, str):
            # Many UserString's functions like `lower`, `__add__` and so on wrap
            # returned values with a call to `self.__class__(...)` to ensure the
            # result is of the same type as the original class.
            # However, as the result of all of such methods is always a string,
            # there's no need to create a new instance of a `LazyString`
            return func

        return object.__new__(cls)

    def __init__(
        self, func: Callable[..., str], *args: Tuple, **kwargs: Mapping
    ) -> None:
        self._func = func
        self._args = args
        self._kwargs = kwargs

    @property
    def data(self) -> str:
        return self._func(*self._args, **self._kwargs)

    def __getnewargs_ex__(self) -> Tuple[Tuple, Mapping]:
        args = (self._func,) + self._args
        return (args, self._kwargs)

    def __getstate__(self) -> Tuple[Callable, Tuple, Mapping]:
        return (self._func, self._args, self._kwargs)

    def __setstate__(self, state: Tuple[Callable, Tuple, Mapping]) -> None:
        self._func, self._args, self._kwargs = state

    def __getattr__(self, name: str) -> Any:
        return getattr(self.data, name)

    def __dir__(self) -> List[str]:
        return dir(str)

    def __copy__(self) -> LazyString:
        return self

    def __repr__(self) -> str:
        try:
            r = repr(str(self.data))
            return f"{self.__class__.__name__}({r})"
        except Exception:
            return "<%s broken>" % self.__class__.__name__
