"""Factories evaluate Django's current clock when building each record."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from speleodb.api.v2.tests.factories import PluginReleaseFactory
from speleodb.api.v2.tests.factories import ProjectCommitFactory
from speleodb.api.v2.tests.factories import PublicAnnoucementFactory
from speleodb.surveys.models import Project

if TYPE_CHECKING:
    from datetime import datetime

    import pytest

    from speleodb.plugins.models import PluginRelease
    from speleodb.plugins.models import PublicAnnoucement
    from speleodb.surveys.models import ProjectCommit


def test_commit_factory_uses_current_django_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now: datetime = timezone.now() - timedelta(days=7)
    monkeypatch.setattr(timezone, "now", lambda: now)
    project: Project = Project()
    first: ProjectCommit = ProjectCommitFactory.build(project=project)
    assert first.authored_date == now

    now += timedelta(days=1)
    second: ProjectCommit = ProjectCommitFactory.build(project=project)
    assert second.authored_date == now


def test_announcement_factory_uses_current_django_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now: datetime = timezone.now() - timedelta(days=7)
    monkeypatch.setattr(timezone, "now", lambda: now)
    first: PublicAnnoucement = PublicAnnoucementFactory.build()
    assert first.creation_date == first.modified_date == now

    now += timedelta(days=1)
    second: PublicAnnoucement = PublicAnnoucementFactory.build()
    assert second.creation_date == second.modified_date == now


def test_release_factory_uses_current_django_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now: datetime = timezone.now() - timedelta(days=7)
    monkeypatch.setattr(timezone, "now", lambda: now)
    first: PluginRelease = PluginReleaseFactory.build()
    assert first.creation_date == first.modified_date == now

    now += timedelta(days=1)
    second: PluginRelease = PluginReleaseFactory.build()
    assert second.creation_date == second.modified_date == now
