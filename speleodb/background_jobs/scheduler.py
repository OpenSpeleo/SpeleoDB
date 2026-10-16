"""Keep the database scheduler while bounding broker retries exponentially."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import override

from django_celery_beat.schedulers import DatabaseScheduler

from config.task_results import HOUSEKEEPING_TASK_NAMES
from speleodb.background_jobs.broker import connect_with_backoff
from speleodb.background_jobs.lease import SchedulerLeaseLostError

if TYPE_CHECKING:
    from celery.beat import ScheduleEntry
    from kombu import Connection
    from kombu import Producer

    from speleodb.background_jobs.lease import SchedulerLease


class ExponentialBackoffDatabaseScheduler(DatabaseScheduler):
    def __init__(self, *args: Any, lease: SchedulerLease, **kwargs: Any) -> None:
        self.lease = lease
        self._closed: bool = False
        self._lazy: bool = bool(kwargs.get("lazy", False))
        # django-celery-beat does not annotate this runtime constructor.
        super().__init__(*args, **kwargs)  # type: ignore[no-untyped-call]

    @override
    def setup_schedule(self) -> None:
        self.lease.assert_owned()
        # Minimal Beat settings disable automatic result-cleanup installation;
        # the predeploy installer owns that managed entry.
        # django-celery-beat does not annotate this runtime hook.
        super().setup_schedule()  # type: ignore[no-untyped-call]

    @override
    def tick(self, *args: Any, **kwargs: Any) -> float:
        self.lease.assert_owned()
        interval: float = super().tick(*args, **kwargs)
        # Celery catches publication Exceptions in apply_entry. Recheck outside
        # that boundary so a failed lease cannot turn into a logged-only error.
        self.lease.assert_owned()
        return interval

    def _check_publish_retry(self, *args: Any, **kwargs: Any) -> None:
        self.lease.assert_owned()

    @override
    def apply_async(
        self,
        entry: ScheduleEntry,
        producer: Producer | None = None,
        advance: bool = True,
        **kwargs: Any,
    ) -> Any:
        self.lease.assert_owned()
        if advance:
            # ModelEntry reconstructs options from the database when reserved.
            # Apply publication policy to that entry, after advancing it once.
            entry = self.reserve(entry)  # type: ignore[no-untyped-call]
        original_options: dict[str, Any] | None = entry.options
        options: dict[str, Any] = original_options or {}
        policy: dict[str, Any] = {
            **self.app.conf.task_publish_retry_policy,
            **options.get("retry_policy", {}),
            "errback": self._check_publish_retry,
            "on_revive": self._check_publish_retry,
        }
        entry.options = {**options, "retry_policy": policy}
        # Minimal Beat sends unknown task names directly. Celery's send_task
        # defaults to ignore_result=False, which overrides worker annotations.
        if entry.task in HOUSEKEEPING_TASK_NAMES:
            entry.options["ignore_result"] = True
        try:
            return super().apply_async(
                entry, producer=producer, advance=False, **kwargs
            )
        finally:
            entry.options = original_options

    @override
    def sync(self) -> None:
        if self._closed or self._lazy or not self.lease.active or self.lease.lost:
            return
        try:
            self.lease.assert_owned()
        except SchedulerLeaseLostError:
            # Finalizers and Celery's shutdown path must not write stale state.
            return
        # django-celery-beat does not annotate its persistence hook.
        super().sync()  # type: ignore[no-untyped-call]

    @override
    def close(self) -> None:
        if self._closed:
            return
        try:
            self.sync()
        finally:
            self._closed = True

    # Celery's runtime hook is absent from the upstream scheduler type stubs.
    def _ensure_connected(self) -> Connection:
        return connect_with_backoff(
            self.connection,
            max_retries=self.app.conf.broker_connection_max_retries,
            base_delay=self.app.conf.broker_retry_base_delay_seconds,
            max_delay=self.app.conf.broker_retry_max_delay_seconds,
            check_shutdown=self.lease.assert_owned,
        )
