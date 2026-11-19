from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import TaskResult

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SurveyTeamFactory
from speleodb.api.v2.tests.factories import SurveyTeamMembershipFactory
from speleodb.api.v2.tests.factories import TeamProjectPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.operations import audience
from speleodb.campaigns.operations import review_digest
from speleodb.campaigns.operations import schedule_campaign
from speleodb.campaigns.tasks import send_campaign_email
from speleodb.campaigns.tests import EMAIL_TEMPLATE
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings

    from speleodb.surveys.models import TeamProjectPermission
    from speleodb.surveys.models import UserProjectPermission


@pytest.fixture
def campaign() -> DonationCampaign:
    today = timezone.localdate()
    return DonationCampaign.objects.create(
        email_main_subject="Community appeal",
        email_reminder_subject="Our campaign is closing soon",
        goal_usd=5000,
        donation_url="https://example.com/give",
        start_date=today,
        end_date=today,
        email_main_template=EMAIL_TEMPLATE,
        reminder_email_template=EMAIL_TEMPLATE,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("project_type", ProjectType.values)
@pytest.mark.parametrize("access", ["direct", "team"])
def test_project_filter_counts_access_to_every_project_type(
    campaign: DonationCampaign, project_type: str, access: str
) -> None:
    user = UserFactory.create()
    project = ProjectFactory.create(type=project_type, created_by=user.email)
    if access == "direct":
        UserProjectPermissionFactory.create(
            project=project, target=user, level=PermissionLevel.WEB_VIEWER
        )
    else:
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(user=user, team=team)
        TeamProjectPermissionFactory.create(
            project=project, target=team, level=PermissionLevel.WEB_VIEWER
        )
    assert audience(campaign, project_users_only=True) == [
        {"user_id": str(user.pk), "email": user.email}
    ]


@pytest.mark.django_db
def test_filter_excludes_zero_projects_and_inactive_access_paths(
    campaign: DonationCampaign,
) -> None:
    no_project = UserFactory.create()
    revoked_direct = UserFactory.create()
    revoked_team = UserFactory.create()
    former_member = UserFactory.create()
    inactive_project = UserFactory.create()
    project = ProjectFactory.create(created_by=no_project.email)
    deleted_project = ProjectFactory.create(
        created_by=no_project.email, is_active=False
    )
    UserProjectPermissionFactory.create(
        project=project, target=revoked_direct, is_active=False
    )
    UserProjectPermissionFactory.create(
        project=deleted_project, target=inactive_project
    )
    for user, grant_active, membership_active in (
        (revoked_team, False, True),
        (former_member, True, False),
    ):
        team = SurveyTeamFactory.create()
        SurveyTeamMembershipFactory.create(
            user=user, team=team, is_active=membership_active
        )
        TeamProjectPermissionFactory.create(
            project=project, target=team, is_active=grant_active
        )
    assert audience(campaign, project_users_only=True) == []
    assert {row["user_id"] for row in audience(campaign)} == {
        str(user.pk)
        for user in (
            no_project,
            revoked_direct,
            revoked_team,
            former_member,
            inactive_project,
        )
    }


@pytest.mark.django_db
def test_filter_preserves_opt_outs_inactive_accounts_and_email_deduplication(
    campaign: DonationCampaign,
) -> None:
    no_access = UserFactory.create(email="shared@example.com")
    eligible = UserFactory.create(email="SHARED@example.com", is_active=False)
    opted_out = UserFactory.create(email_on_speleodb_updates=False)
    empty_email = UserFactory.create(email="")
    project = ProjectFactory.create(created_by=eligible.email)
    for user in (eligible, opted_out, empty_email):
        UserProjectPermissionFactory.create(project=project, target=user)
    team = SurveyTeamFactory.create()
    SurveyTeamMembershipFactory.create(user=eligible, team=team)
    TeamProjectPermissionFactory.create(project=project, target=team)
    assert audience(campaign, project_users_only=True) == [
        {"user_id": str(eligible.pk), "email": eligible.email}
    ]
    assert audience(campaign) == [
        {"user_id": str(no_access.pk), "email": no_access.email}
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_real_send_review_and_delivery_use_project_filter(
    campaign: DonationCampaign,
    reminder: bool,
    mailoutbox: Any,
    django_capture_on_commit_callbacks: Any,
    settings: Settings,
) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    operator = UserFactory.create(
        is_superuser=True, is_staff=True, email_on_speleodb_updates=False
    )
    eligible = UserFactory.create()
    zero_projects = UserFactory.create()
    project = ProjectFactory.create(created_by=eligible.email)
    UserProjectPermissionFactory.create(target=eligible, project=project)
    client = Client()
    client.force_login(operator)
    route = "admin:campaign_send_reminder" if reminder else "admin:campaign_send"
    url = reverse(route, args=[campaign.pk])
    assert b'name="project_users_only"' in client.get(url).content
    review = client.post(url, {"action": "review", "project_users_only": "on"})
    assert review.context_data is not None
    assert review.context_data["recipient_count"] == 1
    confirmation = review.context_data["confirmation"]
    assert confirmation
    assert b'value="1"' in review.content
    assert not TaskResult.objects.exists()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            url,
            {"action": "send", "project_users_only": "1", "confirmation": confirmation},
        )
    assert response.status_code == HTTPStatus.FOUND
    assert [message.to for message in mailoutbox] == [[eligible.email]]
    assert not any(zero_projects.email in message.to for message in mailoutbox)
    campaign.refresh_from_db()
    assert DonationCampaignEmail.objects.get().recipients == [eligible.email]
    task = TaskResult.objects.get()
    assert json.loads(task.task_args)[0]["project_users_only"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_audience_flag_is_bound_to_review_even_if_audience_is_identical(
    campaign: DonationCampaign,
    reminder: bool,
    admin_client: Client,
) -> None:
    operator = UserFactory.create(is_superuser=True, is_staff=True)
    admin_client.force_login(operator)
    project = ProjectFactory.create(created_by=operator.email)
    UserProjectPermissionFactory.create(project=project, target=operator)
    route = "admin:campaign_send_reminder" if reminder else "admin:campaign_send"
    url = reverse(route, args=[campaign.pk])
    review = admin_client.post(url, {"action": "review", "project_users_only": "on"})
    assert review.context_data is not None
    response = admin_client.post(
        url, {"action": "send", "confirmation": review.context_data["confirmation"]}
    )
    assert b"Review again" in response.content
    assert not TaskResult.objects.exists()
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_project_access_revoked_after_review_requires_new_review(
    campaign: DonationCampaign, reminder: bool
) -> None:
    operator = UserFactory.create(is_superuser=True)
    project = ProjectFactory.create(created_by=operator.email)
    permission = UserProjectPermissionFactory.create(project=project, target=operator)
    digest = review_digest(campaign, reminder=reminder, project_users_only=True)
    permission.is_active = False
    permission.save()
    with pytest.raises(ValueError, match="changed"):
        schedule_campaign(
            str(campaign.pk),
            send_id=str(uuid4()),
            requester=operator,
            site_url="https://example.com/",
            digest=digest,
            reminder=reminder,
            project_users_only=True,
        )
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
@pytest.mark.parametrize("access", ["direct", "team"])
@pytest.mark.parametrize("retains_access", [False, True])
def test_worker_requires_at_least_one_remaining_project(
    campaign: DonationCampaign,
    reminder: bool,
    access: str,
    retains_access: bool,
    mailoutbox: Any,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    project = ProjectFactory.create(created_by=operator.email)
    permission: UserProjectPermission | TeamProjectPermission
    if retains_access:
        other_project = ProjectFactory.create(created_by=operator.email)
        UserProjectPermissionFactory.create(project=other_project, target=operator)
    if access == "direct":
        permission = UserProjectPermissionFactory.create(
            project=project, target=operator
        )
    else:
        team = SurveyTeamFactory.create()
        permission = TeamProjectPermissionFactory.create(project=project, target=team)
        SurveyTeamMembershipFactory.create(user=operator, team=team)
    receipt = schedule_campaign(
        str(campaign.pk),
        send_id=str(uuid4()),
        requester=operator,
        site_url="https://example.com/",
        reminder=reminder,
        project_users_only=True,
        digest=review_digest(campaign, reminder=reminder, project_users_only=True),
    )
    permission.is_active = False
    permission.save()
    row = TaskResult.objects.get(task_id=receipt.task_ids[0])
    summary = send_campaign_email.apply(
        args=json.loads(row.task_args), task_id=row.task_id, throw=True
    ).get()
    if retains_access:
        assert summary["outcome"] == "backend-accepted"
        assert [message.to for message in mailoutbox] == [[operator.email]]
    else:
        assert summary["outcome"] == "skipped"
        assert not mailoutbox


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_explicit_test_addresses_are_not_filtered_by_project_access(
    campaign: DonationCampaign, reminder: bool
) -> None:
    operator = UserFactory.create(is_superuser=True)
    receipt = schedule_campaign(
        str(campaign.pk),
        requester=operator,
        site_url="https://example.com/",
        reminder=reminder,
        project_users_only=True,
        test_emails=["zero-projects@example.com"],
    )
    task = TaskResult.objects.get(task_id=receipt.task_ids[0])
    args = json.loads(task.task_args)
    assert args[1] == "zero-projects@example.com"
    assert args[3] is None
    assert args[0]["project_users_only"] is False
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reminder", [False, True])
def test_empty_project_audience_keeps_campaign_unsent(
    campaign: DonationCampaign,
    reminder: bool,
) -> None:
    operator = UserFactory.create(is_superuser=True)
    digest = review_digest(campaign, reminder=reminder, project_users_only=True)
    with pytest.raises(ValueError, match="No eligible recipients"):
        schedule_campaign(
            str(campaign.pk),
            send_id=str(uuid4()),
            requester=operator,
            site_url="https://example.com/",
            reminder=reminder,
            project_users_only=True,
            digest=digest,
        )
    campaign.refresh_from_db()
    assert not DonationCampaignEmail.objects.exists()
    assert not TaskResult.objects.exists()
