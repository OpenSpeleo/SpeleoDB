# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import connection
from django.db import transaction
from django.utils import timezone

from speleodb.api.v1.tests.factories import SensorFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.gis.models import InstallStatus
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station


@pytest.mark.django_db
class TestSensorInstallModel:
    @pytest.fixture
    def station(self) -> Station:
        return StationFactory.create()

    @pytest.fixture
    def sensor(self) -> Sensor:
        return SensorFactory.create()

    def test_default_model(self, sensor: Sensor, station: Station) -> None:
        inst = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            created_by="creator@example.com",
        )
        assert inst.status == InstallStatus.INSTALLED
        assert inst.uninstall_date is None
        assert inst.uninstall_user is None

        assert str(inst) == f"[STATUS: INSTALLED]: Sensor: {inst.sensor.id}"

    def test_retrieved_model(self, sensor: Sensor, station: Station) -> None:
        inst = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        assert inst.status == InstallStatus.RETRIEVED
        assert inst.uninstall_date is not None
        assert inst.uninstall_user is not None
        assert str(inst) == f"[STATUS: RETRIEVED]: Sensor: {inst.sensor.id}"

    @pytest.mark.parametrize(
        "status", [InstallStatus.RETRIEVED, InstallStatus.ABANDONED, InstallStatus.LOST]
    )
    def test_constraints_is_retrieved_false_requires_null_retrieval_fields(
        self,
        sensor: Sensor,
        station: Station,
        status: InstallStatus,
    ) -> None:
        inst = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=status,
            uninstall_date=timezone.localdate(),
            uninstall_user="uninstaller@example.com",
            created_by="creator@example.com",
        )
        assert inst.status == status
        assert inst.uninstall_date is not None
        assert inst.uninstall_user is not None

        assert str(inst) == f"[STATUS: {status.upper()}]: Sensor: {inst.sensor.id}"

        # Invalid: status != InstallStatus.INSTALLED but retrieval fields not set
        inst_bad = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=status,
            uninstall_date=None,
            uninstall_user=None,
            created_by="creator@example.com",
        )
        with pytest.raises(ValidationError):
            inst_bad.full_clean()

    def test_constraints_is_retrieved_true_requires_nonnull_retrieval_fields(
        self, sensor: Sensor, station: Station
    ) -> None:
        # Valid: is_retrieved=True with fields set
        inst = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        inst.full_clean()  # should pass

        # Invalid: `status=InstallStatus.RETRIEVED` but uninstall_user is null
        inst_bad = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user=None,
            created_by="creator@example.com",
        )
        with pytest.raises(ValidationError):
            inst_bad.full_clean()

        # Invalid: `status=InstallStatus.RETRIEVED` but uninstall_user is null
        inst_bad = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=None,
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        with pytest.raises(ValidationError):
            inst_bad.full_clean()

    def test_install_before_or_equal_retrieval_constraint(
        self, sensor: Sensor, station: Station
    ) -> None:
        # Valid: install_date == uninstall_date
        inst1 = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        inst1.full_clean()  # should pass

        # Valid: install_date < uninstall_date
        inst2 = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate() + timedelta(days=1),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        inst2.full_clean()  # should pass

        # Invalid: install_date > uninstall_date
        inst_bad = SensorInstall(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate() + timedelta(days=2),
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        with pytest.raises(ValidationError):
            inst_bad.full_clean()

    def test_due_for_retrieval_strict(self, station: Station) -> None:
        today = timezone.localdate()
        past_date = today - timedelta(days=5)
        future_date = today + timedelta(days=5)

        # expired battery
        inst1 = SensorInstall.objects.create(
            sensor=SensorFactory.create(),
            station=station,
            install_date=past_date,
            install_user="installer@example.com",
            status=InstallStatus.INSTALLED,
            expiracy_battery_date=past_date,
            created_by="creator@example.com",
        )

        # expired memory
        inst2 = SensorInstall.objects.create(
            sensor=SensorFactory.create(),
            station=station,
            install_date=past_date,
            install_user="installer@example.com",
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=past_date,
            created_by="creator@example.com",
        )
        # future expiration
        inst3 = SensorInstall.objects.create(
            sensor=SensorFactory.create(),
            station=station,
            install_date=past_date,
            install_user="installer@example.com",
            status=InstallStatus.INSTALLED,
            expiracy_battery_date=future_date,
            created_by="creator@example.com",
        )

        due = SensorInstall.objects.due_for_retrieval(days=None)  # pyright: ignore[reportAttributeAccessIssue]
        assert inst1 in due
        assert inst2 in due
        assert inst3 not in due

    def test_due_for_retrieval_with_days(self, station: Station) -> None:
        today = timezone.localdate()
        near_future = today + timedelta(days=3)
        far_future = today + timedelta(days=10)

        inst1 = SensorInstall.objects.create(
            sensor=SensorFactory.create(),
            station=station,
            install_date=today,
            install_user="installer@example.com",
            status=InstallStatus.INSTALLED,
            expiracy_battery_date=near_future,
            created_by="creator@example.com",
        )
        inst2 = SensorInstall.objects.create(
            sensor=SensorFactory.create(),
            station=station,
            install_date=today,
            install_user="installer@example.com",
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=far_future,
            created_by="creator@example.com",
        )

        # days=5 → include inst1 but not inst2
        due = SensorInstall.objects.due_for_retrieval(days=5)  # pyright: ignore[reportAttributeAccessIssue]
        assert inst1 in due
        assert inst2 not in due

        # days=15 → include both
        due = SensorInstall.objects.due_for_retrieval(days=15)  # pyright: ignore[reportAttributeAccessIssue]
        assert inst1 in due
        assert inst2 in due

    def test_due_for_retrieval_ignores_retrieved(
        self, sensor: Sensor, station: Station
    ) -> None:
        today = timezone.localdate()
        past_date = today - timedelta(days=3)
        inst = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=past_date,
            install_user="installer@example.com",
            status=InstallStatus.RETRIEVED,  # retrieved already
            expiracy_battery_date=past_date,
            uninstall_date=today,
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )
        due = SensorInstall.objects.due_for_retrieval(days=None)  # pyright: ignore[reportAttributeAccessIssue]
        assert inst not in due

    @pytest.mark.skipif(
        connection.vendor == "sqlite",
        reason="Partial unique constraint not supported on SQLite",
    )
    def test_unique_installed_per_sensor(
        self, sensor: Sensor, station: Station
    ) -> None:
        # Create the first installed sensor
        _ = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer1@example.com",
            created_by="creator@example.com",
        )

        # Verify it exists
        assert (
            SensorInstall.objects.filter(
                sensor=sensor,
                status=InstallStatus.INSTALLED,
            ).count()
            == 1
        )

        # Attempt to create a second installed sensor for the same sensor
        # Must use transaction.atomic for proper cleanup after IntegrityError
        with transaction.atomic(), pytest.raises(IntegrityError):
            SensorInstall.objects.create(
                sensor=sensor,
                station=station,
                install_date=timezone.localdate(),
                install_user="installer2@example.com",
                status=InstallStatus.INSTALLED,
                created_by="creator@example.com",
            )

        # If we change the status to RETRIEVED, it should succeed
        _ = SensorInstall.objects.create(
            sensor=sensor,
            station=station,
            install_date=timezone.localdate(),
            install_user="installer2@example.com",
            status=InstallStatus.RETRIEVED,
            uninstall_date=timezone.localdate(),
            uninstall_user="retriever@example.com",
            created_by="creator@example.com",
        )

        assert (
            SensorInstall.objects.filter(
                sensor=sensor,
                status=InstallStatus.INSTALLED,
            ).count()
            == 1
        )

        assert (
            SensorInstall.objects.filter(
                sensor=sensor,
                status=InstallStatus.RETRIEVED,
            ).count()
            == 1
        )
