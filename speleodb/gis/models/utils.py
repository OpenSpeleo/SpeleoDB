# -*- coding: utf-8 -*-

from __future__ import annotations

import binascii
import os


def generate_random_token() -> str:
    return binascii.hexlify(os.urandom(20)).decode()
