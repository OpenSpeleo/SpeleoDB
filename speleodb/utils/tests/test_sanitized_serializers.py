# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest

from speleodb.api.v2.serializers.announcement import PublicAnnoucementSerializer
from speleodb.api.v2.serializers.cylinder_fleet import CylinderFleetSerializer
from speleodb.api.v2.serializers.cylinder_fleet import CylinderInstallSerializer
from speleodb.api.v2.serializers.cylinder_fleet import CylinderPressureCheckSerializer
from speleodb.api.v2.serializers.cylinder_fleet import CylinderSerializer
from speleodb.api.v2.serializers.experiment import ExperimentRecordSerializer
from speleodb.api.v2.serializers.experiment import ExperimentSerializer
from speleodb.api.v2.serializers.exploration_lead import ExplorationLeadSerializer
from speleodb.api.v2.serializers.gis_view import GISViewCreateUpdateSerializer
from speleodb.api.v2.serializers.gps_track import GPSTrackSerializer
from speleodb.api.v2.serializers.landmark import LandmarkSerializer
from speleodb.api.v2.serializers.log_entry import StationLogEntrySerializer
from speleodb.api.v2.serializers.project import ProjectSerializer
from speleodb.api.v2.serializers.sensor_fleet import SensorFleetSerializer
from speleodb.api.v2.serializers.sensor_fleet import SensorSerializer
from speleodb.api.v2.serializers.station import StationResourceSerializer
from speleodb.api.v2.serializers.station import StationSerializer
from speleodb.api.v2.serializers.station import SubSurfaceStationSerializer
from speleodb.api.v2.serializers.station import SurfaceStationSerializer
from speleodb.api.v2.serializers.station_tag import StationTagSerializer
from speleodb.api.v2.serializers.surface_network import (
    SurfaceMonitoringNetworkSerializer,
)
from speleodb.api.v2.serializers.team import SurveyTeamSerializer
from speleodb.api.v2.serializers.user import UserSerializer
from speleodb.api.v2.tests.factories import ExperimentFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models.experiment import MandatoryFieldUuid
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

if TYPE_CHECKING:
    from rest_framework import serializers

ALL_SANITIZED_SERIALIZERS: list[type[serializers.Serializer]] = [  # type: ignore[type-arg]
    CylinderFleetSerializer,
    CylinderInstallSerializer,
    CylinderPressureCheckSerializer,
    CylinderSerializer,
    ExperimentSerializer,
    ExplorationLeadSerializer,
    GISViewCreateUpdateSerializer,
    GPSTrackSerializer,
    LandmarkSerializer,
    ProjectSerializer,
    PublicAnnoucementSerializer,
    SensorFleetSerializer,
    SensorSerializer,
    StationLogEntrySerializer,
    StationResourceSerializer,
    StationSerializer,
    StationTagSerializer,
    SubSurfaceStationSerializer,
    SurfaceMonitoringNetworkSerializer,
    SurfaceStationSerializer,
    SurveyTeamSerializer,
    UserSerializer,
]


def _build_serializer_field_pairs() -> (
    list[tuple[type[serializers.Serializer], str]]  # type: ignore[type-arg]
):
    pairs: list[tuple[type[serializers.Serializer], str]] = []  # type: ignore[type-arg]
    for cls in ALL_SANITIZED_SERIALIZERS:
        pairs.extend(
            (cls, field)
            for field in cls.sanitized_fields  # type: ignore[attr-defined]
        )
    return pairs


SERIALIZER_FIELD_PAIRS = _build_serializer_field_pairs()
PAIR_IDS = [f"{cls.__name__}.{field}" for cls, field in SERIALIZER_FIELD_PAIRS]


class TestSanitizedFieldsMixinPresence:
    """Verify every serializer in the list actually uses SanitizedFieldsMixin."""

    @pytest.mark.parametrize(
        "serializer_class", ALL_SANITIZED_SERIALIZERS, ids=lambda c: c.__name__
    )
    def test_mixin_in_mro(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
    ) -> None:
        assert issubclass(serializer_class, SanitizedFieldsMixin), (
            f"{serializer_class.__name__} does not use SanitizedFieldsMixin"
        )

    @pytest.mark.parametrize(
        "serializer_class", ALL_SANITIZED_SERIALIZERS, ids=lambda c: c.__name__
    )
    def test_sanitized_fields_is_nonempty(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
    ) -> None:
        assert len(serializer_class.sanitized_fields) > 0, (  # type: ignore[attr-defined]
            f"{serializer_class.__name__}.sanitized_fields is empty"
        )


