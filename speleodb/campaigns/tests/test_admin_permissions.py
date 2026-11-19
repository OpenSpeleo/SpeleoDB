"""Campaign administration stays private even when staff receive model grants."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from django_celery_results.models import GroupResult
from django_celery_results.models import TaskResult

from speleodb.campaigns.letter_operations import issue_letter
from speleodb.campaigns.letter_operations import resend_letter
from speleodb.campaigns.letter_operations import schedule_letter_preview
from speleodb.campaigns.letter_rendering import example_letter
from speleodb.campaigns.models import DonationCampaign
from speleodb.campaigns.models import DonationCampaignDismissal
from speleodb.campaigns.models import DonationCampaignEmail
from speleodb.campaigns.models import DonationThankYouTemplate
from speleodb.campaigns.operations import schedule_campaign
from speleodb.campaigns.tests import EMAIL_TEMPLATE
from speleodb.common.enums import TaskResultStatus
from speleodb.users.models import LogEntry
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.db.models import Model
    from django.test import Client


@pytest.fixture
def campaign_records() -> dict[str, Model]:
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_subject="Private fundraiser appeal",
        email_main_template=EMAIL_TEMPLATE,
        email_reminder_subject="Private fundraiser reminder",
        reminder_email_template=EMAIL_TEMPLATE,
        goal_usd=5000,
        donation_url="https://example.org/give",
        start_date=today,
        end_date=today,
    )
    template = DonationThankYouTemplate.objects.create(
        name="Private gift template", email_subject="Your gift receipt"
    )
    letter = example_letter(template)
    letter.save()
    return {
        "donationcampaign": campaign,
        "donationcampaigndismissal": DonationCampaignDismissal.objects.create(
            campaign=campaign, user=UserFactory.create()
        ),
        "donationcampaignemail": DonationCampaignEmail.objects.create(
            campaign=campaign,
            email_type=DonationCampaignEmail.EmailType.MAIN,
            subject=campaign.email_main_subject,
            template=EMAIL_TEMPLATE,
            recipients=["private-donor@example.org"],
        ),
        "donationthankyoutemplate": template,
        "donationthankyouletters": letter,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("grant", ["none", "direct", "group"])
def test_staff_cannot_discover_or_access_any_campaign_admin(
    client: Client, campaign_records: dict[str, Model], grant: str
) -> None:
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    permissions = Permission.objects.filter(content_type__app_label="campaigns")
    if grant == "direct":
        staff.user_permissions.add(*permissions)
    elif grant == "group":
        group = Group.objects.create(name="Campaign model grants")
        group.permissions.add(*permissions)
        staff.groups.add(group)
    client.force_login(staff)
    index = client.get(reverse("admin:index"))
    assert all(
        app["app_label"] != "campaigns" for app in index.context["available_apps"]
    )
    assert (
        client.get(reverse("admin:app_list", args=["campaigns"])).status_code
        == HTTPStatus.NOT_FOUND
    )
    for name, obj in campaign_records.items():
        prefix = f"admin:campaigns_{name}"
        for action in ("changelist", "add", "change", "history", "delete"):
            args = [obj.pk] if action in {"change", "history", "delete"} else []
            url = reverse(f"{prefix}_{action}", args=args)
            assert client.get(url).status_code == HTTPStatus.FORBIDDEN, (
                name,
                action,
                grant,
            )
            if action != "history":
                assert (
                    client.post(
                        url,
                        {
                            "post": "yes",
                            "action": "delete_selected",
                            "_selected_action": [obj.pk],
                        },
                    ).status_code
                    == HTTPStatus.FORBIDDEN
                )
        obj.refresh_from_db()
    assert not TaskResult.objects.exists()
    assert not LogEntry.objects.exists()


@pytest.mark.django_db
def test_staff_model_grants_cannot_reach_send_preview_pdf_or_transfer_routes(
    client: Client, campaign_records: dict[str, Model]
) -> None:
    staff = UserFactory.create(is_staff=True, is_superuser=False)
    staff.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="campaigns")
    )
    client.force_login(staff)
    campaign = campaign_records["donationcampaign"]
    letter = campaign_records["donationthankyouletters"]
    for route in (
        "campaign_send",
        "campaign_send_reminder",
        "letter_pdf",
        "letter_issue",
        "letter_regenerate",
        "letter_resend",
    ):
        obj = campaign if route.startswith("campaign_") else letter
        url = reverse(f"admin:{route}", args=[obj.pk])
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN
        for action in (
            ("test", "review", "send") if route.startswith("campaign_") else ("send",)
        ):
            assert (
                client.post(url, {"action": action, "emails": staff.email}).status_code
                == HTTPStatus.FORBIDDEN
            )
    for name in (
        "donationcampaign",
        "donationthankyoutemplate",
        "donationthankyouletters",
    ):
        url = reverse(
            f"admin:campaigns_{name}_change", args=[campaign_records[name].pk]
        )
        assert (
            client.post(
                url, {"_save_preview": "template", "_preview_pdf": "1"}
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
    for action in ("import", "export", "process_import"):
        url = reverse(f"admin:campaigns_donationcampaign_{action}")
        if action != "process_import":
            assert client.get(url).status_code == HTTPStatus.FORBIDDEN
        assert client.post(url).status_code == HTTPStatus.FORBIDDEN
    for name, field in (
        ("donationthankyouletters", "template"),
        ("donationcampaignemail", "campaign"),
    ):
        response = client.get(
            reverse("admin:autocomplete"),
            {"app_label": "campaigns", "model_name": name, "field_name": field},
        )
        # These related admins do not expose autocomplete search.
        assert response.status_code == HTTPStatus.NOT_FOUND
    popup = reverse("admin:campaigns_donationcampaign_changelist")
    assert (
        client.get(popup, {"_popup": "1", "_to_field": "id"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert not TaskResult.objects.exists()
    assert not LogEntry.objects.exists()


@pytest.mark.django_db
def test_superusers_retain_campaign_navigation_and_read_access(
    admin_client: Client, campaign_records: dict[str, Model]
) -> None:
    index = admin_client.get(reverse("admin:index"))
    app = next(
        app
        for app in index.context["available_apps"]
        if app["app_label"] == "campaigns"
    )
    assert len(app["models"]) == len(campaign_records)
    for name, obj in campaign_records.items():
        for action in ("changelist", "change", "history"):
            args = [] if action == "changelist" else [obj.pk]
            assert (
                admin_client.get(
                    reverse(f"admin:campaigns_{name}_{action}", args=args)
                ).status_code
                == HTTPStatus.OK
            )


@pytest.mark.django_db
@pytest.mark.parametrize(("active", "superuser"), [(True, False), (False, True)])
def test_campaign_publishers_deny_staff_and_inactive_administrators(
    active: bool, superuser: bool
) -> None:
    requester = UserFactory.create(
        is_staff=True, is_active=active, is_superuser=superuser
    )
    template = DonationThankYouTemplate.objects.create(
        name="Guarded template", email_subject="Receipt"
    )
    letter = example_letter(template)
    letter.save()
    with pytest.raises(PermissionDenied):
        schedule_campaign(
            str(uuid4()),
            requester=requester,
            site_url="https://example.org/",
            test_emails=[requester.email],
        )
    with pytest.raises(PermissionDenied):
        schedule_letter_preview(
            letter, requester=requester, site_url="https://example.org/"
        )
    with pytest.raises(PermissionDenied):
        issue_letter(letter, requester=requester, site_url="https://example.org/")
    with pytest.raises(PermissionDenied):
        resend_letter(letter, requester=requester, site_url="https://example.org/")
    letter.refresh_from_db()
    assert letter.issued_at is None
    assert not letter.pdf
    assert not TaskResult.objects.exists()


@pytest.mark.django_db
def test_staff_cannot_read_campaign_tasks_groups_or_audit_after_demotion(
    client: Client,
) -> None:
    operator = UserFactory.create(is_staff=True, is_superuser=True)
    today = timezone.localdate()
    campaign = DonationCampaign.objects.create(
        email_main_subject="Private campaign diagnostics",
        email_main_template=EMAIL_TEMPLATE,
        goal_usd=5000,
        donation_url="https://example.org/give",
        start_date=today,
        end_date=today,
    )
    receipt = schedule_campaign(
        str(campaign.pk),
        requester=operator,
        site_url="https://example.org/",
        test_emails=[operator.email],
    )
    template = DonationThankYouTemplate.objects.create(
        name="Private acknowledgment diagnostics", email_subject="Receipt"
    )
    letter_task = schedule_letter_preview(
        template, requester=operator, site_url="https://example.org/"
    )
    private_logs = list(LogEntry.objects.values_list("pk", flat=True))
    private_group = GroupResult.objects.get(group_id=receipt.group_id)
    private_tasks = list(TaskResult.objects.all())
    assert {task.task_id for task in private_tasks} == {*receipt.task_ids, letter_task}
    ordinary_task = TaskResult.objects.create(
        task_id=str(uuid4()),
        task_name="celery.backend_cleanup",
        status=TaskResultStatus.SUCCESS,
    )
    ordinary_group = GroupResult.objects.create(group_id=str(uuid4()), result="[]")
    ordinary_log = LogEntry.record(
        actor_email=operator.email,
        action_flag=LogEntry.Action.ACTION,
        object_repr="Visible unrelated admin action",
        change_message="Requested unrelated work.",
    )
    # Missing group metadata must not exclude unrelated groups via a NULL subquery.
    for details in ({}, {"group_id": None}):
        LogEntry.record(
            actor_email=operator.email,
            action_flag=LogEntry.Action.CHANGE,
            model_label="campaigns.donationcampaign",
            object_repr="Private campaign without group",
            details=details,
        )
    operator.is_superuser = False
    operator.save(update_fields=["is_superuser"])
    operator.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="campaigns"),
        Permission.objects.get(
            content_type__app_label="users", codename="view_logentry"
        ),
    )
    client.force_login(operator)
    for name, hidden_ids, visible_id in (
        (
            "django_celery_results_taskresult",
            [task.pk for task in private_tasks],
            ordinary_task.pk,
        ),
        ("django_celery_results_groupresult", [private_group.pk], ordinary_group.pk),
        ("users_logentry", private_logs, ordinary_log.pk),
    ):
        listing = client.get(reverse(f"admin:{name}_changelist"))
        assert listing.status_code == HTTPStatus.OK
        visible = set(listing.context["cl"].queryset.values_list("pk", flat=True))
        assert visible_id in visible
        assert not set(hidden_ids) & visible
        for pk in hidden_ids:
            detail = client.get(reverse(f"admin:{name}_change", args=[pk]))
            assert detail.status_code == HTTPStatus.FOUND
        assert (
            client.get(reverse(f"admin:{name}_change", args=[visible_id])).status_code
            == HTTPStatus.OK
        )
    index = client.get(reverse("admin:index"))
    assert [entry.pk for entry in index.context["recent_admin_actions"]] == [
        ordinary_log.pk
    ]
    assert campaign.email_main_subject.encode() not in index.content
    operator.is_superuser = True
    operator.save(update_fields=["is_superuser"])
    client.force_login(operator)
    for name, pk in (
        ("django_celery_results_taskresult", private_tasks[0].pk),
        ("django_celery_results_groupresult", private_group.pk),
        ("users_logentry", private_logs[0]),
    ):
        assert (
            client.get(reverse(f"admin:{name}_change", args=[pk])).status_code
            == HTTPStatus.OK
        )

    # Task expiry and campaign deletion cannot make their old group public.
    TaskResult.objects.filter(task_id__in=receipt.task_ids).delete()
    campaign.delete()
    operator.is_superuser = False
    operator.save(update_fields=["is_superuser"])
    client.force_login(operator)
    listing = client.get(reverse("admin:django_celery_results_groupresult_changelist"))
    visible = set(listing.context["cl"].queryset.values_list("pk", flat=True))
    assert private_group.pk not in visible
    assert ordinary_group.pk in visible
