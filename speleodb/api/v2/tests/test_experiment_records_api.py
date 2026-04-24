# -*- coding: utf-8 -*-

"""Tests for the station-scoped experiment records endpoints.

- ``api:v2:experiment-records``         (station, experiment) GET / POST
- ``api:v2:experiment-records-detail``  PUT / PATCH / DELETE

View: `speleodb/api/v2/views/experiment.py::ExperimentRecordApiView` and
`ExperimentRecordSpecificApiView`. Records are free-form JSON payloads
keyed by experiment-field UUIDs.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.serializers.experiment import ExperimentRecordSerializer
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

    def test_unknown_exp_id_returns_404(self) -> None:
        # We can't build a route with a missing ``exp_id`` because the URL
        # kwarg is required, so this pins the routed behavior we can actually
        # hit here: an unknown experiment id returns 404.
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
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_post_non_dict_list_body_returns_400(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            [1, 2, 3],
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert not ExperimentRecord.objects.filter(
            station=self.station, experiment=self.experiment
        ).exists()

    def test_post_non_dict_string_body_returns_400(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            "not a dict",
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert not ExperimentRecord.objects.filter(
            station=self.station, experiment=self.experiment
        ).exists()


@pytest.mark.django_db
class TestExperimentRecordUpdate(BaseAPIProjectTestCase):
    """PUT updates an individual record with station visibility and WRITE access
    on the experiment."""

    # Custom field UUID declared on the experiment so strict-key validation
    # allows it in the record payload.
    CUSTOM_FIELD_UUID = "11111111-2222-3333-4444-555555555555"

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(
            created_by=self.user.email,
            experiment_fields={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: {
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                    "order": 0,
                },
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: {
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                    "order": 1,
                },
                self.CUSTOM_FIELD_UUID: {
                    "name": "Notes",
                    "type": "text",
                    "required": False,
                    "order": 2,
                },
            },
        )
        self.experiment_permission = UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.record = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
                self.CUSTOM_FIELD_UUID: "original value",
            },
        )

    def test_requires_authentication(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_put_happy_path_updates_record_data_and_preserves_submitter(self) -> None:
        payload = {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
            self.CUSTOM_FIELD_UUID: "updated value",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: "spoof@example.com",
        }
        response = self.client.put(
            _detail_url(self.record.id),
            payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert self.record.data == {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
            self.CUSTOM_FIELD_UUID: "updated value",
        }
        assert self.record.station_id == self.station.id
        assert self.record.experiment_id == self.experiment.id
        assert (
            response.data["data"][MandatoryFieldUuid.SUBMITTER_EMAIL.value]
            == self.user.email
        )

    def test_read_only_experiment_permission_rejected(self) -> None:
        self.experiment_permission.level = PermissionLevel.READ_ONLY
        self.experiment_permission.save()

        response = self.client.put(
            _detail_url(self.record.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

        self.record.refresh_from_db()
        assert self.record.data[self.CUSTOM_FIELD_UUID] == "original value"

    def test_read_only_project_access_still_allows_put(self) -> None:
        """Editing matches add semantics: READ on the station plus WRITE on the
        experiment is sufficient."""
        read_only_project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_ONLY,
            project=read_only_project,
        )
        station_ro = SubSurfaceStationFactory.create(project=read_only_project)
        record_ro = ExperimentRecord.objects.create(
            station=station_ro,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
            },
        )

        response = self.client.put(
            _detail_url(record_ro.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-03-03"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        record_ro.refresh_from_db()
        assert record_ro.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == "2025-03-03"
        assert (
            record_ro.data[MandatoryFieldUuid.SUBMITTER_EMAIL.value] == self.user.email
        )

    def test_put_requires_station_visibility_even_with_experiment_write(self) -> None:
        hidden_project = ProjectFactory.create(created_by="other@example.com")
        hidden_station = SubSurfaceStationFactory.create(project=hidden_project)
        hidden_record = ExperimentRecord.objects.create(
            station=hidden_station,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
                self.CUSTOM_FIELD_UUID: "hidden station value",
            },
        )

        response = self.client.put(
            _detail_url(hidden_record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-03-03",
                self.CUSTOM_FIELD_UUID: "should be rejected",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

        hidden_record.refresh_from_db()
        assert hidden_record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == (
            "2025-01-01"
        )
        assert hidden_record.data[self.CUSTOM_FIELD_UUID] == "hidden station value"

    def test_put_unknown_id_returns_404(self) -> None:
        response = self.client.put(
            _detail_url(uuid.uuid4()),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_put_omitting_a_field_removes_it(self) -> None:
        """PUT replaces the entire ``data`` payload. Fields that are not in
        the request must disappear from the stored record."""
        payload = {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-04-04"}
        response = self.client.put(
            _detail_url(self.record.id),
            payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        # The custom field was on the original record and is not in the
        # payload -> PUT semantics drop it. SUBMITTER_EMAIL is server-restored.
        assert self.record.data == {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-04-04",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
        }
        assert self.CUSTOM_FIELD_UUID not in self.record.data

    def test_patch_merges_partial_payload_and_preserves_other_fields(self) -> None:
        """PATCH must MERGE the payload into existing ``data``. Fields not in
        the payload must be preserved, not wiped."""
        payload = {self.CUSTOM_FIELD_UUID: "patched value"}
        response = self.client.patch(
            _detail_url(self.record.id),
            payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert self.record.data == {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
            self.CUSTOM_FIELD_UUID: "patched value",
        }

    def test_patch_empty_body_is_a_noop_on_data(self) -> None:
        """An empty PATCH body must not destroy the record. This is the
        regression test for the wholesale-replace bug."""
        before = dict(self.record.data)

        response = self.client.patch(
            _detail_url(self.record.id),
            {},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert self.record.data == before

    def test_patch_cannot_spoof_submitter_email(self) -> None:
        payload = {
            self.CUSTOM_FIELD_UUID: "patched",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: "spoof@example.com",
        }
        response = self.client.patch(
            _detail_url(self.record.id),
            payload,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert (
            self.record.data[MandatoryFieldUuid.SUBMITTER_EMAIL.value]
            == self.user.email
        )

    def test_put_non_dict_body_returns_400(self) -> None:
        """The view must reject a non-object JSON body cleanly, not 500."""
        response = self.client.put(
            _detail_url(self.record.id),
            [1, 2, 3],
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        self.record.refresh_from_db()
        # Ensure the record is untouched by the rejected request.
        assert self.record.data[self.CUSTOM_FIELD_UUID] == "original value"

    def test_patch_non_dict_body_returns_400(self) -> None:
        response = self.client.patch(
            _detail_url(self.record.id),
            "not a dict",
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_admin_permission_allows_edit(self) -> None:
        """Admin permission satisfies the (deletion & admin) | (edition & write)
        chain on PUT. Pins the OR-of-permissions contract."""
        self.experiment_permission.level = PermissionLevel.ADMIN
        self.experiment_permission.save()

        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-05-05",
                self.CUSTOM_FIELD_UUID: "admin-edited",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert self.record.data[self.CUSTOM_FIELD_UUID] == "admin-edited"
        assert (
            self.record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == "2025-05-05"
        )


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


@pytest.mark.django_db
class TestExperimentRecordDeletePermissions(BaseAPIProjectTestCase):
    """Pins that DELETE requires ADMIN on the experiment plus station
    visibility."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.READ_AND_WRITE,
            permission_type=PermissionType.USER,
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        self.experiment_permission = UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.record = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email},
        )

    def test_write_user_cannot_delete_record(self) -> None:
        response = self.client.delete(
            _detail_url(self.record.id), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert ExperimentRecord.objects.filter(id=self.record.id).exists()

    def test_admin_still_cannot_delete_without_station_visibility(self) -> None:
        self.experiment_permission.level = PermissionLevel.ADMIN
        self.experiment_permission.save()

        hidden_project = ProjectFactory.create(created_by="other@example.com")
        hidden_station = SubSurfaceStationFactory.create(project=hidden_project)
        hidden_record = ExperimentRecord.objects.create(
            station=hidden_station,
            experiment=self.experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email},
        )

        response = self.client.delete(
            _detail_url(hidden_record.id), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert ExperimentRecord.objects.filter(id=hidden_record.id).exists()


@pytest.mark.django_db
class TestExperimentRecordsOnInactiveExperiments(BaseAPIProjectTestCase):
    """All mutations on records whose experiment has been deactivated
    must 404, not silently persist or leak history. The frontend already
    filters ``is_active=false`` out of the list endpoint; without a matching
    backend gate, a direct URL call would be a silent backdoor."""

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
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
            },
        )
        # Deactivate AFTER the record exists so we exercise the "lookup by
        # live record id but experiment is inactive" path.
        self.experiment.is_active = False
        self.experiment.save()

    def test_get_records_on_inactive_experiment_returns_404(self) -> None:
        response = self.client.get(
            _records_url(self.station.id, self.experiment.id),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_post_record_on_inactive_experiment_returns_404(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_put_on_inactive_experiment_returns_404(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

        self.record.refresh_from_db()
        assert self.record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == (
            "2025-01-01"
        )

    def test_patch_on_inactive_experiment_returns_404(self) -> None:
        response = self.client.patch(
            _detail_url(self.record.id),
            {"note": "should not land"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    def test_delete_on_inactive_experiment_returns_404(self) -> None:
        response = self.client.delete(
            _detail_url(self.record.id), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data
        assert ExperimentRecord.objects.filter(id=self.record.id).exists()


@pytest.mark.django_db
class TestExperimentRecordSchemaValidation(BaseAPIProjectTestCase):
    REQUIRED_TEXT_FIELD_UUID = "22222222-3333-4444-5555-666666666666"
    NUMBER_FIELD_UUID = "77777777-8888-9999-aaaa-bbbbbbbbbbbb"
    BOOLEAN_FIELD_UUID = "cccccccc-dddd-eeee-ffff-000000000000"
    SELECT_FIELD_UUID = "12121212-3434-5656-7878-909090909090"
    SELECT_OPTION_WITH_ACCENT = "Très bon"

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(
            created_by=self.user.email,
            experiment_fields={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: {
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                    "order": 0,
                },
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: {
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                    "order": 1,
                },
                self.REQUIRED_TEXT_FIELD_UUID: {
                    "name": "Sample Label",
                    "type": "text",
                    "required": True,
                    "order": 2,
                },
                self.NUMBER_FIELD_UUID: {
                    "name": "Ph",
                    "type": "number",
                    "required": False,
                    "order": 3,
                },
                self.BOOLEAN_FIELD_UUID: {
                    "name": "Confirmed",
                    "type": "boolean",
                    "required": False,
                    "order": 4,
                },
                self.SELECT_FIELD_UUID: {
                    "name": "Quality",
                    "type": "select",
                    "required": False,
                    "order": 5,
                    "options": [self.SELECT_OPTION_WITH_ACCENT, "bad"],
                },
            },
        )
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.record = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
                self.REQUIRED_TEXT_FIELD_UUID: "existing sample",
                self.NUMBER_FIELD_UUID: 12.5,
                self.BOOLEAN_FIELD_UUID: True,
                self.SELECT_FIELD_UUID: self.SELECT_OPTION_WITH_ACCENT,
            },
        )

    def test_post_missing_required_field_rejected_400(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02",
                self.NUMBER_FIELD_UUID: 11.0,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "Sample Label" in str(response.data["errors"]["data"])

    def test_put_omitting_required_field_rejected_400_and_record_unchanged(
        self,
    ) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.NUMBER_FIELD_UUID: 14.0,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        existing_number = 12.5
        self.record.refresh_from_db()
        assert self.record.data[self.REQUIRED_TEXT_FIELD_UUID] == "existing sample"
        assert self.record.data[self.NUMBER_FIELD_UUID] == existing_number

    def test_put_invalid_number_type_rejected_400(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
                self.NUMBER_FIELD_UUID: "14.0",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "must be a number" in str(response.data["errors"]["data"])

    def test_patch_invalid_select_option_rejected_400(self) -> None:
        response = self.client.patch(
            _detail_url(self.record.id),
            {self.SELECT_FIELD_UUID: "excellent"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        self.record.refresh_from_db()
        assert (
            self.record.data[self.SELECT_FIELD_UUID] == self.SELECT_OPTION_WITH_ACCENT
        )

    def test_post_accepts_select_option_with_accents_verbatim(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02",
                self.REQUIRED_TEXT_FIELD_UUID: "new sample",
                self.SELECT_FIELD_UUID: self.SELECT_OPTION_WITH_ACCENT,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert (
            response.data["data"][self.SELECT_FIELD_UUID]
            == self.SELECT_OPTION_WITH_ACCENT
        )

    def test_patch_preserves_existing_select_option_with_accents(self) -> None:
        response = self.client.patch(
            _detail_url(self.record.id),
            {self.NUMBER_FIELD_UUID: 14.0},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert self.record.data[self.NUMBER_FIELD_UUID] == 14.0  # noqa: PLR2004
        assert (
            self.record.data[self.SELECT_FIELD_UUID] == self.SELECT_OPTION_WITH_ACCENT
        )

    def test_put_invalid_boolean_type_rejected_400(self) -> None:
        """Sending a string in place of a real boolean must be rejected.
        Pins the bool-vs-string discrimination in ``_validate_record_value``."""
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
                self.BOOLEAN_FIELD_UUID: "true",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "must be a boolean" in str(response.data["errors"]["data"])

        self.record.refresh_from_db()
        assert self.record.data[self.BOOLEAN_FIELD_UUID] is True

    def test_put_invalid_date_format_rejected_400(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "not-a-date",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "must be a valid date" in str(response.data["errors"]["data"])

    def test_put_accepts_iso_datetime_for_date_field(self) -> None:
        """The validator falls back to ``parse_datetime`` when ``parse_date``
        fails. An ISO datetime string must therefore validate."""
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01T12:30:00",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        self.record.refresh_from_db()
        assert (
            self.record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value]
            == "2025-01-01T12:30:00"
        )

    def test_put_invalid_text_type_rejected_400(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.REQUIRED_TEXT_FIELD_UUID: 12345,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "must be a string" in str(response.data["errors"]["data"])

    def test_put_number_rejects_bool_value(self) -> None:
        """Regression guard: ``isinstance(True, int)`` is True, so the
        validator must explicitly reject booleans for number fields."""
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
                self.NUMBER_FIELD_UUID: True,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "must be a number" in str(response.data["errors"]["data"])

    def test_put_number_rejects_nan_and_inf(self) -> None:
        """``math.isfinite`` must reject NaN and infinity even though they
        are technically ``float`` instances.

        JSON itself can't represent NaN/Inf, so a request body never reaches
        the validator with these values — DRF's JSONField rejects them at
        parse time. We invoke ``_validate_record_value`` directly to pin
        the in-validator branch in case the JSON layer ever loosens.
        """
        ser = ExperimentRecordSerializer()
        field_def = self.experiment.experiment_fields[self.NUMBER_FIELD_UUID]

        for bad_value in (float("nan"), float("inf"), float("-inf")):
            error = ser._validate_record_value(  # noqa: SLF001
                field_id=self.NUMBER_FIELD_UUID,
                field_definition=field_def,
                value=bad_value,
            )
            assert error is not None, (
                f"Expected {bad_value!r} to fail, but validator accepted it"
            )
            assert "must be a finite number" in error

    def test_put_aggregates_multiple_field_errors(self) -> None:
        """``validate()`` must collect ALL field errors into the response,
        not short-circuit on the first failure. Pins UX so users see every
        problem at once."""
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02",
                self.REQUIRED_TEXT_FIELD_UUID: "updated sample",
                self.NUMBER_FIELD_UUID: "not-a-number",
                self.SELECT_FIELD_UUID: "off-list",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        errors_blob = str(response.data["errors"]["data"])
        assert "Ph" in errors_blob
        assert "must be a number" in errors_blob
        assert "Quality" in errors_blob
        assert "must match one of the configured options" in errors_blob


@pytest.mark.django_db
class TestExperimentRecordStrictDataKeys(BaseAPIProjectTestCase):
    """Keys in ``data`` must correspond to fields declared on the experiment.

    Mandatory MEASUREMENT_DATE / SUBMITTER_EMAIL UUIDs are always present via
    ``MandatoryFieldUuid.get_mandatory_fields()``. Any other key must have
    been declared on ``experiment.experiment_fields`` at create time."""

    CUSTOM_FIELD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)
        self.experiment = ExperimentFactory.create(
            created_by=self.user.email,
            experiment_fields={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: {
                    "name": "Measurement Date",
                    "type": "date",
                    "required": True,
                    "order": 0,
                },
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: {
                    "name": "Submitter Email",
                    "type": "text",
                    "required": True,
                    "order": 1,
                },
                self.CUSTOM_FIELD_UUID: {
                    "name": "Notes",
                    "type": "text",
                    "required": False,
                    "order": 2,
                },
            },
        )
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.ADMIN,
        )
        self.record = ExperimentRecord.objects.create(
            station=self.station,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
                self.CUSTOM_FIELD_UUID: "existing",
            },
        )

    def test_post_unknown_field_uuid_rejected_400(self) -> None:
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02",
                "not-a-declared-uuid": "junk",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "Unknown field UUID" in str(response.data["errors"]["data"])

    def test_put_unknown_field_uuid_rejected_400(self) -> None:
        response = self.client.put(
            _detail_url(self.record.id),
            {
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02",
                "not-declared": "junk",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        self.record.refresh_from_db()
        # The record must be untouched by a rejected PUT.
        assert self.record.data[self.CUSTOM_FIELD_UUID] == "existing"

    def test_patch_unknown_field_uuid_rejected_400(self) -> None:
        """PATCH's merged-into-existing payload must still be validated."""
        response = self.client.patch(
            _detail_url(self.record.id),
            {"not-declared": "junk"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

    def test_post_with_only_mandatory_uuids_succeeds(self) -> None:
        """Mandatory UUIDs are always implicitly declared on every experiment;
        a payload using only those must validate."""
        response = self.client.post(
            _records_url(self.station.id, self.experiment.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-02"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data


@pytest.mark.django_db
class TestExperimentRecordPostDualPermissionContract(BaseAPIProjectTestCase):
    """Pin the split-layer permission contract on
    :class:`ExperimentRecordApiView`: BOTH gates apply on POST.

      - station: class-level :class:`SDB_ReadAccess` via ``get_object()``.
      - experiment: inline ``SDB_WriteAccess`` check inside ``post``.

    Each layer can independently reject. Together they form the contract.
    Companion existing tests (kept where they are):

      - ``TestExperimentRecordCreate.test_read_only_experiment_permission_rejected``
        pins the experiment-WRITE gate (station READ, experiment READ -> 403).
      - ``TestExperimentRecordCreate.test_read_only_project_access_still_allows_post``
        pins that station READ alone is sufficient at the station layer
        (station READ-only + experiment WRITE -> 201).

    The two tests below close the remaining gaps.
    """

    def setUp(self) -> None:
        super().setUp()
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        UserExperimentPermissionFactory.create(
            user=self.user,
            experiment=self.experiment,
            level=PermissionLevel.READ_AND_WRITE,
        )

    def test_post_requires_station_read_even_with_experiment_write(self) -> None:
        """Station READ is a real precondition. A user with experiment WRITE
        but ZERO permission on the station's project must be rejected by
        the class-level station gate."""
        unrelated_project = ProjectFactory.create(created_by="someone@example.com")
        # Deliberately do NOT grant any project permission to self.user.
        unreachable_station = SubSurfaceStationFactory.create(project=unrelated_project)

        response = self.client.post(
            _records_url(unreachable_station.id, self.experiment.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01"},
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not ExperimentRecord.objects.filter(
            station=unreachable_station, experiment=self.experiment
        ).exists()

    def test_post_succeeds_with_station_admin_and_experiment_write(self) -> None:
        """Sanity: a more-permissive station permission than what the
        class-level requires must not fail the contract."""
        # ``BaseAPIProjectTestCase.set_test_project_permission`` defaults the
        # user to no permission on ``self.project`` until we set it.
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        station = SubSurfaceStationFactory.create(project=self.project)

        response = self.client.post(
            _records_url(station.id, self.experiment.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01"},
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert ExperimentRecord.objects.filter(
            station=station, experiment=self.experiment
        ).exists()


@pytest.mark.django_db
class TestExperimentRecordDetailRequiresStationAccess(BaseAPIProjectTestCase):
    """Pin the strengthened object-permission traversal for record details.

    ``BaseAccessLevel.has_object_permission(ExperimentRecord)`` in
    :mod:`speleodb.api.v2.permissions` requires BOTH ``SDB_ReadAccess`` on
    the record's underlying station AND the requested level on the
    underlying experiment. PUT / PATCH / DELETE on a record whose station
    is not visible to the caller must therefore return 403, regardless of
    the caller's permission level on the experiment itself.

    This complements
    :class:`TestExperimentRecordPostDualPermissionContract` which pins the
    POST equivalent: POST goes through the inline ``SDB_WriteAccess(experiment)``
    check on the view, NOT through ``has_object_permission(ExperimentRecord)``,
    so the two test paths exercise different code and both must exist.

    If the ``ExperimentRecord`` traversal in ``permissions.py`` is ever
    weakened back to experiment-only, all three tests below fail loudly.
    """

    def setUp(self) -> None:
        super().setUp()
        # Build a record on a station belonging to a project the user has
        # no permission on at all. The user has experiment WRITE / ADMIN
        # depending on the test (set inside the test body).
        self.experiment = ExperimentFactory.create(created_by=self.user.email)
        unrelated_project = ProjectFactory.create(created_by="someone@example.com")
        # Deliberately no UserProjectPermissionFactory for self.user.
        self.unreachable_station = SubSurfaceStationFactory.create(
            project=unrelated_project
        )
        self.record = ExperimentRecord.objects.create(
            station=self.unreachable_station,
            experiment=self.experiment,
            data={
                MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                MandatoryFieldUuid.SUBMITTER_EMAIL.value: self.user.email,
            },
        )

    def _grant_experiment_level(self, level: PermissionLevel) -> None:
        UserExperimentPermissionFactory.create(
            user=self.user, experiment=self.experiment, level=level
        )

    def test_put_on_record_with_unreachable_station_returns_403(self) -> None:
        self._grant_experiment_level(PermissionLevel.READ_AND_WRITE)

        response = self.client.put(
            _detail_url(self.record.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        self.record.refresh_from_db()
        assert self.record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == (
            "2025-01-01"
        )

    def test_patch_on_record_with_unreachable_station_returns_403(self) -> None:
        self._grant_experiment_level(PermissionLevel.READ_AND_WRITE)

        response = self.client.patch(
            _detail_url(self.record.id),
            {MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-02-02"},
            format="json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        self.record.refresh_from_db()
        assert self.record.data[MandatoryFieldUuid.MEASUREMENT_DATE.value] == (
            "2025-01-01"
        )

    def test_delete_on_record_with_unreachable_station_returns_403(self) -> None:
        self._grant_experiment_level(PermissionLevel.ADMIN)

        response = self.client.delete(
            _detail_url(self.record.id), headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert ExperimentRecord.objects.filter(id=self.record.id).exists()
