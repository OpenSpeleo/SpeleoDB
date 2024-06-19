#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import namedtuple
from itertools import product
from itertools import starmap


def named_product(**items):
    Product = namedtuple("Product", items.keys())  # noqa: PYI024
    return starmap(Product, product(*items.values()))
