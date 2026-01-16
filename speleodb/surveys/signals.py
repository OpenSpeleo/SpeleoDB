# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import Signal
from django.dispatch import receiver

from speleodb.common.caching import UserProjectPermissionCache
from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.models import SurveyTeamMembership

if TYPE_CHECKING:
    from speleodb.users.models import SurveyTeam


git_push_done = Signal()


@receiver(git_push_done)
def notify_admin(sender: Any, **kwargs: Any) -> None:
    print(f"Git Push Executed! {sender=} | Task details: {kwargs=}")  # noqa: T201


@receiver([post_save, post_delete], sender=UserProjectPermission)
def invalidate_user_project_permissions(
    sender: Any, instance: UserProjectPermission, **kwargs: Any
) -> None:
    transaction.on_commit(
        lambda: UserProjectPermissionCache.delete(
            instance.target_id,  # pyright: ignore[reportAttributeAccessIssue]
            instance.project_id,  # pyright: ignore[reportAttributeAccessIssue]
        )
    )


@receiver([post_save, post_delete], sender=TeamProjectPermission)
def invalidate_team_project_permissions(
    sender: Any, instance: TeamProjectPermission, **kwargs: Any
) -> None:
    def invalidate() -> None:
        survey_team: SurveyTeam = instance.target
        for user_id in survey_team.memberships.filter(is_active=True).values_list(
            "user_id", flat=True
        ):
            UserProjectPermissionCache.delete(
                user_id,  # pyright: ignore[reportAttributeAccessIssue]
                instance.project_id,  # pyright: ignore[reportAttributeAccessIssue]
            )

    transaction.on_commit(invalidate)


@receiver([post_save, post_delete], sender=SurveyTeamMembership)
def invalidate_on_membership_change(
    sender: Any, instance: SurveyTeamMembership, **kwargs: Any
) -> None:
    def invalidate() -> None:
        survey_team: SurveyTeam = instance.team
        for project_id in survey_team.project_permissions.values_list(
            "project_id", flat=True
        ):
            UserProjectPermissionCache.delete(
                instance.user_id,  # pyright: ignore[reportAttributeAccessIssue]
                project_id,
            )

    transaction.on_commit(invalidate)