@pytest.mark.django_db
class TestHTMLStrippingPerField:
    """
    For every (serializer, field) pair, verify that to_internal_value
    strips HTML tags via sanitize_text.

    All payloads are kept under 8 characters so they fit within any
    field's max_length (e.g. CylinderSerializer.serial max_length=15).
    Assertions are case-insensitive to handle validators that transform
    text (e.g. StationTagSerializer.validate_name title-cases).
    """

    @pytest.mark.parametrize(
        ("serializer_class", "field_name"), SERIALIZER_FIELD_PAIRS, ids=PAIR_IDS
    )
    def test_bold_tag_stripped(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
        field_name: str,
    ) -> None:
        ser = serializer_class(partial=True)
        result = ser.to_internal_value({field_name: "<b>x</b>"})
        value = result[field_name]
        assert "<" not in value, (
            f"{serializer_class.__name__}.{field_name}: "
            f"HTML tags not stripped. Got: {value!r}"
        )
        assert "x" in value.lower()

    @pytest.mark.parametrize(
        ("serializer_class", "field_name"), SERIALIZER_FIELD_PAIRS, ids=PAIR_IDS
    )
    def test_img_tag_stripped(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
        field_name: str,
    ) -> None:
        ser = serializer_class(partial=True)
        result = ser.to_internal_value({field_name: "<img>y"})
        value = result[field_name]
        assert "<" not in value
        assert "img" not in value.lower()

    @pytest.mark.parametrize(
        ("serializer_class", "field_name"), SERIALIZER_FIELD_PAIRS, ids=PAIR_IDS
    )
    def test_anchor_tag_stripped(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
        field_name: str,
    ) -> None:
        ser = serializer_class(partial=True)
        result = ser.to_internal_value({field_name: "<a>z</a>"})
        value = result[field_name]
        assert "<" not in value
        assert "z" in value.lower()

    @pytest.mark.parametrize(
        ("serializer_class", "field_name"), SERIALIZER_FIELD_PAIRS, ids=PAIR_IDS
    )
    def test_clean_text_unchanged(
        self,
        serializer_class: type[serializers.Serializer],  # type: ignore[type-arg]
        field_name: str,
    ) -> None:
        ser = serializer_class(partial=True)
        result = ser.to_internal_value({field_name: "Ab1"})
        assert result[field_name].lower() == "ab1"
        assert "<" not in result[field_name]


