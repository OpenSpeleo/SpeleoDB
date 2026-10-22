"""Safety boundary for subprocess tests using the dedicated Redis broker."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings

TEST_BROKER_PORT: int = 6381
REDIS_PORT: int = 6379


def isolated_test_broker_url() -> str:
    broker_url: str = settings.TEST_CELERY_BROKER_URL
    broker = urlsplit(broker_url)
    allowed: bool = (
        broker.hostname in {"localhost", "127.0.0.1", "redis"}
        and broker.port == TEST_BROKER_PORT
    ) or (broker.hostname == "celery-test-redis" and broker.port == REDIS_PORT)
    assert broker.scheme == "redis"
    assert allowed, (
        "Use the dedicated celery-test-redis service; development brokers are refused."
    )
    return broker_url
