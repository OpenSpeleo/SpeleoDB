"""The direction cutover preserves survey identity and user-owned lead data."""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from speleodb.api.v2.tests.factories import ProjectFactory


@pytest.mark.django_db(transaction=True)
def test_direction_migration_preserves_leads_sources_and_reversible_bearings() -> None:
    old_target = [("gis", "0047_exploration_lead_sources_and_headings")]
    executor = MigrationExecutor(connection)
    latest_targets = executor.loader.graph.leaf_nodes()
    executor.migrate(old_target)
    try:
        old_apps = executor.loader.project_state(old_target).apps
        old_lead_model = old_apps.get_model("gis", "ExplorationLead")
        old_source_model = old_apps.get_model("gis", "ExplorationLeadSource")
        project = ProjectFactory.create()
        records: list[dict[str, Any]] = []
        for index, headings in enumerate([[], [337.5], [90, 90, 359.9]]):
            lead = old_lead_model.objects.create(
                project_id=project.pk,
                description=f"Original field notes {index}\n !N! ",
                headings=headings,
                latitude="20.1234567",
                longitude="-87.1234567",
                created_by="surveyor@example.test",
            )
            records.append(old_lead_model.objects.values().get(pk=lead.pk))
            old_source_model.objects.create(
                project_id=project.pk,
                lead_id=lead.pk,
                kind=1,
                digest=str(index),
                payload=f"native-source-{index}",
                source_format="ARIANE",
            )
        old_source_model.objects.create(
            project_id=project.pk,
            lead_id=None,
            kind=1,
            digest="deleted",
            payload="deleted-source",
            source_format="ARIANE",
        )
        sources = list(old_source_model.objects.order_by("pk").values())

        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)
        new_apps = executor.loader.project_state(latest_targets).apps
        new_lead_model = new_apps.get_model("gis", "ExplorationLead")
        new_source_model = new_apps.get_model("gis", "ExplorationLeadSource")
        for record in records:
            copied = new_lead_model.objects.values().get(pk=record["id"])
            assert copied.pop("directions") == (
                [{"heading": value, "checked": False} for value in record["headings"]]
                or [{"heading": None, "checked": False}]
            )
            assert copied == {
                key: value for key, value in record.items() if key != "headings"
            }
        assert list(new_source_model.objects.order_by("pk").values()) == sources

        # Reverse restores bearings without manufacturing an old-schema status.
        new_lead_model.objects.filter(pk=records[-1]["id"]).update(
            directions=[
                {"heading": 90, "checked": True},
                {"heading": None, "checked": False},
                {"heading": 90, "checked": False},
            ]
        )
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        restored_model = executor.loader.project_state(old_target).apps.get_model(
            "gis", "ExplorationLead"
        )
        assert restored_model.objects.get(pk=records[-1]["id"]).headings == [90, 90]
    finally:
        # Restore the current graph before pytest flushes or another test uses it.
        MigrationExecutor(connection).migrate(latest_targets)
