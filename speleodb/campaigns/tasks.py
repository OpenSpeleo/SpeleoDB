"""Campaign delivery uses the existing single-execution task result guard."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from celery.exceptions import Ignore

from speleodb.background_jobs.operation_execution import operation_execution
from speleodb.campaigns.mail import send_message
from speleodb.users.models import User


@shared_task(
    bind=True,
    # The execution guard owns STARTED; Celery must not write it before the claim.
    track_started=False,
    name="speleodb.campaigns.tasks.send_campaign_email",
    soft_time_limit=90,
    time_limit=120,
)
def send_campaign_email(
    self: Any,
    snapshot: dict[str, Any],
    email: str,
    site_url: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    with operation_execution(self.request.id) as execution:
        if execution is None:
            # Returning would let Celery overwrite the original result with SUCCESS.
            raise Ignore
        if (
            user_id
            and not User.objects.filter(
                pk=user_id, email=email, email_on_speleodb_updates=True
            ).exists()
        ):
            summary = {
                "outcome": "skipped",
                "reason": "Account, address or preference changed.",
            }
        else:
            execution.progress("sending")
            summary = send_message(
                snapshot, email=email, site_url=site_url, user_id=user_id
            )
        execution.complete(summary)
        return summary