@pytest.mark.django_db
class TestExperimentRecordDataSanitization:
    """Test schema-aware sanitization for experiment record JSON values."""

    TEXT_FIELD_UUID = "11111111-1111-1111-1111-111111111111"
    SELECT_FIELD_UUID = "22222222-2222-2222-2222-222222222222"

    def _build_record_serializer(
        self,
        *,
        text_value: str,
        select_value: str | None = None,
    ) -> ExperimentRecordSerializer:
        experiment_fields: dict[str, dict[str, Any]] = {
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
            self.TEXT_FIELD_UUID: {
                "name": "Notes",
                "type": "text",
                "required": False,
                "order": 2,
            },
        }
        payload: dict[str, Any] = {
            MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
            MandatoryFieldUuid.SUBMITTER_EMAIL.value: "submitter@example.com",
            self.TEXT_FIELD_UUID: text_value,
        }

        if select_value is not None:
            experiment_fields[self.SELECT_FIELD_UUID] = {
                "name": "Quality",
                "type": "select",
                "required": False,
                "order": 3,
                "options": ["Très bon", "bad"],
            }
            payload[self.SELECT_FIELD_UUID] = select_value

        experiment = ExperimentFactory.create(
            created_by="owner@example.com",
            experiment_fields=experiment_fields,
        )
        station = SubSurfaceStationFactory.create()
        record = ExperimentRecord.objects.create(
            station=station,
            experiment=experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: "submitter@example.com"},
        )
        return ExperimentRecordSerializer(
            record,
            data={
                "experiment": experiment.id,
                "station": station.id,
                "data": payload,
            },
        )

    def test_script_tag_in_text_value_is_stripped_on_save(self) -> None:
        serializer = self._build_record_serializer(
            text_value='<script>alert("xss")</script>value'
        )
        assert serializer.is_valid(), serializer.errors
        updated_record = serializer.save()
        assert "<script>" not in updated_record.data[self.TEXT_FIELD_UUID]
        assert updated_record.data[self.TEXT_FIELD_UUID] == "value"

    def test_img_tag_in_text_value_is_stripped_on_save(self) -> None:
        serializer = self._build_record_serializer(text_value="<img>text")
        assert serializer.is_valid(), serializer.errors
        updated_record = serializer.save()
        assert "<img" not in updated_record.data[self.TEXT_FIELD_UUID]
        assert updated_record.data[self.TEXT_FIELD_UUID] == "text"

    def test_bold_tag_in_text_value_is_stripped_on_save(self) -> None:
        serializer = self._build_record_serializer(text_value="<b>val</b>")
        assert serializer.is_valid(), serializer.errors
        updated_record = serializer.save()
        assert "<" not in updated_record.data[self.TEXT_FIELD_UUID]
        assert updated_record.data[self.TEXT_FIELD_UUID] == "val"

    def test_non_string_values_untouched(self) -> None:
        ser = ExperimentRecordSerializer()
        data: dict[str, Any] = {"int": 42, "float": 3.14, "bool": True, "none": None}
        result = ser.validate_data(data)
        assert result == data

    def test_empty_dict_returns_empty(self) -> None:
        ser = ExperimentRecordSerializer()
        assert ser.validate_data({}) == {}

    def test_non_dict_returns_as_is(self) -> None:
        ser = ExperimentRecordSerializer()
        assert ser.validate_data("not a dict") == "not a dict"  # type: ignore[arg-type, comparison-overlap]

    def test_update_sanitizes_strings_and_preserves_native_types(self) -> None:
        expected_float = 12.5
        text_field = "aaaaaaaa-1111-1111-1111-111111111111"
        num_field = "bbbbbbbb-2222-2222-2222-222222222222"
        bool_field = "cccccccc-3333-3333-3333-333333333333"
        select_field = "dddddddd-4444-4444-4444-444444444444"
        select_value = "Très bon"
        experiment = ExperimentFactory.create(
            created_by="owner@example.com",
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
                text_field: {
                    "name": "Notes",
                    "type": "text",
                    "required": False,
                    "order": 2,
                },
                num_field: {
                    "name": "Ph",
                    "type": "number",
                    "required": False,
                    "order": 3,
                },
                bool_field: {
                    "name": "Confirmed",
                    "type": "boolean",
                    "required": False,
                    "order": 4,
                },
                select_field: {
                    "name": "Quality",
                    "type": "select",
                    "required": False,
                    "order": 5,
                    "options": [select_value, "bad"],
                },
            },
        )
        station = SubSurfaceStationFactory.create()
        record = ExperimentRecord.objects.create(
            station=station,
            experiment=experiment,
            data={MandatoryFieldUuid.SUBMITTER_EMAIL.value: "submitter@example.com"},
        )
        serializer = ExperimentRecordSerializer(
            record,
            data={
                "experiment": experiment.id,
                "station": station.id,
                "data": {
                    MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                    MandatoryFieldUuid.SUBMITTER_EMAIL.value: "submitter@example.com",
                    text_field: "<b>unsafe</b>",
                    num_field: expected_float,
                    bool_field: False,
                    select_field: select_value,
                },
            },
        )

        assert serializer.is_valid(), serializer.errors
        updated_record = serializer.save()

        assert "<" not in updated_record.data[text_field]
        assert updated_record.data[num_field] == expected_float
        assert updated_record.data[bool_field] is False
        assert updated_record.data[select_field] == select_value

    def test_unknown_key_in_data_is_rejected_at_serializer_level(self) -> None:
        """Serializer-level strict-key validation: an unknown UUID in the
        payload must fail ``is_valid()`` with a clear ``data`` error."""
        declared_uuid = "aaaaaaaa-1111-2222-3333-444444444444"
        experiment = ExperimentFactory.create(
            created_by="owner@example.com",
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
                declared_uuid: {
                    "name": "Notes",
                    "type": "text",
                    "required": False,
                    "order": 2,
                },
            },
        )
        station = SubSurfaceStationFactory.create()
        serializer = ExperimentRecordSerializer(
            data={
                "experiment": experiment.id,
                "station": station.id,
                "data": {
                    MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                    MandatoryFieldUuid.SUBMITTER_EMAIL.value: "s@example.com",
                    "undeclared-uuid": "junk",
                },
            }
        )
        assert not serializer.is_valid()
        assert "data" in serializer.errors
        assert "Unknown field UUID" in str(serializer.errors["data"])

    def test_required_record_field_missing_is_rejected_at_serializer_level(
        self,
    ) -> None:
        required_uuid = "eeeeeeee-1111-2222-3333-444444444444"
        experiment = ExperimentFactory.create(
            created_by="owner@example.com",
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
                required_uuid: {
                    "name": "Sample Label",
                    "type": "text",
                    "required": True,
                    "order": 2,
                },
            },
        )
        station = SubSurfaceStationFactory.create()

        serializer = ExperimentRecordSerializer(
            data={
                "experiment": experiment.id,
                "station": station.id,
                "data": {
                    MandatoryFieldUuid.MEASUREMENT_DATE.value: "2025-01-01",
                    MandatoryFieldUuid.SUBMITTER_EMAIL.value: "s@example.com",
                },
            }
        )

        assert not serializer.is_valid()
        assert "data" in serializer.errors
        assert "Sample Label" in str(serializer.errors["data"])

    def test_invalid_record_types_are_rejected_at_serializer_level(self) -> None:
        number_uuid = "11111111-aaaa-bbbb-cccc-222222222222"
        boolean_uuid = "33333333-aaaa-bbbb-cccc-444444444444"
        select_uuid = "55555555-aaaa-bbbb-cccc-666666666666"
        experiment = ExperimentFactory.create(
            created_by="owner@example.com",
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
                number_uuid: {
                    "name": "Ph",
                    "type": "number",
                    "required": False,
                    "order": 2,
                },
                boolean_uuid: {
                    "name": "Confirmed",
                    "type": "boolean",
                    "required": False,
                    "order": 3,
                },
                select_uuid: {
                    "name": "Quality",
                    "type": "select",
                    "required": False,
                    "order": 4,
                    "options": ["good", "bad"],
                },
            },
        )
        station = SubSurfaceStationFactory.create()

        serializer = ExperimentRecordSerializer(
            data={
                "experiment": experiment.id,
                "station": station.id,
                "data": {
                    MandatoryFieldUuid.MEASUREMENT_DATE.value: 20250101,
                    MandatoryFieldUuid.SUBMITTER_EMAIL.value: "s@example.com",
                    number_uuid: "12.5",
                    boolean_uuid: "false",
                    select_uuid: "excellent",
                },
            }
        )

        assert not serializer.is_valid()
        assert "data" in serializer.errors
        assert "Measurement Date" in str(serializer.errors["data"])
        assert "must be a number" in str(serializer.errors["data"])
        assert "must be a boolean" in str(serializer.errors["data"])
        assert "configured options" in str(serializer.errors["data"])

    def test_validate_record_value_select_with_missing_options_is_safe(self) -> None:
        """The model layer rejects select fields without ``options`` (Pydantic
        validation in ``ExperimentFieldDefinition``), so malformed
        definitions cannot reach the validator through the normal API path.

        This pins the validator's defensive ``options or []`` branch in
        case the model invariant is ever loosened: the validator must
        reject every value rather than crash on missing-key access.
        """
        ser = ExperimentRecordSerializer()

        for missing_options_def in (
            {"name": "Misconfigured", "type": "select", "required": False},
            {
                "name": "Misconfigured",
                "type": "select",
                "required": False,
                "options": None,
            },
            {
                "name": "Misconfigured",
                "type": "select",
                "required": False,
                "options": [],
            },
        ):
            error = ser._validate_record_value(  # noqa: SLF001
                field_id="select-no-opts",
                field_definition=missing_options_def,
                value="anything",
            )
            assert error is not None
            assert "Misconfigured" in error
            assert "configured options" in error
