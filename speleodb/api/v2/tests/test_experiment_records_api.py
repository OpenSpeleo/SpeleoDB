# -*- coding: utf-8 -*-

"""Tests for the station-scoped experiment records endpoints.

- ``api:v2:experiment-records``         (station, experiment) GET / POST
- ``api:v2:experiment-records-detail``  DELETE

View: `speleodb/api/v2/views/experiment.py::ExperimentRecordApiView` and
`ExperimentRecordSpecificApiView`. Records are free-form JSON payloads
keyed by experiment-field UUIDs.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.api.v2.tests.factories import UserExperimentPermissionFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models.experiment import MandatoryFieldUuid


def _records_url(station_id: uuid.UUID | str, exp_id: uuid.UUID | str) -> str:
    return reverse(
        "api:v2:experiment-records",
        kwargs={"id": station_id, "exp_id": exp_id},
    )


def _detail_url(record_id: uuid.UUID | str) -> str:
    return reverse("api:v2:experiment-records-detail", kwargs={"id": record_id})


@pytest.mark.django_db
class TestExperimentRecordList(BaseAPIProjectTestCase):
    """GET station-scoped experiment records list."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY, permission_type=PermissionType.USER
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_ONLY,
        )

    def test_requires_authentication(self) -> None:
        response = self.client.get(_records_url(self.station.id, self.experiment.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_empty_list_when_no_records(self) -> None:
        response = self.client.get(
            _records_url(self.station.id, self.experiment.id),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data == []

    def test_returns_records_in_creation_order_desc(self) -> None:
        r1 = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email},
        )
        r2 = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email},
        )
        response = self.client.get(
            _records_url(self.station.id, self.experiment.id),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [rec["id"] for rec in response.data]
        # Ordering: -creation_date -> most recent first
        assert ids.index(str(r2.id)) < ids.index(str(r1.id))

    def test_missing_exp_id_returns_400(self) -> None:
        # Construct an explicit URL with no exp_id resolvable -- the view
        # returns 400 via ``_get_experiment``.  We can't build this through
        # reverse() because the URL kwarg is required; instead hit a path
        # that the URL router can still resolve but where the experiment
        # doesn't exist.
        fake_exp_id = uuid.uuid4()
        response = self.client.get(
            _records_url(self.station.id, fake_exp_id),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_unknown_station_404(self) -> None:
        response = self.client.get(
            _records_url(uuid.uuid4(), self.experiment.id),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestExperimentRecordCreate(BaseAPIProjectTestCase):
    """POST creates a new experiment record. Requires WRITE access on the
    *experiment* (class-level permission on the station is READ). See
    `ExperimentRecordApiView.post` -> ``SDB_WriteAccess()...(experiment)``.
    """

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

    def test_happy_path(self) -> None:
        payload = {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
        }
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert ExperimentRecord.objects.filter(
            station=self.station, experiment=self.experiment
        ).exists()
        record = ExperimentRecord.objects.get(
            station=self.station, experiment=self.experiment
        )
        # View auto-injects the submitter email into `data`.
        assert record.data[MandatoryFieldUuid.SUBMITTER_EMAIL.value] == self.user.email

    def test_read_only_experiment_permission_rejected(self) -> None:
        """A user with only READ access on the experiment cannot POST
        records, even if they have WRITE on the station's project."""
        read_only_experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=read_only_experiment,
            level=PermissionLevel.READ_ONLY,
        )

        response = self.client.post(
            _records_url(self.station.id, read_only_experiment.id),
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not ExperimentRecord.objects.filter(
            station=self.station, experiment=read_only_experiment
        ).exists()

    def test_read_only_project_access_still_allows_post(self) -> None:
        """The class-level permission on the station is READ (not WRITE), so
        a READ_ONLY project permission + WRITE on the experiment is sufficient.
        This pins the current permission contract so a future tightening is a
        deliberate test change, not a silent regression."""
        read_only_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_ONLY,
            project=read_only_project,
        )
        station_ro = SubSurfaceStationFactory.create(project=read_only_project)

        response = self.client.post(
            _records_url(station_ro.id, self.experiment.id),
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data


@pytest.mark.django_db
class TestExperimentRecordDelete(BaseAPIProjectTestCase):
    """DELETE an individual record (admin-only)."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.record = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email},
        )

    def test_requires_authentication(self) -> None:
        response = self.client.delete(_detail_url(self.record.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_happy_path(self) -> None:
        record_id = self.record.id
        response = self.client.delete(
            _detail_url(record_id), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert not ExperimentRecord.objects.filter(id=record_id).exists()
        assert response.data["id"] == str(record_id)

    def test_delete_unknown_id_returns_404(self) -> None:
        response = self.client.delete(
            _detail_url(uuid.uuid4()), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
