# -*- coding: utf-8 -*-

from __future__ import annotations

from celery import shared_task

from speleodb.users.models import User


@shared_task()
def get_users_count() -> int:
    """A pointless Celery task to demonstrate usage."""
    return User.objects.count()
