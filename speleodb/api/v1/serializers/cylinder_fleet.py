# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from rest_framework import serializers

from speleodb.common.enums import InstallStatus
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import CylinderPressureCheck
from speleodb.surveys.models import Project
from speleodb.users.models import User
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

logger = logging.getLogger(__name__)


class CylinderSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[Cylinder]):
    """Serializer for Cylinder model."""

    sanitized_fields: ClassVar[list[str]] = ["name", "brand", "owner", "notes", "type"]

    # Make fleet write-only since we pass it via URL
    fleet = serializers.PrimaryKeyRelatedField(
        queryset=CylinderFleet.objects.all(),
        write_only=True,
        required=False,
    )

    # Read-only fields for API responses
    fleet_id = serializers.UUIDField(source="fleet.id", read_only=True)
    fleet_name = serializers.CharField(source="fleet.name", read_only=True)

    # Latest install info
    latest_install_location = serializers.SerializerMethodField()
    latest_install_lat = serializers.SerializerMethodField()
    latest_install_long = serializers.SerializerMethodField()
    latest_install_date = serializers.SerializerMethodField()
    active_installs = serializers.SerializerMethodField()

    class Meta:
        model = Cylinder
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "latest_install_location",
            "latest_install_lat",
            "latest_install_long",
            "latest_install_date",
            "active_installs",
        ]

    def get_latest_install_location(self, obj: Cylinder) -> str | None:
        """Get location name where the cylinder is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return install.location_name if install else None

    def get_latest_install_lat(self, obj: Cylinder) -> float | None:
        """Get the latitude where the cylinder is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return float(install.latitude) if install else None

    def get_latest_install_long(self, obj: Cylinder) -> float | None:
        """Get the longitude where the cylinder is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return float(install.longitude) if install else None

    def get_latest_install_date(self, obj: Cylinder) -> str | None:
        """Get the install date of the current install."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return (
            install.install_date.isoformat()
            if install and install.install_date
            else None
        )

    def get_active_installs(self, obj: Cylinder) -> list[dict[str, Any]]:
        """Get active installs with full details."""
        installs = obj.installs.filter(status=InstallStatus.INSTALLED)

        active_installs: list[dict[str, Any]] = [
            {
                "id": str(install.id),
                "location_name": install.location_name,
                "latitude": str(install.latitude),
                "longitude": str(install.longitude),
                "distance_from_entry": install.distance_from_entry,
                "unit_system": install.unit_system,
                "install_date": install.install_date.isoformat()
                if install.install_date
                else None,
            }
            for install in installs
        ]

        return active_installs


class CylinderFleetSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[CylinderFleet]
):
    """Serializer for CylinderFleet model with optional initial cylinders."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    # Explicitly declare name field to enforce validation
    name = serializers.CharField(
        max_length=50,
        min_length=1,
        allow_blank=False,
        required=True,
        trim_whitespace=True,
    )

    created_by = serializers.EmailField(required=False)

    # Read-only cylinder count
    cylinder_count = serializers.SerializerMethodField()

    class Meta:
        model = CylinderFleet
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
        ]

    def validate_name(self, value: str) -> str:
        """Validate that fleet name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Fleet name cannot be empty.")
        return value.strip()

    def get_cylinder_count(self, obj: CylinderFleet) -> int:
        """Get the number of cylinders in this fleet."""
        return obj.cylinders.count()

    def create(self, validated_data: dict[str, Any]) -> CylinderFleet:
        """Create a new cylinder fleet with automatic permission creation."""
        cylinder_fleet = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = CylinderFleetUserPermission.objects.create(
            cylinder_fleet=cylinder_fleet,
            user=User.objects.get(email=validated_data["created_by"]),
            level=PermissionLevel.ADMIN,
        )

        return cylinder_fleet

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        created_by = attrs.get("created_by")

        if self.instance is None and created_by is None:
            raise serializers.ValidationError(
                "`created_by` must be specified during creation."
            )

        if self.instance is not None and "created_by" in attrs:
            raise serializers.ValidationError("`created_by` cannot be updated.")

        return attrs


