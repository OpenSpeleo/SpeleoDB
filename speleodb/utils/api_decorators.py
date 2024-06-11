#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wrapt
from rest_framework import exceptions

from speleodb.utils.helpers import wrap_response_with_status


@wrapt.decorator
def request_wrapper(wrapped, instance, args, kwargs):
    try:
        request = kwargs["request"]
    except KeyError:
        request = args[0]

    try:
        inner_fn = getattr(instance, f"_{request.method.lower()}")
    except AttributeError as e:
        raise exceptions.MethodNotAllowed(request.method) from e

    return wrap_response_with_status(inner_fn, request, *args, **kwargs)


def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes
            # this call is needed for request permissions
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)

        return decorated_func

    return decorator
