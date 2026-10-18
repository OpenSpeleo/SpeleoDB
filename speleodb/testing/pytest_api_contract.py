"""Optional rendered-response contract audit for the existing integration suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings

from speleodb.testing.api_contract import CONTRACT_METADATA
from speleodb.testing.api_contract import CONTRACT_OBSERVATIONS

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.main import Session


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--api-contract-report", help="Write rendered API observations as JSON"
    )
    parser.addoption(
        "--api-contract-enforce",
        action="store_true",
        help="Fail on any response contract violation",
    )


@pytest.fixture(scope="session", autouse=True)
def api_contract_observer(request: pytest.FixtureRequest) -> Generator[None]:
    if request.config.getoption(
        "--api-contract-enforce"
    ) and not request.config.getoption("--api-contract-report"):
        raise pytest.UsageError("--api-contract-enforce requires --api-contract-report")
    if not request.config.getoption("--api-contract-report"):
        yield
        return
    with override_settings(
        MIDDLEWARE=[
            *settings.MIDDLEWARE,
            "speleodb.testing.api_contract.APIContractMiddleware",
        ]
    ):
        yield


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: Session, exitstatus: int) -> Generator[None]:
    # Audit plugins may change exitstatus after the last test has completed.
    yield
    destination = session.config.getoption("--api-contract-report")
    if not destination:
        return
    if session.config.getoption("--api-contract-enforce") and any(
        "error" in item for item in CONTRACT_OBSERVATIONS
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                **CONTRACT_METADATA,
                "exit_status": int(session.exitstatus),
                "test_invocation": list(session.config.invocation_params.args),
                "observations": CONTRACT_OBSERVATIONS,
            },
            indent=2,
        )
        + "\n"
    )


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: Config
) -> None:
    if config.getoption("--api-contract-report"):
        operations = {item["operation_id"] for item in CONTRACT_OBSERVATIONS}
        errors = [item for item in CONTRACT_OBSERVATIONS if "error" in item]
        terminalreporter.write_sep(
            "=",
            f"API contract: {len(operations)} operations, "
            f"{len(CONTRACT_OBSERVATIONS)} responses, {len(errors)} violations",
        )