class CylinderFleetWithPermSerializer(serializers.ModelSerializer[CylinderFleet]):
    """Optimized serializer for listing cylinder fleets with user permission level."""

    cylinder_count = serializers.IntegerField(read_only=True)
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.SerializerMethodField()

    class Meta:
        model = CylinderFleet
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_by",
            "creation_date",
            "modified_date",
            "cylinder_count",
            "user_permission_level",
            "user_permission_level_label",
        ]
        read_only_fields = fields

    def get_user_permission_level_label(
        self, obj: CylinderFleet
    ) -> StrOrPromise | None:
        if perm_lvl := getattr(obj, "user_permission_level", None):
            return PermissionLevel.from_value(perm_lvl).label

        return None


class CylinderFleetUserPermissionSerializer(
    serializers.ModelSerializer[CylinderFleetUserPermission]
):
    """Serializer for CylinderFleetUserPermission model."""

    # User email for creation/updates
    user_email = serializers.EmailField(write_only=True, required=False)

    # Read-only user info
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.SerializerMethodField()
    user_display_email = serializers.EmailField(source="user.email", read_only=True)

    # Read-only permission level label
    level_label = serializers.CharField(read_only=True)

    # Fleet info (read-only)
    fleet_id = serializers.UUIDField(source="cylinder_fleet.id", read_only=True)
    fleet_name = serializers.CharField(source="cylinder_fleet.name", read_only=True)

    class Meta:
        model = CylinderFleetUserPermission
        fields = [
            "id",
            "user",
            "user_email",
            "user_id",
            "user_full_name",
            "user_display_email",
            "cylinder_fleet",
            "fleet_id",
            "fleet_name",
            "level",
            "level_label",
            "is_active",
            "deactivated_by",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "user",
            "cylinder_fleet",
            "deactivated_by",
            "creation_date",
            "modified_date",
        ]

    def get_user_full_name(self, obj: CylinderFleetUserPermission) -> str:
        """Get user's full name or email."""
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.user.email

    def validate_user_email(self, value: str) -> str:
        """Validate user exists."""
        try:
            User.objects.get(email=value)
        except User.DoesNotExist as e:
            raise serializers.ValidationError(
                f"User with email '{value}' does not exist."
            ) from e
        return value

    def validate_level(self, value: int) -> int:
        """Validate permission level is valid."""
        valid_levels = [
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ]
        if value not in valid_levels:
            raise serializers.ValidationError(
                f"Invalid permission level. Must be one of: {valid_levels}"
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> CylinderFleetUserPermission:
        """Create a new permission."""
        # Handle user_email if provided
        if "user_email" in validated_data:
            user_email = validated_data.pop("user_email")
            validated_data["user"] = User.objects.get(email=user_email)

        # Check for existing permission
        existing_perm = CylinderFleetUserPermission.objects.filter(
            user=validated_data["user"],
            cylinder_fleet=validated_data["cylinder_fleet"],
        ).first()

        if existing_perm:
            if existing_perm.is_active:
                raise serializers.ValidationError(
                    {"user": ["User already has an active permission for this fleet."]}
                )
            # Reactivate existing permission
            existing_perm.is_active = True
            existing_perm.level = validated_data.get("level", existing_perm.level)
            existing_perm.deactivated_by = None
            existing_perm.save()
            return existing_perm

        return super().create(validated_data)

    def update(
        self,
        instance: CylinderFleetUserPermission,
        validated_data: dict[str, Any],
    ) -> CylinderFleetUserPermission:
        """Update permission level only."""
        # Only allow updating level
        if "level" in validated_data:
            instance.level = validated_data["level"]
            instance.save()

        return instance


class CylinderInstallSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[CylinderInstall]
):
    """Serializer for CylinderInstall model."""

    sanitized_fields: ClassVar[list[str]] = ["location_name", "notes"]

    # Read-only nested information
    cylinder_id = serializers.UUIDField(source="cylinder.id", read_only=True)
    cylinder_name = serializers.CharField(source="cylinder.name", read_only=True)
    cylinder_serial = serializers.CharField(source="cylinder.serial", read_only=True)
    cylinder_fleet_id = serializers.UUIDField(
        source="cylinder.fleet.id", read_only=True
    )
    cylinder_fleet_name = serializers.CharField(
        source="cylinder.fleet.name", read_only=True
    )
    # Cylinder's unit system (for pressure display)
    cylinder_unit_system = serializers.CharField(
        source="cylinder.unit_system", read_only=True
    )

    # Read-only project information
    project_id = serializers.UUIDField(
        source="project.id", read_only=True, default=None
    )
    project_name = serializers.CharField(
        source="project.name", read_only=True, default=None
    )

    # Cylinder is write-only for creation
    cylinder = serializers.PrimaryKeyRelatedField(
        queryset=Cylinder.objects.all(),
        write_only=True,
        required=True,
    )

    # Project is optional
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )

    # Pressure check count
    pressure_check_count = serializers.SerializerMethodField()
    latest_pressure_check = serializers.SerializerMethodField()

    class Meta:
        model = CylinderInstall
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
        ]

    def get_pressure_check_count(self, obj: CylinderInstall) -> int:
        """Get the number of pressure checks for this install."""
        return obj.pressure_checks.count()

    def get_latest_pressure_check(self, obj: CylinderInstall) -> dict[str, Any] | None:
        """Get the latest pressure check data."""
        check = obj.pressure_checks.order_by("-creation_date").first()
        if check:
            return {
                "id": str(check.id),
                "pressure": check.pressure,
                "unit_system": check.unit_system,
                "user": check.user,
                "creation_date": check.creation_date.isoformat(),
            }
        return None

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate cylinder install data and status transitions."""
        instance = self.instance
        install_status = data.get(
            "status", instance.status if instance else InstallStatus.INSTALLED
        )

        # If updating status to not INSTALLED, require uninstall fields
        if install_status != InstallStatus.INSTALLED:
            uninstall_date = data.get("uninstall_date")
            uninstall_user = data.get("uninstall_user")

            if not uninstall_date:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date is required when marking as uninstalled."
                        )
                    }
                )
            if not uninstall_user:
                raise serializers.ValidationError(
                    {
                        "uninstall_user": (
                            "Uninstall user is required when marking as uninstalled."
                        )
                    }
                )

            # Check install_date <= uninstall_date
            install_date = data.get(
                "install_date", instance.install_date if instance else None
            )
            if install_date and uninstall_date and install_date > uninstall_date:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date must be on or after install date."
                        )
                    }
                )

        # If status is INSTALLED, validate no uninstall fields
        else:
            if "uninstall_date" in data and data["uninstall_date"] is not None:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date can only be set when status is uninstalled."
                        )
                    }
                )
            if "uninstall_user" in data and data["uninstall_user"] is not None:
                raise serializers.ValidationError(
                    {
                        "uninstall_user": (
                            "Uninstall user can only be set when status is uninstalled."
                        )
                    }
                )

        # Validate status transitions
        if instance:
            current_status = instance.status
            # Can only change from INSTALLED to other statuses
            if current_status not in (InstallStatus.INSTALLED, install_status):
                raise serializers.ValidationError(
                    {
                        "status": (
                            f"Cannot change status from {current_status} to "
                            f"{install_status}. Only INSTALLED cylinders can have "
                            "their status changed."
                        )
                    }
                )

        return data

    def create(self, validated_data: dict[str, Any]) -> CylinderInstall:
        """Create a new cylinder install."""
        # Check if cylinder is already installed elsewhere
        cylinder = validated_data["cylinder"]
        existing_install = CylinderInstall.objects.filter(
            cylinder=cylinder, status=InstallStatus.INSTALLED
        ).first()

        if existing_install:
            raise serializers.ValidationError(
                {
                    "cylinder": (
                        f"This cylinder is already installed at "
                        f"'{existing_install.location_name}'. "
                        "A cylinder can only be installed at one location at a time."
                    )
                }
            )

        return super().create(validated_data)

    def update(
        self, instance: CylinderInstall, validated_data: dict[str, Any]
    ) -> CylinderInstall:
        """Update an existing cylinder install."""
        # If cylinder is being changed, check if new cylinder is already installed
        if "cylinder" in validated_data:
            new_cylinder = validated_data["cylinder"]
            # Only check if it's a different cylinder
            if new_cylinder != instance.cylinder:
                existing_install = CylinderInstall.objects.filter(
                    cylinder=new_cylinder, status=InstallStatus.INSTALLED
                ).first()

                if existing_install:
                    raise serializers.ValidationError(
                        {
                            "cylinder": (
                                f"This cylinder is already installed at "
                                f"'{existing_install.location_name}'. "
                                "A cylinder can only be installed at one location "
                                "at a time."
                            )
                        }
                    )

        return super().update(instance, validated_data)


class CylinderInstallGeoJSONSerializer(serializers.ModelSerializer[CylinderInstall]):
    """GeoJSON Serializer for CylinderInstall - returns as GeoJSON Feature."""

    id = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()
    properties = serializers.SerializerMethodField()

    class Meta:
        model = CylinderInstall
        fields = ["id", "type", "geometry", "properties"]

    def get_id(self, obj: CylinderInstall) -> str:
        """Feature ID for Mapbox feature state management."""
        return str(obj.id)

    def get_type(self, _: CylinderInstall) -> str:
        return "Feature"

    def get_geometry(self, obj: CylinderInstall) -> dict[str, Any]:
        return {
            "type": "Point",
            "coordinates": [float(obj.longitude), float(obj.latitude)],
        }

    def get_properties(self, obj: CylinderInstall) -> dict[str, Any]:
        return {
            "id": str(obj.id),
            "cylinder_id": str(obj.cylinder_id),
            "cylinder_name": obj.cylinder.name,
            "cylinder_serial": obj.cylinder.serial,
            "fleet_id": str(obj.cylinder.fleet_id),
            "fleet_name": obj.cylinder.fleet.name,
            "project_id": str(obj.project_id) if obj.project_id else None,
            "project_name": obj.project.name if obj.project else None,
            "location_name": obj.location_name,
            "install_date": obj.install_date.isoformat() if obj.install_date else None,
            "install_user": obj.install_user,
            "distance_from_entry": obj.distance_from_entry,
            "unit_system": obj.unit_system,
            "status": obj.status,
            "o2_percentage": obj.cylinder.o2_percentage,
            "he_percentage": obj.cylinder.he_percentage,
            "pressure": obj.cylinder.pressure,
            "pressure_unit_system": obj.cylinder.unit_system,
        }


class CylinderPressureCheckSerializer(
    serializers.ModelSerializer[CylinderPressureCheck]
):
    """Serializer for CylinderPressureCheck model."""

    # Read-only nested information
    install_id = serializers.UUIDField(source="install.id", read_only=True)
    cylinder_id = serializers.UUIDField(source="install.cylinder.id", read_only=True)
    cylinder_name = serializers.CharField(
        source="install.cylinder.name", read_only=True
    )
    location_name = serializers.CharField(
        source="install.location_name", read_only=True
    )

    # Install is set by the view based on URL parameter, not by client
    install = serializers.PrimaryKeyRelatedField(
        queryset=CylinderInstall.objects.all(),
        write_only=True,
        required=False,  # View sets this from URL param
    )

    class Meta:
        model = CylinderPressureCheck
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
        ]
        # Note: 'user' field is set by the view, but is not read-only
        # because it's stored as a string email, not a FK

    def validate_pressure(self, value: int) -> int:
        """Validate pressure is positive."""
        if value < 0:
            raise serializers.ValidationError("Pressure must be a positive value.")
        return value

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate pressure against unit system limits."""
        unit_system = data.get("unit_system")
        pressure = data.get("pressure")

        if unit_system and pressure:
            if unit_system == UnitSystem.METRIC and pressure > 400:  # noqa: PLR2004
                raise serializers.ValidationError(
                    {"pressure": "Maximum pressure for BAR is 400."}
                )
            if unit_system == UnitSystem.IMPERIAL and pressure > 5000:  # noqa: PLR2004
                raise serializers.ValidationError(
                    {"pressure": "Maximum pressure for PSI is 5000."}
                )

        return data
