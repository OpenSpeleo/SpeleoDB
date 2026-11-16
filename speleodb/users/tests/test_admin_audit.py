"""Administrator history is permanent and follows the actual admin action."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import django.contrib.admin.models
import pytest
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.urls import reverse

from speleodb.users.models import LogEntry

if TYPE_CHECKING:
    from django.test import Client

    from speleodb.users.models import User


@pytest.mark.django_db
def test_even_superusers_cannot_delete_admin_history(
    admin_client: Client,
    admin_user: User,
) -> None:
    entry = LogEntry.objects.create(
        actor_email=admin_user.email,
        action_flag=LogEntry.Action.CHANGE,
        object_repr="Audit target",
        change_message="Changed the project name.",
    )
    response = admin_client.post(
        reverse("admin:users_logentry_delete", args=[entry.pk]), {"post": "yes"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert LogEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_admin_history_cannot_be_edited_or_bulk_deleted(
    admin_client: Client,
    admin_user: User,
) -> None:
    entry = LogEntry.record(
        actor_email=admin_user.email,
        action_flag=LogEntry.Action.CHANGE,
        object_repr="Original target",
        change_message="Original description",
    )
    response = admin_client.post(
        reverse("admin:users_logentry_change", args=[entry.pk]),
        {"object_repr": "Rewritten target", "change_message": "Rewritten history"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    admin_client.post(
        reverse("admin:users_logentry_changelist"),
        {"action": "delete_selected", "_selected_action": [entry.pk], "post": "yes"},
    )
    entry.refresh_from_db()
    assert entry.object_repr == "Original target"
    assert entry.change_message == "Original description"


@pytest.mark.django_db
def test_native_admin_crud_and_object_history_use_email_snapshots(
    admin_client: Client,
    admin_user: User,
) -> None:
    # An unchanged third-party admin must also use the central audit integration.
    response = admin_client.post(
        reverse("admin:auth_group_add"), {"name": "Original group"}
    )
    assert response.status_code == HTTPStatus.FOUND
    group = Group.objects.get(name="Original group")
    response = admin_client.post(
        reverse("admin:auth_group_change", args=[group.pk]),
        {"name": "Renamed group"},
    )
    assert response.status_code == HTTPStatus.FOUND
    entries = LogEntry.objects.filter(model_label="auth.group", object_id=str(group.pk))
    assert set(entries.values_list("action_flag", flat=True)) == {
        LogEntry.Action.ADDITION,
        LogEntry.Action.CHANGE,
    }
    assert set(entries.values_list("actor_email", flat=True)) == {admin_user.email}
    history = admin_client.get(reverse("admin:auth_group_history", args=[group.pk]))
    assert history.status_code == HTTPStatus.OK
    assert admin_user.email in history.content.decode()
    assert "Changed Name." in history.content.decode()
    response = admin_client.post(
        reverse("admin:auth_group_delete", args=[group.pk]),
        {"post": "yes"},
    )
    assert response.status_code == HTTPStatus.FOUND
    assert not Group.objects.filter(pk=group.pk).exists()
    assert list(entries.values_list("action_flag", flat=True)) == [
        LogEntry.Action.DELETION,
        LogEntry.Action.CHANGE,
        LogEntry.Action.ADDITION,
    ]
    assert entries.filter(action_flag=LogEntry.Action.DELETION).exists()
    assert not django.contrib.admin.models.LogEntry.objects.exists()


@pytest.mark.django_db
def test_bulk_delete_preserves_each_target_history(admin_client: Client) -> None:
    groups = [Group.objects.create(name=f"Bulk target {number}") for number in range(2)]
    response = admin_client.post(
        reverse("admin:auth_group_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [group.pk for group in groups],
            "post": "yes",
        },
    )
    assert response.status_code == HTTPStatus.FOUND
    assert not Group.objects.filter(pk__in=[group.pk for group in groups]).exists()
    assert set(LogEntry.objects.values_list("object_id", flat=True)) == {
        str(group.pk) for group in groups
    }
    assert not django.contrib.admin.models.LogEntry.objects.exists()


@pytest.mark.django_db
def test_recent_preview_does_not_limit_full_history(
    admin_client: Client,
    admin_user: User,
) -> None:
    total_entries = 11
    for number in range(total_entries):
        LogEntry.record(
            actor_email=admin_user.email,
            action_flag=LogEntry.Action.ACTION,
            object_repr=f"Request number {number}",
            change_message="Requested work.",
        )
    index = admin_client.get(reverse("admin:index"))
    assert index.status_code == HTTPStatus.OK
    content = index.content.decode()
    assert "Request number 0<" not in content
    assert "Request number 10<" in content
    assert reverse("admin:users_logentry_changelist") in content
    history = admin_client.get(reverse("admin:users_logentry_changelist"))
    assert history.status_code == HTTPStatus.OK
    assert "Request number 0" in history.content.decode()
    assert LogEntry.objects.count() == total_entries


@pytest.mark.django_db
def test_history_preserves_staff_permissions_and_escapes_messages(
    admin_client: Client,
    admin_user: User,
) -> None:
    group = Group.objects.create(name="Visible target")
    entry = LogEntry.record(
        actor_email=admin_user.email,
        action_flag=LogEntry.Action.ACTION,
        obj=group,
        change_message="Requested <script>alert('x')</script>",
    )
    admin_user.is_superuser = False
    admin_user.save(update_fields=["is_superuser"])
    response = admin_client.get(reverse("admin:users_logentry_change", args=[entry.pk]))
    assert response.status_code == HTTPStatus.OK
    assert "&lt;script&gt;" in response.content.decode()
    assert "<script>alert" not in response.content.decode()
    site = Site.objects.get_current()
    response = admin_client.get(reverse("admin:sites_site_history", args=[site.pk]))
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
@pytest.mark.parametrize(
    "message",
    ["[null]", '[{"changed": {}}]', '[{"added": "<script>bad</script>"}]'],
)
def test_malformed_historical_messages_remain_readable(
    admin_client: Client, admin_user: User, message: str
) -> None:
    group = Group.objects.create(name="Historical message target")
    entry = LogEntry.record(
        actor_email=admin_user.email,
        action_flag=LogEntry.Action.CHANGE,
        obj=group,
        change_message=message,
    )
    for url in (
        reverse("admin:index"),
        reverse("admin:users_logentry_changelist"),
        reverse("admin:users_logentry_change", args=[entry.pk]),
        reverse("admin:auth_group_history", args=[group.pk]),
    ):
        response = admin_client.get(url)
        assert response.status_code == HTTPStatus.OK
        assert "Historical message target" in response.content.decode()
        assert "<script>bad</script>" not in response.content.decode()
    entry.refresh_from_db()
    assert entry.change_message == message
    assert entry.get_change_message() == message
