#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from collections.abc import Sequence
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Merge all the different `.env` files inside `.env/production` into a single file "
        "`.env` file at the project root level"
    )

    def merge_dot_env_files(self, input_files: Sequence[Path], out_file: Path) -> None:
        merged_content = ""
        for merge_file in input_files:
            if not merge_file.exists():
                logger.warning(f"The file `{merge_file}` does not exists... Skipping !")
                continue
            merged_content += merge_file.read_text()
            merged_content += os.linesep
        out_file.write_text(merged_content)

    def handle(self, *args, **kwargs):
        base_project_dir = Path(__file__).parents[4].resolve()
        source_dotenv_dir = base_project_dir / ".envs" / ".production"
        input_files = [
            source_dotenv_dir / ".django",
            source_dotenv_dir / ".postgres",
        ]
        output_file = base_project_dir / ".env"
        self.merge_dot_env_files(input_files, output_file)