# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import os
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Used to generate DJANGO_FIELD_ENCRYPTION_KEY value"

    def handle(self, *args: Any, **kwargs: Any) -> None:
        self.stdout.write(base64.urlsafe_b64encode(os.urandom(32)).decode())
