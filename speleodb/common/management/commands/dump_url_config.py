import json
from io import StringIO
from pathlib import Path
from typing import Any

from django.core.management import BaseCommand
from django.core.management import call_command


def collect_and_filter_urls() -> list[dict[str, str]]:
    output_buffer = StringIO()
    call_command("show_urls", "--format=json", stdout=output_buffer)

    # Parse the JSON
    data: list[dict[str, str]] = json.loads(output_buffer.getvalue())

    def filter_fn(url_config: dict[str, str]) -> bool:
        return not url_config["url"].startswith(
            (
                "/silk/",
                "/__debug__/",
                "/debug_mode/",
                "/admin/",
            )
        )

    return sorted(filter(filter_fn, data), key=lambda cfg: cfg["url"])


class Command(BaseCommand):
    help = (
        "Loads all URLs from `show_urls` management command and only preserve the "
        "essential ones."
    )

    def handle(self, *args: Any, **kwargs: Any) -> None:
        data = collect_and_filter_urls()

        with (Path(__file__).parent.parent.parent / "tests/url_config.json").open(
            mode="w"
        ) as fp:
            json.dump(data, fp, indent=4)
