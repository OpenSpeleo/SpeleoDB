# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest

from speleodb.api.v1.serializers.announcement import PublicAnnoucementSerializer
from speleodb.api.v1.serializers.cylinder_fleet import CylinderFleetSerializer
from speleodb.api.v1.serializers.cylinder_fleet import CylinderInstallSerializer
from speleodb.api.v1.serializers.cylinder_fleet import CylinderPressureCheckSerializer
from speleodb.api.v1.serializers.cylinder_fleet import CylinderSerializer
from speleodb.api.v1.serializers.experiment import ExperimentRecordSerializer
from speleodb.api.v1.serializers.experiment import ExperimentSerializer
from speleodb.api.v1.serializers.exploration_lead import ExplorationLeadSerializer
from speleodb.api.v1.serializers.gis_view import GISViewCreateUpdateSerializer
from speleodb.api.v1.serializers.gps_track import GPSTrackSerializer
from speleodb.api.v1.serializers.landmark import LandmarkSerializer
from speleodb.api.v1.serializers.log_entry import StationLogEntrySerializer
from speleodb.api.v1.serializers.project import ProjectSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorSerializer
from speleodb.api.v1.serializers.station import StationResourceSerializer
from speleodb.api.v1.serializers.station import StationSerializer
from speleodb.api.v1.serializers.station import SubSurfaceStationSerializer
from speleodb.api.v1.serializers.station import SurfaceStationSerializer
from speleodb.api.v1.serializers.station_tag import StationTagSerializer
from speleodb.api.v1.serializers.surface_network import (
    SurfaceMonitoringNetworkSerializer,
)
from speleodb.api.v1.serializers.team import SurveyTeamSerializer
from speleodb.api.v1.serializers.user import UserSerializer
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
    """Test that ExperimentRecordSerializer.validate_data sanitizes JSON strings."""

    def test_script_tag_in_json_value_stripped(self) -> None:
        ser = ExperimentRecordSerializer()
        data: dict[str, Any] = {
            "field-uuid-1": '<script>alert("xss")</script>value',
            "field-uuid-2": "clean value",
            "field-uuid-3": 42,
        }
        result = ser.validate_data(data)
        assert "<script>" not in result["field-uuid-1"]
        assert result["field-uuid-2"] == "clean value"
        assert result["field-uuid-3"] == data["field-uuid-3"]

    def test_img_tag_in_json_value_stripped(self) -> None:
        ser = ExperimentRecordSerializer()
        data: dict[str, Any] = {"field-1": "<img>text"}
        result = ser.validate_data(data)
        assert "<img" not in result["field-1"]
        assert "text" in result["field-1"]

    def test_bold_tag_in_json_value_stripped(self) -> None:
        ser = ExperimentRecordSerializer()
        data: dict[str, Any] = {"field-1": "<b>val</b>"}
        result = ser.validate_data(data)
        assert "<" not in result["field-1"]
        assert "val" in result["field-1"]

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
