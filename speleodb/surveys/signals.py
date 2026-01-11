# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import Signal
from django.dispatch import receiver

from speleodb.surveys.models import ProjectMutex

git_push_done = Signal()


@receiver(git_push_done)
def notify_admin(sender: Any, **kwargs: Any) -> None:
    print(f"Git Push Executed! {sender=} | Task details: {kwargs=}")  # noqa: T201


@receiver([post_save, post_delete], sender=ProjectMutex)
def invalidate_project_mutex_cache(sender, instance: ProjectMutex, **kwargs: Any):
    print("CACHE CLEARED: START !!!!!!!!!!!!!")
    cache.delete(f"project:{instance.project.id}:active_mutex_id")
    print("CACHE CLEARED: END !!!!!!!!!!!!!")
