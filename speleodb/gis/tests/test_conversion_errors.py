"""Preserve actionable conversion failures through Celery serialization."""

from __future__ import annotations

from celery import Celery
from celery.backends.base import Backend
from celery.utils.serialization import get_pickleable_exception

from speleodb.surveys.models.project import ConversionFailedError
from speleodb.surveys.models.project import ConversionSummary


def test_aggregate_failure_survives_celery_exception_serialization() -> None:
    summary = ConversionSummary(processed=3, generated=1, failed=2)
    failure = ConversionFailedError(summary)
    # Celery performs the actual serialization round-trip and returns the
    # original exception only when reconstruction succeeds with its concrete type.
    assert get_pickleable_exception(failure) is failure
    assert failure.summary.as_dict() == summary.as_dict()
    assert str(failure) == "Map conversion failed for 2 revision(s)."
    with Celery("conversion-serialization", set_as_current=False) as app:
        backend = Backend(app=app)
        restored = backend.exception_to_python(
            backend.prepare_exception(failure, serializer="json")
        )
    assert isinstance(restored, ConversionFailedError)
    assert restored.summary.as_dict() == summary.as_dict()
    assert str(restored) == str(failure)
