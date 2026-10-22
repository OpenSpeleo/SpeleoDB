"""Run all backend coverage by default; exclusions must be requested explicitly."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.reports import CollectReport
    from _pytest.reports import TestReport
    from _pytest.runner import CallInfo


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--light",
        action="store_true",
        default=False,
        help="Explicitly deselect tests marked skip_if_lighttest.",
    )
    parser.addoption(
        "--offline",
        action="store_true",
        default=False,
        help="Explicitly deselect tests marked skip_if_offline.",
    )


def pytest_configure(config: Config) -> None:
    for marker in (
        "skip_if_lighttest: excluded only by the explicit --light option",
        "skip_if_offline: excluded only by the explicit --offline option",
        "live_services: real worker or broker integration; enabled by default",
        "local_infrastructure: local GitLab routing/bootstrap; enabled by default",
    ):
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    exclusions: list[str] = []
    if config.getoption("--light"):
        exclusions.append("skip_if_lighttest")
    if config.getoption("--offline"):
        exclusions.append("skip_if_offline")
    deselected: list[Item] = [
        item
        for item in items
        if any(item.get_closest_marker(marker) for marker in exclusions)
    ]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item not in deselected]


def _reject_skip(report: TestReport | CollectReport) -> None:
    if report.skipped:
        reason: str = str(report.longrepr)
        report.outcome = "failed"
        report.longrepr = (
            "Implicit test skips are forbidden. Supply the required test services "
            "or explicitly deselect coverage with -m, --ignore, --light or --offline."
            f"\nOriginal skip: {reason}"
        )


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: Item,
    call: CallInfo[None],
) -> Generator[None, TestReport, TestReport]:
    report: TestReport = yield
    _reject_skip(report)
    return report


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, CollectReport, CollectReport]:
    report: CollectReport = yield
    _reject_skip(report)
    return report
