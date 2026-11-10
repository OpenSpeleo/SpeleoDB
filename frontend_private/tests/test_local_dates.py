from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import TYPE_CHECKING

from django.utils import timezone

from frontend_private.tests.test_template_lint_regressions import ENTITY_ID
from frontend_private.tests.test_template_lint_regressions import descendants
from frontend_private.tests.test_template_lint_regressions import render_page

if TYPE_CHECKING:
    from django.test.html import Element


def displayed_dates(page: Element) -> list[tuple[str, str]]:
    dates: list[tuple[str, str]] = []
    for element in descendants(page):
        attributes = dict(element.attributes)
        if element.name == "time" and "data-local-date" in attributes:
            value = attributes["datetime"]
            mode = attributes["data-local-date"]
            assert value is not None
            assert mode is not None
            dates.append((value, mode))
    return dates


def test_lock_history_preserves_instants_across_repeated_dst_hour() -> None:
    acquired = dt.datetime(2026, 11, 1, 5, 30, 17, tzinfo=dt.UTC)
    released = dt.datetime(2026, 11, 1, 6, 30, 29, tzinfo=dt.UTC)
    mutex = SimpleNamespace(
        creation_date=acquired,
        modified_date=released,
        user=SimpleNamespace(name="Diver"),
        is_active=False,
    )
    with timezone.override("America/New_York"):
        page = render_page("pages/project/mutex_history.html", mutexes=[mutex])
    dates = displayed_dates(page)
    assert all(mode == "datetime" for _, mode in dates)
    assert [dt.datetime.fromisoformat(value) for value, _ in dates] == [
        acquired,
        released,
        acquired,
        released,
    ]


def test_projects_show_modification_and_actual_lock_creation_in_both_layouts() -> None:
    modified = dt.datetime(2026, 1, 2, 0, 15, tzinfo=dt.UTC)
    acquired = dt.datetime(2026, 1, 1, 23, 45, tzinfo=dt.UTC)
    project = SimpleNamespace(
        id=ENTITY_ID,
        name="Cave",
        type="compass",
        country=SimpleNamespace(code="US"),
        modified_date=modified,
    )
    project_data = SimpleNamespace(
        project=project,
        active_mutex=SimpleNamespace(
            creation_date=acquired, user=SimpleNamespace(name="Diver")
        ),
    )
    page = render_page(
        "pages/projects.html", projects_by_country={"United States": [project_data]}
    )
    dates = displayed_dates(page)
    assert all(mode == "datetime" for _, mode in dates)
    assert [dt.datetime.fromisoformat(value) for value, _ in dates] == [
        modified,
        acquired,
        modified,
        acquired,
    ]


def test_experiment_dates_remain_calendar_days_and_missing_end_stays_empty() -> None:
    experiment = SimpleNamespace(
        id=ENTITY_ID, start_date=dt.date(2026, 1, 2), end_date=None
    )
    with timezone.override("Pacific/Honolulu"):
        page = render_page(
            "pages/experiments.html",
            experiment_perms=[SimpleNamespace(experiment=experiment)],
        )
    assert displayed_dates(page) == [("2026-01-02", "date")] * 2


def test_sensor_expiry_keeps_calendar_day_and_missing_battery_placeholder() -> None:
    sensor = SimpleNamespace(
        active_installs=[
            SimpleNamespace(
                expiracy_memory_date=dt.date(2026, 1, 2), expiracy_battery_date=None
            )
        ]
    )
    page = render_page("snippets/sensor_table.html", sensors=[sensor])
    assert displayed_dates(page) == [("2026-01-02", "date")]
    assert any(
        element.name == "td" and element.children == ["-"]
        for element in descendants(page)
    )


def test_public_release_date_preserves_timestamp_for_browser_timezone() -> None:
    published = "2026-01-02T00:15:27Z"
    page = render_page(
        "pages/download.html",
        compass_sidecar_version="test-release",
        compass_sidecar_pub_date=published,
    )
    assert displayed_dates(page) == [(published, "datetime")]
