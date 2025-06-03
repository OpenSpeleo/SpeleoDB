#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

    from django.core.management import execute_from_command_line

    # This allows easy placement of apps within the interior
    # speleodb directory.
    current_path = Path(__file__).parent.resolve()
    sys.path.append(str(current_path / "speleodb"))

    execute_from_command_line(sys.argv)
