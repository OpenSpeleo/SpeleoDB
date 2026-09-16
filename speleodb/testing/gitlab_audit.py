"""Process-safe, test-only accounting at the real GitLab HTTP boundary.

Allocations authorize one immutable namespace/path, never a replacement remote.
The SQLite ledger survives transaction rollbacks, caught errors, and subprocesses.
No request headers, bodies, response bodies, or credential-bearing URLs are saved.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import traceback
from contextlib import closing
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlsplit
from uuid import uuid4

import requests

if TYPE_CHECKING:
    from collections.abc import Generator

LEDGER_ENV: str = "SPELEODB_GITLAB_AUDIT_LEDGER"
ALLOCATION_ENV: str = "SPELEODB_GITLAB_ALLOCATION"
NODE_ENV: str = "SPELEODB_GITLAB_TEST_NODE"
PHASE_ENV: str = "SPELEODB_GITLAB_TEST_PHASE"
MAX_REPOSITORIES: int = 9
MAX_CREATION_ATTEMPTS: int = 5
VERIFIED_CLEANUP_OUTCOMES: frozenset[str] = frozenset(
    {"absent", "marked-for-deletion", "verified-absent", "verified-marked-for-deletion"}
)
CREATION_ALLOCATIONS: frozenset[str] = frozenset(
    {
        "canonical-admin",
        "canonical-write",
        "canonical-read",
        "canonical-view",
        "manager-new",
        "proxy-new",
        "empty-archive",
        "manager-empty",
        "write-check",
    }
)
_original_send = requests.Session.send
_installed: bool = False


def _application_stack() -> list[str]:
    return [
        f"{frame.filename}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_stack()[:-1]
        if "site-packages" not in frame.filename
    ]


def _unsupported_creation_route(path: str) -> bool:
    """Other GitLab creation APIs cannot borrow a normal project allocation.

    These APIs may create multiple projects asynchronously. None belongs to
    our test feature contract: block them before they can escape accounting.
    """
    route: str = unquote(path).partition("/api/v4/")[2]
    return (
        route
        in {
            "bulk_imports",
            "offline_imports",
            "groups/import",
            "projects/import",
            "projects/remote-import",
            "projects/remote-import-s3",
        }
        or route.startswith(("import/", "projects/user/"))
        or bool(re.fullmatch(r"projects/.+/fork", route))
    )


class RepositoryBudgetError(RuntimeError):
    """An unallocated creation must fail even if its caller catches this error."""


class AuditLedger:
    """Small durable ledger, serialized with SQLite's process-safe write lock."""

    def __init__(self, path: Path) -> None:
        self.path: Path = path

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=30)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def initialize(self, *, deny_create: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS configuration "
                "(run_id TEXT NOT NULL, deny_create INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO configuration VALUES (?, ?)",
                (self.path.parent.name, int(deny_create)),
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS allocations ("
                "name TEXT PRIMARY KEY, namespace TEXT NOT NULL, path TEXT NOT NULL, "
                "negative INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, "
                "project_id TEXT, inflight INTEGER NOT NULL DEFAULT 0, "
                "uncertain INTEGER NOT NULL DEFAULT 0, "
                "terminal INTEGER NOT NULL DEFAULT 0, "
                "UNIQUE(namespace, path))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events "
                "(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def event(self, connection: sqlite3.Connection, **fields: Any) -> int:
        payload: dict[str, Any] = {
            "run_id": self.path.parent.name,
            "nodeid": os.environ.get(NODE_ENV, "session"),
            "phase": os.environ.get(PHASE_ENV, "session"),
            "pid": os.getpid(),
            **fields,
        }
        cursor: sqlite3.Cursor = connection.execute(
            "INSERT INTO events (payload) VALUES (?)", (json.dumps(payload),)
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def reserve(
        self, name: str, namespace: str, path: str, *, negative: bool = False
    ) -> None:
        reason: str | None = None
        with self.transaction() as connection:
            row: sqlite3.Row | None = connection.execute(
                "SELECT * FROM allocations WHERE name = ?", (name,)
            ).fetchone()
            if (negative and name != "invalid-namespace") or (
                not negative and name not in CREATION_ALLOCATIONS
            ):
                reason = f"Unknown GitLab creation allocation: {name}"
            elif negative and namespace != "-1":
                reason = "The negative allocation requires namespace -1"
            elif row is not None:
                if (row["namespace"], row["path"], bool(row["negative"])) != (
                    namespace,
                    path,
                    negative,
                ):
                    reason = f"Allocation {name} cannot change namespace or path"
            elif connection.execute(
                "SELECT name FROM allocations WHERE namespace = ? AND path = ?",
                (namespace, path),
            ).fetchone():
                reason = "A GitLab identity cannot belong to two allocations"
            else:
                connection.execute(
                    "INSERT INTO allocations (name, namespace, path, negative) "
                    "VALUES (?, ?, ?, ?)",
                    (name, namespace, path, int(negative)),
                )
                self.event(
                    connection,
                    event="allocation",
                    allocation=name,
                    namespace=namespace,
                    path=path,
                    negative=negative,
                )
            if reason is not None:
                self.event(connection, event="violation", reason=reason)
        if reason is not None:
            raise RepositoryBudgetError(reason)

    def before_create(
        self, name: str | None, namespace: str, path: str
    ) -> tuple[int, str]:
        reason: str | None = None
        event_id: int = 0
        with self.transaction() as connection:
            row: sqlite3.Row | None = connection.execute(
                "SELECT * FROM allocations WHERE name = ?", (name,)
            ).fetchone()
            configuration: sqlite3.Row = connection.execute(
                "SELECT * FROM configuration"
            ).fetchone()
            if configuration["deny_create"]:
                reason = "GitLab creation disabled by --gitlab-audit-deny-create"
            elif row is None or (row["namespace"], row["path"]) != (namespace, path):
                reason = "GitLab creation has no matching explicit allocation"
            elif row["project_id"] is not None:
                reason = "An allocation cannot create another repository after success"
            elif row["inflight"]:
                reason = "Concurrent creation of the same allocation is forbidden"
            elif row["negative"] and row["attempts"]:
                reason = "The invalid-namespace allocation permits one request only"
            elif row["terminal"]:
                reason = "The allocation received a definitive non-retryable rejection"
            elif row["attempts"] >= MAX_CREATION_ATTEMPTS:
                reason = "The allocation exhausted its five creation attempts"
            elif not row["negative"] and (
                connection.execute(
                    "SELECT COUNT(*) FROM allocations WHERE name != ? AND "
                    "(project_id IS NOT NULL OR inflight = 1 OR uncertain = 1)",
                    (name,),
                ).fetchone()[0]
                >= MAX_REPOSITORIES
            ):
                reason = "The cumulative nine-repository GitLab budget is exhausted"
            event_id = self.event(
                connection,
                event="violation" if reason else "creation_attempt",
                allocation=name,
                namespace=namespace,
                path=path,
                attempt=0 if row is None else row["attempts"] + 1,
                stack=_application_stack(),
                reason=reason,
            )
            if reason is None:
                connection.execute(
                    "UPDATE allocations SET attempts = attempts + 1, inflight = 1 "
                    "WHERE name = ?",
                    (name,),
                )
        if reason is not None:
            raise RepositoryBudgetError(
                f"{reason}: namespace={namespace} path={path}; "
                f"test={os.environ.get(NODE_ENV, 'session')}; audit={self.path}"
            )
        assert name is not None
        return event_id, name

    def reject_unsupported_creation(self, path: str) -> None:
        reason: str = (
            "GitLab fork/import/admin creation is outside the test allocations"
        )
        with self.transaction() as connection:
            self.event(
                connection,
                event="violation",
                reason=reason,
                route=path,
                stack=_application_stack(),
            )
        raise RepositoryBudgetError(f"{reason}; audit={self.path}")

    def after_create(
        self,
        event_id: int,
        name: str,
        *,
        status: int | None,
        project_id: str | None = None,
        error_type: str | None = None,
    ) -> None:
        success: bool = (
            status is not None and HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES
        )
        uncertain: bool = (
            status is None
            or status >= HTTPStatus.INTERNAL_SERVER_ERROR
            or (success and project_id is None)
        )
        terminal: bool = (
            status is not None
            and not success
            and not uncertain
            and status
            not in {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.CONFLICT,
            }
        )
        created_id: str | None = project_id if success else None
        with self.transaction() as connection:
            row: sqlite3.Row = connection.execute(
                "SELECT * FROM allocations WHERE name = ?", (name,)
            ).fetchone()
            connection.execute(
                "UPDATE allocations SET inflight = 0, "
                "project_id = COALESCE(?, project_id), "
                "uncertain = CASE WHEN ? IS NOT NULL THEN 0 "
                "ELSE MAX(uncertain, ?) END, terminal = ? WHERE name = ?",
                (
                    created_id,
                    created_id,
                    int(uncertain),
                    int(terminal),
                    name,
                ),
            )
            self.event(
                connection,
                event="creation_result",
                attempt_event=event_id,
                allocation=name,
                status=status,
                project_id=project_id,
                error_type=error_type,
                outcome="created"
                if success
                else "uncertain"
                if uncertain
                else "rejected",
            )
            if row["negative"] and status != HTTPStatus.BAD_REQUEST:
                self.event(
                    connection,
                    event="violation",
                    reason="The invalid-namespace request must return HTTP 400",
                )

    def reconcile(self, namespace: str, path: str, project_id: str) -> None:
        with self.transaction() as connection:
            row: sqlite3.Row | None = connection.execute(
                "SELECT name FROM allocations WHERE namespace = ? AND path = ? "
                "AND uncertain = 1",
                (namespace, path),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE allocations SET project_id = ?, uncertain = 0, "
                    "inflight = 0 WHERE name = ?",
                    (project_id, row["name"]),
                )
                self.event(
                    connection,
                    event="reconciled",
                    allocation=row["name"],
                    project_id=project_id,
                )

    def summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            allocations: list[dict[str, Any]] = [
                dict(row)
                for row in connection.execute("SELECT * FROM allocations ORDER BY name")
            ]
            events: list[dict[str, Any]] = [
                {"id": row["id"], **json.loads(row["payload"])}
                for row in connection.execute("SELECT * FROM events ORDER BY id")
            ]
        verified_cleanup: dict[str, str] = {
            str(event["project_id"]): str(event["outcome"])
            for event in events
            if event["event"] == "cleanup"
            and event["outcome"] in VERIFIED_CLEANUP_OUTCOMES
        }
        for allocation in allocations:
            allocation["cleanup_outcome"] = verified_cleanup.get(
                allocation["project_id"]
            )
        return {
            "run_id": self.path.parent.name,
            "budget": MAX_REPOSITORIES,
            "created": sum(row["project_id"] is not None for row in allocations),
            "creation_requests": sum(row["attempts"] for row in allocations),
            "violations": sum(event["event"] == "violation" for event in events),
            "unresolved": [
                row["name"]
                for row in allocations
                if row["uncertain"] or row["inflight"]
            ],
            "allocations": allocations,
            "events": events,
        }

    def export(self) -> dict[str, Any]:
        summary: dict[str, Any] = self.summary()
        events: list[dict[str, Any]] = summary.pop("events")
        (self.path.parent / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        (self.path.parent / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        (self.path.parent / "summary.txt").write_text(
            f"GitLab run {summary['run_id']}: {summary['created']}/{MAX_REPOSITORIES} "
            f"repositories; {summary['creation_requests']} POSTs; "
            f"{summary['violations']} violations; unresolved={summary['unresolved']}\n"
            + "".join(
                f"{row['name']}: {row['namespace']}/{row['path']} "
                f"id={row['project_id']} attempts={row['attempts']} "
                f"cleanup={row['cleanup_outcome'] or 'not-verified'}\n"
                for row in summary["allocations"]
            ),
            encoding="utf-8",
        )
        return summary


def get_ledger() -> AuditLedger:
    path: str | None = os.environ.get(LEDGER_ENV)
    if path is None:
        raise RepositoryBudgetError("GitLab test audit was not initialized by pytest")
    return AuditLedger(Path(path))


def start_run(
    directory: Path | None = None, *, deny_create: bool = False
) -> AuditLedger:
    directory = directory or Path(".artifacts/gitlab") / uuid4().hex
    ledger: AuditLedger = AuditLedger(directory.resolve() / "ledger.sqlite3")
    ledger.initialize(deny_create=deny_create)
    os.environ[LEDGER_ENV] = str(ledger.path)
    os.environ.pop(ALLOCATION_ENV, None)
    install_guard()
    return ledger


def join_run(*, deny_create: bool = False) -> AuditLedger:
    """Nested pytest processes inherit the existing cumulative budget."""
    ledger: AuditLedger = get_ledger()
    with ledger.transaction() as connection:
        configuration: sqlite3.Row | None = connection.execute(
            "SELECT * FROM configuration"
        ).fetchone()
        if configuration is None:
            raise RepositoryBudgetError("The inherited GitLab audit is not initialized")
        if deny_create:
            connection.execute("UPDATE configuration SET deny_create = 1")
    install_guard()
    return ledger


@contextmanager
def creation_allocation(
    name: str, namespace_id: str | int, path: str, *, negative: bool = False
) -> Generator[None]:
    get_ledger().reserve(name, str(namespace_id), path, negative=negative)
    previous: str | None = os.environ.get(ALLOCATION_ENV)
    os.environ[ALLOCATION_ENV] = name
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(ALLOCATION_ENV, None)
        else:
            os.environ[ALLOCATION_ENV] = previous


def record_cleanup(project_id: str | int, outcome: str) -> None:
    ledger: AuditLedger = get_ledger()
    with ledger.transaction() as connection:
        ledger.event(
            connection,
            event="cleanup",
            project_id=str(project_id),
            outcome=outcome,
        )


def _creation_identity(request: requests.PreparedRequest) -> tuple[str, str]:
    body: str | bytes | None = request.body  # type: ignore[assignment]
    data: dict[str, Any] = {}
    if isinstance(body, (str, bytes)):
        if "application/json" in request.headers.get("Content-Type", ""):
            try:
                decoded: Any = json.loads(body)
            except ValueError:
                decoded = None
            if isinstance(decoded, dict):
                data = decoded
        else:
            text: str = body.decode() if isinstance(body, bytes) else body
            data = {key: values[0] for key, values in parse_qs(text).items()}
    return str(data.get("namespace_id", "")), str(
        data.get("path") or data.get("name", "")
    )


def _response_project(response: requests.Response) -> dict[str, Any]:
    try:
        data: Any = response.json()
    except ValueError, requests.exceptions.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _response_project_id(data: dict[str, Any]) -> str | None:
    value: Any = data.get("id")
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        text: str = str(value)
        if text.isdecimal() and int(text) > 0:
            return text
    return None


def _audited_send(
    self: requests.Session, request: requests.PreparedRequest, **kwargs: Any
) -> requests.Response:
    if LEDGER_ENV not in os.environ:
        return _original_send(self, request, **kwargs)
    path: str = urlsplit(request.url or "").path.rstrip("/")
    ledger: AuditLedger = get_ledger()
    if request.method == "POST" and _unsupported_creation_route(path):
        ledger.reject_unsupported_creation(path)
    if request.method == "POST" and unquote(path).endswith("/api/v4/projects"):
        namespace, project_path = _creation_identity(request)
        event_id, name = ledger.before_create(
            os.environ.get(ALLOCATION_ENV), namespace, project_path
        )
        try:
            response: requests.Response = _original_send(self, request, **kwargs)
        except BaseException as error:
            ledger.after_create(
                event_id, name, status=None, error_type=type(error).__name__
            )
            raise
        data: dict[str, Any] = _response_project(response)
        ledger.after_create(
            event_id,
            name,
            status=response.status_code,
            project_id=_response_project_id(data),
        )
        return response
    response = _original_send(self, request, **kwargs)
    project_identifier: str = path.partition("/api/v4/projects/")[2]
    if project_identifier and "/" not in project_identifier:
        if request.method == "DELETE":
            record_cleanup(unquote(project_identifier), f"HTTP {response.status_code}")
        elif request.method == "GET" and response.status_code == HTTPStatus.OK:
            data = _response_project(response)
            namespace_data: Any = data.get("namespace")
            project_id: str | None = _response_project_id(data)
            if isinstance(namespace_data, dict) and project_id and "path" in data:
                ledger.reconcile(
                    str(namespace_data.get("id", "")),
                    str(data["path"]),
                    project_id,
                )
    return response


def install_guard() -> None:
    """Also called by test settings in inherited management/Celery processes."""
    global _installed  # noqa: PLW0603
    if not _installed:
        requests.Session.send = _audited_send
        _installed = True


def finish_run() -> dict[str, Any]:
    return get_ledger().export()
