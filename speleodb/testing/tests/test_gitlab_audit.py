"""Exercise accounting without creating any GitLab repositories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
import requests

from speleodb.testing.gitlab_audit import ALLOCATION_ENV
from speleodb.testing.gitlab_audit import CREATION_ALLOCATIONS
from speleodb.testing.gitlab_audit import LEDGER_ENV
from speleodb.testing.gitlab_audit import MAX_REPOSITORIES
from speleodb.testing.gitlab_audit import AuditLedger
from speleodb.testing.gitlab_audit import RepositoryBudgetError
from speleodb.testing.gitlab_audit import join_run


@pytest.fixture
def ledger(tmp_path: Path) -> AuditLedger:
    ledger = AuditLedger(tmp_path / "audit" / "ledger.sqlite3")
    ledger.initialize()
    return ledger


def test_unallocated_creation_is_durable_even_when_exception_is_caught(
    ledger: AuditLedger,
) -> None:
    with pytest.raises(RepositoryBudgetError, match="no matching explicit allocation"):
        ledger.before_create(None, "42", "unexpected")
    summary = ledger.summary()
    assert summary["created"] == 0
    assert summary["creation_requests"] == 0
    assert summary["violations"] == 1
    assert summary["events"][0]["stack"]
    assert summary["events"][0]["pid"] == os.getpid()


def test_named_allocations_match_the_strict_repository_budget() -> None:
    assert len(CREATION_ALLOCATIONS) == MAX_REPOSITORIES == 9  # noqa: PLR2004


def test_failed_response_with_an_id_never_counts_as_created(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("manager-new", "42", "same-path")
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=None, error_type="Timeout")
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=400, project_id="unrelated-error-id")
    summary = ledger.summary()
    assert summary["created"] == 0
    assert summary["allocations"][0]["project_id"] is None
    assert summary["unresolved"] == ["manager-new"]


def test_success_without_project_id_stays_uncertain(ledger: AuditLedger) -> None:
    ledger.reserve("manager-new", "42", "same-path")
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=201)
    summary = ledger.summary()
    assert summary["created"] == 0
    assert summary["unresolved"] == ["manager-new"]


@pytest.mark.parametrize(
    "route",
    [
        "projects/1/fork",
        "projects/group%2Fproject/fork",
        "projects/import",
        "projects/remote-import",
        "projects/remote-import-s3",
        "projects/user/1",
        "groups/import",
        "bulk_imports",
        "offline_imports",
        "import/github",
    ],
)
def test_alternate_creation_routes_cannot_bypass_guard(
    ledger: AuditLedger, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    monkeypatch.setenv(LEDGER_ENV, str(ledger.path))
    with pytest.raises(RepositoryBudgetError, match="outside the test allocations"):
        requests.post(f"http://127.0.0.1:1/api/v4/{route}", timeout=1)
    assert ledger.summary()["violations"] == 1
    assert ledger.summary()["created"] == 0


def test_identity_cannot_change_and_deleted_allocation_cannot_create_again(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("canonical-admin", "42", "first")
    with pytest.raises(RepositoryBudgetError, match="cannot change"):
        ledger.reserve("canonical-admin", "42", "replacement")
    event_id, name = ledger.before_create("canonical-admin", "42", "first")
    ledger.after_create(event_id, name, status=201, project_id="100")
    with ledger.transaction() as connection:
        ledger.event(connection, event="cleanup", project_id="100", outcome="HTTP 202")
    assert ledger.summary()["allocations"][0]["cleanup_outcome"] is None
    with ledger.transaction() as connection:
        ledger.event(
            connection,
            event="cleanup",
            project_id="100",
            outcome="verified-marked-for-deletion",
        )
        ledger.event(
            connection,
            event="cleanup",
            project_id="100",
            outcome="verified-absent",
        )
    with pytest.raises(RepositoryBudgetError, match="after success"):
        ledger.before_create("canonical-admin", "42", "first")
    summary = ledger.summary()
    assert summary["created"] == 1
    assert summary["allocations"][0]["project_id"] == "100"
    assert summary["allocations"][0]["cleanup_outcome"] == "verified-absent"
    ledger.export()
    assert "cleanup=verified-absent" in (ledger.path.parent / "summary.txt").read_text()


def test_retries_share_identity_and_uncertain_outcome_requires_readback(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("manager-new", "42", "same-path")
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=429)
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=None, error_type="Timeout")
    assert ledger.summary()["unresolved"] == ["manager-new"]
    ledger.reconcile("42", "same-path", "100")
    summary = ledger.summary()
    assert summary["created"] == 1
    assert summary["creation_requests"] == 2  # noqa: PLR2004
    assert summary["unresolved"] == []


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_definitive_rejections_retire_allocation(
    ledger: AuditLedger, status: int
) -> None:
    ledger.reserve("manager-new", "42", "same-path")
    event_id, name = ledger.before_create("manager-new", "42", "same-path")
    ledger.after_create(event_id, name, status=status)
    with pytest.raises(RepositoryBudgetError, match="non-retryable"):
        ledger.before_create("manager-new", "42", "same-path")


def test_creation_attempts_remain_bounded(ledger: AuditLedger) -> None:
    ledger.reserve("manager-new", "42", "same-path")
    for _ in range(5):
        event_id, name = ledger.before_create("manager-new", "42", "same-path")
        ledger.after_create(event_id, name, status=429)
    with pytest.raises(RepositoryBudgetError, match="five creation attempts"):
        ledger.before_create("manager-new", "42", "same-path")


def test_negative_namespace_allocation_requires_exactly_one_real_rejection(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("invalid-namespace", "-1", "negative", negative=True)
    event_id, name = ledger.before_create("invalid-namespace", "-1", "negative")
    ledger.after_create(event_id, name, status=400)
    with pytest.raises(RepositoryBudgetError, match="one request only"):
        ledger.before_create("invalid-namespace", "-1", "negative")
    assert ledger.summary()["created"] == 0


def test_negative_namespace_unexpected_success_consumes_budget_and_fails(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("invalid-namespace", "-1", "negative", negative=True)
    event_id, name = ledger.before_create("invalid-namespace", "-1", "negative")
    ledger.after_create(event_id, name, status=201, project_id="100")
    summary = ledger.summary()
    assert summary["created"] == 1
    assert summary["violations"] == 1


@pytest.mark.parametrize("namespace", ["0", "1", "42", "missing", "", "-2"])
def test_negative_allocation_cannot_exempt_a_different_namespace(
    ledger: AuditLedger, namespace: str
) -> None:
    with pytest.raises(RepositoryBudgetError, match="requires namespace -1"):
        ledger.reserve("invalid-namespace", namespace, "negative", negative=True)
    assert ledger.summary()["violations"] == 1


def test_negative_request_can_follow_all_nine_successful_allocations(
    ledger: AuditLedger,
) -> None:
    for name in sorted(CREATION_ALLOCATIONS):
        ledger.reserve(name, "42", name)
        event_id, allocation = ledger.before_create(name, "42", name)
        ledger.after_create(event_id, allocation, status=201, project_id=name)
    ledger.reserve("invalid-namespace", "-1", "negative", negative=True)
    event_id, name = ledger.before_create("invalid-namespace", "-1", "negative")
    ledger.after_create(event_id, name, status=400)
    summary = ledger.summary()
    assert summary["created"] == MAX_REPOSITORIES
    assert summary["creation_requests"] == MAX_REPOSITORIES + 1
    assert summary["violations"] == 0


def test_ninth_success_exhausts_budget_even_for_remaining_named_allocation(
    ledger: AuditLedger,
) -> None:
    # An unexpectedly successful negative test consumes one of the nine slots.
    ledger.reserve("invalid-namespace", "-1", "negative", negative=True)
    event_id, name = ledger.before_create("invalid-namespace", "-1", "negative")
    ledger.after_create(event_id, name, status=201, project_id="negative-id")
    names: tuple[str, ...] = (
        "canonical-admin",
        "canonical-write",
        "canonical-read",
        "canonical-view",
        "manager-new",
        "proxy-new",
        "empty-archive",
        "manager-empty",
    )
    for name in names:
        ledger.reserve(name, "42", name)
        event_id, allocation = ledger.before_create(name, "42", name)
        ledger.after_create(event_id, allocation, status=201, project_id=name)
    ledger.reserve("write-check", "42", "last")
    with pytest.raises(RepositoryBudgetError, match="budget is exhausted"):
        ledger.before_create("write-check", "42", "last")
    assert ledger.summary()["created"] == 9  # noqa: PLR2004


def test_diagnostic_mode_blocks_allocated_creation(tmp_path: Path) -> None:
    ledger = AuditLedger(tmp_path / "deny" / "ledger.sqlite3")
    ledger.initialize(deny_create=True)
    ledger.reserve("canonical-admin", "42", "first")
    with pytest.raises(RepositoryBudgetError, match="deny-create"):
        ledger.before_create("canonical-admin", "42", "first")
    assert ledger.summary()["creation_requests"] == 0


def test_exports_are_readable_and_contain_no_request_payload(
    ledger: AuditLedger,
) -> None:
    ledger.reserve("canonical-admin", "42", "first")
    event_id, name = ledger.before_create("canonical-admin", "42", "first")
    ledger.after_create(event_id, name, status=201, project_id="100")
    summary = ledger.export()
    saved = json.loads((ledger.path.parent / "summary.json").read_text())
    assert saved == summary
    events = (ledger.path.parent / "events.jsonl").read_text().splitlines()
    assert all(isinstance(json.loads(line), dict) for line in events)
    assert "1/9 repositories" in (ledger.path.parent / "summary.txt").read_text()
    assert all("headers" not in json.loads(line) for line in events)


@pytest.mark.parametrize(
    "script",
    [
        "import requests; requests.post('http://127.0.0.1:1/api/v4/projects', "
        "json={'namespace_id': '42', 'name': 'unexpected'}, timeout=1)",
        "import gitlab; gitlab.Gitlab('http://127.0.0.1:1', private_token='unused')"
        ".projects.create({'namespace_id': '42', 'name': 'unexpected'})",
    ],
)
def test_test_settings_install_guard_in_real_management_subprocess(
    ledger: AuditLedger,
    script: str,
) -> None:
    environment: dict[str, str] = dict(os.environ)
    environment[LEDGER_ENV] = str(ledger.path)
    environment.pop(ALLOCATION_ENV, None)
    # Port 1 cannot be reached: the assertion requires our guard to fail first.
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "manage.py",
            "shell",
            "--settings=config.settings.test",
            "--command",
            script,
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "RepositoryBudgetError" in result.stderr
    assert "ConnectionError" not in result.stderr
    assert ledger.summary()["violations"] == 1


def test_child_processes_share_atomic_allocation_state(ledger: AuditLedger) -> None:
    ledger.reserve("canonical-admin", "42", "first")
    environment: dict[str, str] = dict(os.environ)
    environment[LEDGER_ENV] = str(ledger.path)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from speleodb.testing.gitlab_audit import get_ledger; "
            "get_ledger().before_create('canonical-admin', '42', 'first')",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.returncode == 0
    with pytest.raises(RepositoryBudgetError, match="Concurrent creation"):
        ledger.before_create("canonical-admin", "42", "first")


@pytest.mark.parametrize("deny_create", [False, True])
def test_nested_pytest_joins_existing_ledger_without_resetting_budget(
    ledger: AuditLedger, tmp_path: Path, deny_create: bool
) -> None:
    ledger.reserve("canonical-admin", "42", "first")
    event_id, name = ledger.before_create("canonical-admin", "42", "first")
    ledger.after_create(event_id, name, status=201, project_id="100")
    configuration: Path = tmp_path / "pytest.ini"
    configuration.write_text("[pytest]\n", encoding="utf-8")
    test_file: Path = tmp_path / "test_nested.py"
    test_file.write_text("def test_placeholder():\n    pass\n", encoding="utf-8")
    environment: dict[str, str] = dict(os.environ)
    environment[LEDGER_ENV] = str(ledger.path)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "speleodb.testing.pytest_gitlab",
            "-c",
            str(configuration),
            "--collect-only",
            *(["--gitlab-audit-deny-create"] if deny_create else []),
            "-q",
            str(test_file),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "GitLab: 1/9 repositories, 1 creation POSTs" in result.stdout
    assert ledger.path.parent.name in result.stdout
    assert ledger.summary()["created"] == 1
    assert not (tmp_path / ".artifacts").exists()
    ledger.reserve("manager-new", "42", "next")
    if deny_create:
        with pytest.raises(RepositoryBudgetError, match="deny-create"):
            ledger.before_create("manager-new", "42", "next")
    else:
        ledger.before_create("manager-new", "42", "next")


def test_joining_cannot_weaken_an_existing_deny_creation_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = AuditLedger(tmp_path / "deny" / "ledger.sqlite3")
    ledger.initialize(deny_create=True)
    monkeypatch.setenv(LEDGER_ENV, str(ledger.path))
    join_run()
    ledger.reserve("canonical-admin", "42", "first")
    with pytest.raises(RepositoryBudgetError, match="deny-create"):
        ledger.before_create("canonical-admin", "42", "first")


def test_streamed_repository_responses_are_not_consumed_by_audit(
    ledger: AuditLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ArchiveHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            content: bytes = b"real streamed archive bytes"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    monkeypatch.setenv(LEDGER_ENV, str(ledger.path))
    with ThreadingHTTPServer(("127.0.0.1", 0), ArchiveHandler) as server:
        thread: Thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with requests.get(
                f"http://127.0.0.1:{server.server_port}/api/v4/projects/1/repository/archive",
                stream=True,
                timeout=5,
            ) as response:
                assert not response._content_consumed  # noqa: SLF001
                assert response.raw.read() == b"real streamed archive bytes"
        finally:
            server.shutdown()
            thread.join(timeout=5)
