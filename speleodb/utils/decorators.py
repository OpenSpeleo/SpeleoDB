import functools
from typing import Any

__all__ = ["classproperty"]


class classproperty(property):  # noqa: N801
    """
    Similar to `property`, but allows class-level properties.  That is,
    a property whose getter is like a `classmethod`.

    The wrapped method may explicitly use the `classmethod` decorator (which
    must become before this decorator), or the `classmethod` may be omitted
    (it is implicit through use of this decorator).

    .. note::

        classproperty only works for *read-only* properties.  It does not
        currently allow writeable/deletable properties, due to subtleties of how
        Python descriptors work.  In order to implement such properties on a class
        a metaclass for that class must be implemented.

    Parameters
    ----------
    fget : callable
        The function that computes the value of this property (in particular,
        the function when this is used as a decorator) a la `property`.

    doc : str, optional
        The docstring for the property--by default inherited from the getter
        function.

    Examples
    --------

        >>> class Foo:
        ...     _bar_internal = 1
        ...     @classproperty
        ...     def bar(cls):
        ...         return cls._bar_internal + 1
        ...
        >>> Foo.bar
        2
        >>> foo_instance = Foo()
        >>> foo_instance.bar
        2
        >>> foo_instance._bar_internal = 2
        >>> foo_instance.bar  # Ignores instance attributes
        2
    """

    def __init__(self, fget: Any | None, doc: str | None = None) -> None:
        fget = self._wrap_fget(fget)
        super().__init__(fget=fget, doc=doc)

        # There is a buglet in Python where self.__doc__ doesn't
        # get set properly on instances of property subclasses if
        # the doc argument was used rather than taking the docstring
        # from fget
        # Related Python issue: https://bugs.python.org/issue24766
        if doc is not None:
            self.__doc__ = doc

    def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
        return self.fget.__wrapped__(owner)  # type: ignore[union-attr]
        # return super.__get__(instance, owner)

    def getter(self, fget: Any) -> Any:
        return super().getter(self._wrap_fget(fget))

    def setter(self, fset: Any) -> property:
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties"
        )

    def deleter(self, fdel: Any) -> property:
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties"
        )

    @staticmethod
    def _wrap_fget(orig_fget: Any) -> Any:
        if isinstance(orig_fget, classmethod):
            orig_fget = orig_fget.__func__

        @functools.wraps(orig_fget)
        def fget(obj: Any) -> Any:
            return orig_fget(obj.__class__)

        return fget
