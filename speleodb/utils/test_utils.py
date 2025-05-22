#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import namedtuple
from itertools import product
from itertools import starmap
from typing import Any


def named_product(**items: dict[Any, Any]) -> starmap[Any]:
    Product = namedtuple("Product", list(items.keys()))  # noqa: PYI024
    return starmap(Product, product(*items.values()))
