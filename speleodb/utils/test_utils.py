#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import namedtuple
from itertools import product
from itertools import starmap
from typing import Any


def named_product(**items: Any) -> list[Any]:
    Product = namedtuple("Product", list(items.keys()))  # type: ignore[misc]  # noqa: PYI024
    return list(starmap(Product, product(*items.values())))
