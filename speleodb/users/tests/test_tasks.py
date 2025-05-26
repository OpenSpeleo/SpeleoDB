import pytest
from celery.result import EagerResult
from pytest_django.fixtures import SettingsWrapper

from speleodb.users.tasks import get_users_count
from speleodb.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_user_count(settings: SettingsWrapper) -> None:
    """A basic test to execute the get_users_count Celery task."""
    batch_size = 3
    UserFactory.create_batch(batch_size)
    settings.CELERY_TASK_ALWAYS_EAGER = True
    task_result = get_users_count.delay()  # pyright: ignore[reportCallIssue]
    assert isinstance(task_result, EagerResult)
    assert task_result.result == batch_size
