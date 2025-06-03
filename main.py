#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os

import django
from dotenv import load_dotenv

load_dotenv(".envs/.local/.django")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Initialize Django
django.setup()

if __name__ == "__main__":
    from speleodb.users.models import User

    user = User.objects.get(email="contact@speleodb.com")
    print(f"{user=}")  # noqa: T201
