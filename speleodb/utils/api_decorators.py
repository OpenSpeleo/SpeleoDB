#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections.abc import Callable
from typing import Any

from rest_framework import permissions
from rest_framework.generics import GenericAPIView


def method_permission_classes(
    classes: tuple[type[permissions.BasePermission]],
) -> Callable[..., Any]:
    for _cls in classes:
        if not issubclass(_cls, permissions.BasePermission):
            raise TypeError(
                f"`{_cls}` is of an improper type - Expected `BasePermission`."
            )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def decorated_func(self: GenericAPIView, *args: Any, **kwargs: Any) -> Any:  # type: ignore[type-arg,unused-ignore]
            self.permission_classes = classes
            # this call is needed for request permissions
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)

        return decorated_func

    return decorator
