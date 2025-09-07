# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

from deepdiff import DeepDiff

from speleodb.common.management.commands.dump_url_config import collect_and_filter_urls


def test_url_configuration() -> None:
    """
    Tests URL resolution and path generation for various endpoints.
    """
    json_f = Path(__file__).parent / "url_config.json"
    assert json_f.exists()
    assert json_f.is_file()

    with json_f.open("r") as fp:
        json_data = json.load(fp)

    url_config = collect_and_filter_urls()

    ddiff = DeepDiff(json_data, url_config, ignore_order=True)
    assert ddiff.get("values_changed", None) is None
