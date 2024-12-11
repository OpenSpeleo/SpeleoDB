#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Used to generate DJANGO_FIELD_ENCRYPTION_KEY value"

    def handle(self, *args, **kwargs):
        self.stdout.write(base64.urlsafe_b64encode(os.urandom(32)).decode())
