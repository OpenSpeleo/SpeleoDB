"""Root pytest hooks for the mandatory GitLab creation budget."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from speleodb.testing.gitlab_audit import ALLOCATION_ENV
from speleodb.testing.gitlab_audit import LEDGER_ENV
from speleodb.testing.gitlab_audit import NODE_ENV
from speleodb.testing.gitlab_audit import PHASE_ENV
from speleodb.testing.gitlab_audit import finish_run
from speleodb.testing.gitlab_audit import join_run
from speleodb.testing.gitlab_audit import start_run

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.terminal import TerminalReporter


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--gitlab-audit-deny-create",
        action="store_true",
        default=False,
        help="Trace and reject every GitLab repository creation before transport.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: Config) -> None:
    if getattr(config.option, "numprocesses", None):
        raise pytest.UsageError(
            "GitLab repository leases require serial pytest execution"
        )
    if LEDGER_ENV in os.environ:
        join_run(deny_create=config.getoption("--gitlab-audit-deny-create"))
    else:
        start_run(deny_create=config.getoption("--gitlab-audit-deny-create"))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: Item) -> None:
    os.environ[NODE_ENV] = item.nodeid
    os.environ[PHASE_ENV] = "setup"
    os.environ.pop(ALLOCATION_ENV, None)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: Item) -> None:
    os.environ[PHASE_ENV] = "call"


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: Item) -> None:
    os.environ[PHASE_ENV] = "teardown"


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    summary = finish_run()
    if summary["violations"] or summary["unresolved"]:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    summary = finish_run()
    terminalreporter.write_sep(
        "=",
        f"GitLab: {summary['created']}/{summary['budget']} repositories, "
        f"{summary['creation_requests']} creation POSTs, "
        f"{summary['violations']} violations",
    )
    terminalreporter.write_line(f"Audit: .artifacts/gitlab/{summary['run_id']}")
    if summary["unresolved"]:
        terminalreporter.write_line(f"Unresolved creations: {summary['unresolved']}")
