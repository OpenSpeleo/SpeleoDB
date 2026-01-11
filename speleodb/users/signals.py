# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import Signal
from django.dispatch import receiver

from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models.team import membership_cache_key

git_push_done = Signal()


@receiver([post_save, post_delete], sender=SurveyTeamMembership)
def invalidate_survey_team_membership_cache(
    sender,
    instance: SurveyTeamMembership,
    **kwargs: Any,
):
    """
    Invalidate cached active membership for a given team/user pair.
    Runs on commit to avoid cache inconsistency on rollbacks.
    """
    print("CACHE CLEARED: START !!!!!!!!!!!!!")
    team_id = instance.team.id
    user_id = instance.user.id

    transaction.on_commit(
        lambda: cache.delete(membership_cache_key(team_id=team_id, user_id=user_id))
    )
    print("CACHE CLEARED: END !!!!!!!!!!!!!")
