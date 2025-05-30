#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any


class SingletonMetaClass(type):
    _instance: Any | None = None

    def __call__(cls, *args: list[Any], **kwargs: dict[str, Any]) -> Any:
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)

        return cls._instance
