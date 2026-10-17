"""Result-history policy shared by workers and the isolated Beat publisher.

Keep this module free of Django models and task imports: Beat intentionally has
no application task registry or result backend.
"""

from __future__ import annotations

HOUSEKEEPING_TASK_NAMES: frozenset[str] = frozenset(
    {
        "speleodb.background_jobs.tasks.maintain_background_jobs",
        "speleodb.background_jobs.tasks.delete_expired_artifacts",
        "celery.backend_cleanup",
    }
)
