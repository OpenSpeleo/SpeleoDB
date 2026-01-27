# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import date
from datetime import timedelta
from pathlib import Path
from typing import Any

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from factory import Faker
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from speleodb.common.enums import InstallStatus
from speleodb.common.enums import OperationalStatus
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import CylinderPressureCheck
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import ExplorationLead
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station
from speleodb.gis.models import StationLogEntry
from speleodb.gis.models import StationResource
from speleodb.gis.models import StationResourceType
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.gis.models import SurfaceStation
from speleodb.gis.models.experiment import FieldType
from speleodb.gis.models.experiment import MandatoryFieldUuid
from speleodb.plugins.models import PluginRelease
from speleodb.plugins.models import PublicAnnoucement
from speleodb.plugins.models.platform_base import OperatingSystemEnum
from speleodb.plugins.models.platform_base import SurveyPlatformEnum
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models import ProjectType
from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import SurveyTeamMembershipRole
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


class SurveyTeamFactory(DjangoModelFactory[SurveyTeam]):
    name: str = Faker("name")  # type: ignore[assignment]
    description: str = factory.LazyAttribute(
        lambda obj: f"Team description for `{obj.name}`"
    )  # type: ignore[assignment]
    # Use lazy generation to avoid accessing django_countries at import time
    country: str = factory.Faker("country_code")  # type: ignore[assignment]

    class Meta:
        model = SurveyTeam


class SurveyTeamMembershipFactory(DjangoModelFactory[SurveyTeamMembership]):
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    team: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    role = random.choice(SurveyTeamMembershipRole.values)

    class Meta:
        model = SurveyTeamMembership


class TokenFactory(DjangoModelFactory[Token]):
    key: str = Faker("password", length=40, special_chars=True, upper_case=True)  # type: ignore[assignment]
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]

    class Meta:
        model = Token


class ProjectFactory(DjangoModelFactory[Project]):
    name = factory.Sequence(lambda n: f"Test Cave {n:04d}")
    description: str = factory.LazyAttribute(
        lambda obj: f"Project description for `{obj.name}`"
    )  # type: ignore[assignment]
    longitude: float = Faker("longitude")  # type: ignore[assignment]
    latitude: float = Faker("latitude")  # type: ignore[assignment]

    # Defer to Faker for a valid ISO country code; avoids empty-iterator races
    country: str = factory.Faker("country_code")  # type: ignore[assignment]

    type: str = factory.Faker(  # type: ignore[assignment]
        "random_element", elements=ProjectType.values
    )

    created_by: str = factory.LazyAttribute(lambda _: UserFactory.create().email)  # type: ignore[assignment]

    class Meta:
        model = Project


class ProjectCommitFactory(DjangoModelFactory[ProjectCommit]):
    """Factory for creating ProjectCommit instances."""

    id: str = factory.LazyFunction(  # type: ignore[assignment]
        lambda: hashlib.sha1(random.randbytes(32), usedforsecurity=False).hexdigest()
    )
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]
    author_name: str = Faker("name")  # type: ignore[assignment]
    author_email: str = Faker("email")  # type: ignore[assignment]
    authored_date: Any = factory.LazyFunction(timezone.now)
    message: str = Faker("sentence")  # type: ignore[assignment]
    tree: list[dict[str, str]] = []

    class Meta:
        model = ProjectCommit


class UserProjectPermissionFactory(DjangoModelFactory[UserProjectPermission]):
    level = PermissionLevel.READ_AND_WRITE
    target: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = UserProjectPermission


class TeamProjectPermissionFactory(DjangoModelFactory[TeamProjectPermission]):
    level = PermissionLevel.READ_AND_WRITE
    target: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = TeamProjectPermission


class PublicAnnoucementFactory(DjangoModelFactory[PublicAnnoucement]):
    """
    Factory for creating PublicAnnoucement instances for testing.
    """

    class Meta:
        model = PublicAnnoucement

    # ---------- Default Values for Required Fields ----------

    title = factory.Sequence(lambda n: f"Announcement {n}")
    header: str = Faker("sentence")  # type: ignore[assignment]
    message: str = Faker("paragraph")  # type: ignore[assignment]

    software = SurveyPlatformEnum.WEB
    version = "1.0.0"
    is_active = True

    # Timestamps — allow override in tests if necessary
    creation_date: Any = factory.LazyFunction(timezone.now)
    modified_date: Any = factory.LazyFunction(timezone.now)
    expiracy_date: Any = None  # Default: no expiration


class PluginReleaseFactory(DjangoModelFactory[PluginRelease]):
    class Meta:
        model = PluginRelease

    # Fields
    plugin_version = "1.0.0"  # Could make this parametric if needed
    software = SurveyPlatformEnum.WEB  # Default enum value
    min_software_version = "1.0.0"
    max_software_version = "2.0.0"
    operating_system = OperatingSystemEnum.ANY

    changelog: str = Faker("paragraph")  # type: ignore[assignment]

    # Generate a random sha256 hash (lowercase hex)
    @factory.lazy_attribute  # type: ignore[arg-type]
    def sha256_hash(self) -> str:
        random_bytes = (
            random.randbytes(32)
            if hasattr(random, "randbytes")
            else bytes(random.getrandbits(8) for _ in range(32))
        )
        return hashlib.sha256(random_bytes).hexdigest()

    download_url: str = Faker("url", schemes="https")  # type: ignore[assignment]

    creation_date = factory.LazyFunction(timezone.now)
    modified_date = factory.LazyFunction(timezone.now)


class ExplorationLeadFactory(DjangoModelFactory[ExplorationLead]):
    """Factory for creating ExplorationLead instances."""

    id = factory.LazyFunction(uuid.uuid4)
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]
    description: str = factory.Faker("text", max_nb_chars=200)  # type: ignore[assignment]
    latitude: float = factory.Faker("latitude")  # type: ignore[assignment]
    longitude: float = factory.Faker("longitude")  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(lambda _: UserFactory.create().email)  # type: ignore[assignment]

    class Meta:
        model = ExplorationLead


class SubSurfaceStationFactory(DjangoModelFactory[SubSurfaceStation]):
    """Factory for creating SubSurfaceStation instances.

    Note: Station is now a polymorphic base class. This factory creates
    SubSurfaceStation instances which have a project field.
    """

    id = factory.LazyFunction(uuid.uuid4)
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]
    name = factory.Sequence(lambda n: f"ST{n:03d}")
    description: str = factory.Faker("text", max_nb_chars=200)  # type: ignore[assignment]
    latitude: float = factory.Faker("latitude")  # type: ignore[assignment]
    longitude: float = factory.Faker("longitude")  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(lambda _: UserFactory.create().email)  # type: ignore[assignment]
    type: str = "sensor"

    class Meta:
        model = SubSurfaceStation

    @classmethod
    def create_with_coordinates(
        cls, lat: float, lng: float, **kwargs: Any
    ) -> SubSurfaceStation:
        """Create a station with specific coordinates."""
        return cls.create(latitude=lat, longitude=lng, **kwargs)

    @classmethod
    def create_demo_stations(
        cls, project: Project, count: int = 3, **kwargs: Any
    ) -> list[SubSurfaceStation]:
        """Create demo stations with realistic cave survey data."""
        demo_data = [
            {
                "name": "Station Alpha",
                "description": "Main data collection point at cave entrance",
                "latitude": 20.194500,
                "longitude": -87.497500,
            },
            {
                "name": "Equipment Station",
                "description": "Data logger and sensor installation point",
                "latitude": 20.196200,
                "longitude": -87.499100,
            },
            {
                "name": "Deep Chamber",
                "description": "Large chamber with multiple passages",
                "latitude": 20.195800,
                "longitude": -87.498600,
            },
        ]

        stations = []
        for i in range(min(count, len(demo_data))):
            data = demo_data[i]
            station = cls.create(
                project=project,
                name=data["name"],
                description=data["description"],
                latitude=data["latitude"],
                longitude=data["longitude"],
                **kwargs,
            )
            stations.append(station)

        return stations


# ================ SURFACE MONITORING NETWORK FACTORIES ================ #


class SurfaceMonitoringNetworkFactory(DjangoModelFactory[SurfaceMonitoringNetwork]):
    """Factory for creating SurfaceMonitoringNetwork instances."""

    class Meta:
        model = SurfaceMonitoringNetwork

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Network {n:03d}")
    description: str = factory.LazyAttribute(
        lambda obj: f"Network description for `{obj.name}`"
    )  # type: ignore[assignment]
    is_active = True
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )


class SurfaceMonitoringNetworkUserPermissionFactory(
    DjangoModelFactory[SurfaceMonitoringNetworkUserPermission]
):
    """Factory for creating SurfaceMonitoringNetworkUserPermission instances."""

    class Meta:
        model = SurfaceMonitoringNetworkUserPermission

    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    network: SurfaceMonitoringNetwork = factory.SubFactory(  # type: ignore[assignment]
        SurfaceMonitoringNetworkFactory
    )
    level = PermissionLevel.READ_AND_WRITE
    is_active = True


class SurfaceStationFactory(DjangoModelFactory[SurfaceStation]):
    """Factory for creating SurfaceStation instances.

    SurfaceStation instances are linked to a SurfaceMonitoringNetwork
    (not a Project like SubSurfaceStation).
    """

    class Meta:
        model = SurfaceStation

    id = factory.LazyFunction(uuid.uuid4)
    network: SurfaceMonitoringNetwork = factory.SubFactory(  # type: ignore[assignment]
        SurfaceMonitoringNetworkFactory
    )
    name = factory.Sequence(lambda n: f"SURF{n:03d}")
    description: str = factory.Faker("text", max_nb_chars=200)  # type: ignore[assignment]
    latitude: float = factory.Faker("latitude")  # type: ignore[assignment]
    longitude: float = factory.Faker("longitude")  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )

    @classmethod
    def create_with_coordinates(
        cls, lat: float, lng: float, **kwargs: Any
    ) -> SurfaceStation:
        """Create a surface station with specific coordinates."""
        return cls.create(latitude=lat, longitude=lng, **kwargs)


class StationResourceFactory(DjangoModelFactory[StationResource]):
    """Factory for creating StationResource instances."""

    class Meta:
        model = StationResource
        skip_postgeneration_save = True  # Add this to avoid deprecation warning

    id = factory.LazyFunction(uuid.uuid4)
    station: SubSurfaceStation = factory.SubFactory(SubSurfaceStationFactory)  # type: ignore[assignment]
    resource_type: StationResourceType = factory.Faker(
        "random_element",
        elements=[
            StationResourceType.PHOTO,
            StationResourceType.VIDEO,
            StationResourceType.NOTE,
            StationResourceType.DOCUMENT,
        ],
    )  # type: ignore[assignment]

    title: str = factory.Faker("sentence", nb_words=4)  # type: ignore[assignment]
    description: str = factory.Faker("text", max_nb_chars=300)  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(lambda _: UserFactory.create().email)  # type: ignore[assignment]

    text_content: str = ""

    @factory.post_generation
    def with_content(self, create: bool, extracted: Any, **kwargs: Any) -> None:
        """Add appropriate content based on resource type."""
        if not create:
            return

        if self.resource_type == StationResourceType.NOTE:
            if not self.text_content:
                self.text_content = f"Note content for {self.title}"

    @classmethod
    def _create(
        cls, model_class: type[StationResource], *args: Any, **kwargs: Any
    ) -> StationResource:
        """Override create to handle file-based resources properly."""
        # For file-based resources without a file, provide a test file
        resource_type = kwargs.get(
            "resource_type", cls._meta.declarations.get("resource_type")
        )
        if hasattr(resource_type, "fget"):
            # It's still a factory declaration, get a value
            resource_type = resource_type.fget()  # type: ignore[union-attr]

        if resource_type in [
            StationResourceType.PHOTO,
            StationResourceType.VIDEO,
            StationResourceType.DOCUMENT,
        ]:
            if "file" not in kwargs or not kwargs.get("file"):
                # Provide appropriate test file
                artifacts_dir = Path(__file__).parent / "artifacts"

                if resource_type == StationResourceType.PHOTO:
                    with (artifacts_dir / "image.jpg").open(mode="rb") as f:
                        kwargs["file"] = SimpleUploadedFile(
                            "test_image.jpg", f.read(), content_type="image/jpeg"
                        )
                elif resource_type == StationResourceType.VIDEO:
                    with (artifacts_dir / "video.mp4").open(mode="rb") as f:
                        kwargs["file"] = SimpleUploadedFile(
                            "test_video.mp4", f.read(), content_type="video/mp4"
                        )
                elif resource_type == StationResourceType.DOCUMENT:
                    with (artifacts_dir / "document.pdf").open(mode="rb") as f:
                        kwargs["file"] = SimpleUploadedFile(
                            "test_document.pdf",
                            f.read(),
                            content_type="application/pdf",
                        )

        return super()._create(model_class, *args, **kwargs)

    @classmethod
    def create_photo(cls, station: Station, **kwargs: Any) -> StationResource:
        """Create a photo resource."""
        return cls.create(
            station=station,
            resource_type=StationResourceType.PHOTO,
            title="Station Overview Photo",
            description="Wide angle shot of the station location",
            **kwargs,
        )

    @classmethod
    def create_note(cls, station: Station, **kwargs: Any) -> StationResource:
        """Create a note resource with realistic cave survey content."""
        content = """Water depth: 1.2m
Flow rate: ~0.5 m/s
Temperature: 23°C
Visibility: Excellent (>30m)
Ceiling height: 4.5m

Notes: Strong current from nearby survey line. Recommend safety line for divers.
Station positioned at junction of main passage and side chamber.
Good visibility in all directions."""

        return cls.create(
            station=station,
            resource_type=StationResourceType.NOTE,
            title="Survey Measurements",
            description="Water flow and depth readings",
            text_content=content,
            **kwargs,
        )

    @classmethod
    def create_video(cls, station: Station, **kwargs: Any) -> StationResource:
        """Create a video resource."""
        return cls.create(
            station=station,
            resource_type=StationResourceType.VIDEO,
            title="360° Site Survey",
            description="Complete view of the station location",
            **kwargs,
        )

    @classmethod
    def create_demo_resources(cls, station: Station) -> list[StationResource]:
        """Create a complete set of demo resources for a station."""
        return [
            cls.create_photo(station),
            cls.create_note(station),
            cls.create_video(station),
        ]


class PhotoStationResourceFactory(StationResourceFactory):
    """Factory specifically for photo station resources."""

    resource_type = StationResourceType.PHOTO
    title: str = factory.LazyAttribute(lambda obj: f"Photo - {obj.station.name}")  # type: ignore[assignment]


class VideoStationResourceFactory(StationResourceFactory):
    """Factory specifically for video station resources."""

    resource_type = StationResourceType.VIDEO
    title: str = factory.LazyAttribute(lambda obj: f"Video - {obj.station.name}")  # type: ignore[assignment]


class NoteStationResourceFactory(StationResourceFactory):
    """Factory specifically for note station resources."""

    resource_type = StationResourceType.NOTE
    title: str = factory.LazyAttribute(lambda obj: f"Notes - {obj.station.name}")  # type: ignore[assignment]
    text_content: str = Faker("paragraph")  # type: ignore[assignment]


class DocumentStationResourceFactory(StationResourceFactory):
    """Factory specifically for document station resources."""

    resource_type = StationResourceType.DOCUMENT
    title: str = factory.LazyAttribute(lambda obj: f"Document - {obj.station.name}")  # type: ignore[assignment]


class StationLogEntryFactory(DjangoModelFactory[StationLogEntry]):
    """Factory for creating StationLogEntry instances."""

    class Meta:
        model = StationLogEntry
        skip_postgeneration_save = True  # Add this to avoid deprecation warning

    id = factory.LazyFunction(uuid.uuid4)
    station: SubSurfaceStation = factory.SubFactory(SubSurfaceStationFactory)  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(lambda _: UserFactory.create().email)  # type: ignore[assignment]

    title: str = factory.Faker("sentence", nb_words=4)  # type: ignore[assignment]
    notes: str = factory.Faker("text", max_nb_chars=300)  # type: ignore[assignment]
    # text_content: str = ""


class ExperimentFactory(DjangoModelFactory[Experiment]):
    """Factory for creating Experiment instances."""

    class Meta:
        model = Experiment

    name: str = Faker("sentence", nb_words=3)  # type: ignore[assignment]
    code: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda obj: f"EXP-{random.randint(1000, 9999)}"
    )
    description: str = Faker("text", max_nb_chars=200)  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )
    experiment_fields: dict[str, Any] = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: {
            **MandatoryFieldUuid.get_mandatory_fields(),
            Experiment.generate_field_uuid(): {
                "name": "Ph Level",
                "type": FieldType.NUMBER.value,
                "required": False,
                "order": 2,
            },
        }
    )


class UserExperimentPermissionFactory(DjangoModelFactory[ExperimentUserPermission]):
    level = PermissionLevel.READ_AND_WRITE
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    experiment: Experiment = factory.SubFactory(ExperimentFactory)  # type: ignore[assignment]

    class Meta:
        model = ExperimentUserPermission


# ================ SENSOR FLEET FACTORIES ================ #


class SensorFleetFactory(DjangoModelFactory[SensorFleet]):
    """Factory for creating SensorFleet instances."""

    class Meta:
        model = SensorFleet

    name: str = factory.Sequence(lambda n: f"Fleet {n:03d}")  # type: ignore[assignment]
    description: str = factory.Faker(  # type: ignore[assignment]
        "text", max_nb_chars=200
    )
    is_active = True
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )


class SensorFactory(DjangoModelFactory[Sensor]):
    """Factory for creating Sensor instances."""

    class Meta:
        model = Sensor

    name: str = factory.Sequence(lambda n: f"Sensor {n:03d}")  # type: ignore[assignment]
    notes: str = factory.Faker("text", max_nb_chars=100)  # type: ignore[assignment]
    status = OperationalStatus.FUNCTIONAL
    fleet: SensorFleet = factory.SubFactory(SensorFleetFactory)  # type: ignore[assignment]
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )


class SensorFleetUserPermissionFactory(DjangoModelFactory[SensorFleetUserPermission]):
    """Factory for creating SensorFleetUserPermission instances."""

    class Meta:
        model = SensorFleetUserPermission

    level = PermissionLevel.READ_AND_WRITE
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    sensor_fleet: SensorFleet = factory.SubFactory(SensorFleetFactory)  # type: ignore[assignment]


class SensorInstallFactory(DjangoModelFactory[SensorInstall]):
    """Factory for creating SensorInstall instances."""

    class Meta:
        model = SensorInstall

    sensor: Sensor = factory.SubFactory(SensorFactory)  # type: ignore[assignment]
    station: SubSurfaceStation = factory.SubFactory(SubSurfaceStationFactory)  # type: ignore[assignment]
    install_date = factory.LazyFunction(timezone.localdate)
    install_user: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )
    status = InstallStatus.INSTALLED
    uninstall_date: date | None = None
    uninstall_user: str | None = None
    expiracy_memory_date: date | None = None
    expiracy_battery_date: date | None = None
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )

    @classmethod
    def create_uninstalled(
        cls,
        sensor: Sensor | None = None,
        station: Station | None = None,
        status: InstallStatus = InstallStatus.RETRIEVED,
        **kwargs: Any,
    ) -> SensorInstall:
        """Create a retrieved sensor install."""

        assert status != InstallStatus.INSTALLED, (
            "Status must not be INSTALLED for uninstalled installs."
        )

        if sensor is None:
            sensor = SensorFactory.create()
        if station is None:
            station = SubSurfaceStationFactory.create()

        install_date = kwargs.get("install_date", timezone.localdate())
        uninstall_date = kwargs.get("uninstall_date", install_date + timedelta(days=30))

        return cls.create(
            sensor=sensor,
            station=station,
            status=status,
            install_date=install_date,
            uninstall_date=uninstall_date,
            uninstall_user=kwargs.get("uninstall_user", UserFactory.create().email),
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["install_date", "uninstall_date", "uninstall_user"]
            },
        )

    @classmethod
    def create_lost(
        cls, sensor: Sensor | None = None, station: Station | None = None, **kwargs: Any
    ) -> SensorInstall:
        """Create a lost sensor install."""
        if sensor is None:
            sensor = SensorFactory.create()
        if station is None:
            station = SubSurfaceStationFactory.create()

        return cls.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.LOST,
            **kwargs,
        )

    @classmethod
    def create_abandoned(
        cls, sensor: Sensor | None = None, station: Station | None = None, **kwargs: Any
    ) -> SensorInstall:
        """Create an abandoned sensor install."""
        if sensor is None:
            sensor = SensorFactory.create()
        if station is None:
            station = SubSurfaceStationFactory.create()

        return cls.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.ABANDONED,
            **kwargs,
        )


# ================ CYLINDER FLEET FACTORIES ================ #


class CylinderFleetFactory(DjangoModelFactory[CylinderFleet]):
    """Factory for creating CylinderFleet instances."""

    class Meta:
        model = CylinderFleet

    name: str = factory.Sequence(lambda n: f"Cylinder Fleet {n:03d}")  # type: ignore[assignment]
    description: str = factory.Faker(  # type: ignore[assignment]
        "text", max_nb_chars=200
    )
    is_active = True
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )


class CylinderFactory(DjangoModelFactory[Cylinder]):
    """Factory for creating Cylinder instances."""

    class Meta:
        model = Cylinder

    name: str = factory.Sequence(lambda n: f"Cylinder {n:03d}")  # type: ignore[assignment]
    serial: str = factory.Sequence(lambda n: f"SN-{n:05d}")  # type: ignore[assignment]
    brand: str = factory.Faker("company")  # type: ignore[assignment]
    owner: str = factory.Faker("name")  # type: ignore[assignment]
    notes: str = factory.Faker("text", max_nb_chars=100)  # type: ignore[assignment]
    type: str = factory.Faker("word")  # type: ignore[assignment]
    o2_percentage = 21
    he_percentage = 0
    pressure = 3000
    unit_system = UnitSystem.IMPERIAL
    fleet: CylinderFleet = factory.SubFactory(CylinderFleetFactory)  # type: ignore[assignment]
    status = OperationalStatus.FUNCTIONAL
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )


class CylinderFleetUserPermissionFactory(
    DjangoModelFactory[CylinderFleetUserPermission]
):
    """Factory for creating CylinderFleetUserPermission instances."""

    class Meta:
        model = CylinderFleetUserPermission

    level = PermissionLevel.READ_AND_WRITE
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    cylinder_fleet: CylinderFleet = factory.SubFactory(CylinderFleetFactory)  # type: ignore[assignment]


class CylinderInstallFactory(DjangoModelFactory[CylinderInstall]):
    """Factory for creating CylinderInstall instances."""

    class Meta:
        model = CylinderInstall

    cylinder: Cylinder = factory.SubFactory(CylinderFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]
    location_name: str = factory.Faker("city")  # type: ignore[assignment]
    latitude: float = factory.Faker("latitude")  # type: ignore[assignment]
    longitude: float = factory.Faker("longitude")  # type: ignore[assignment]
    install_date = factory.LazyFunction(timezone.localdate)
    install_user: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )
    status = InstallStatus.INSTALLED
    uninstall_date: date | None = None
    uninstall_user: str | None = None
    created_by: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )

    @classmethod
    def create_uninstalled(
        cls,
        cylinder: Cylinder | None = None,
        install_status: InstallStatus = InstallStatus.RETRIEVED,
        **kwargs: Any,
    ) -> CylinderInstall:
        """Create a retrieved cylinder install."""

        assert install_status != InstallStatus.INSTALLED, (
            "Status must not be INSTALLED for uninstalled installs."
        )

        if cylinder is None:
            cylinder = CylinderFactory.create()

        install_date = kwargs.get("install_date", timezone.localdate())
        uninstall_date = kwargs.get("uninstall_date", install_date + timedelta(days=30))

        return cls.create(
            cylinder=cylinder,
            status=install_status,
            install_date=install_date,
            uninstall_date=uninstall_date,
            uninstall_user=kwargs.get("uninstall_user", UserFactory.create().email),
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["install_date", "uninstall_date", "uninstall_user"]
            },
        )


class CylinderPressureCheckFactory(DjangoModelFactory[CylinderPressureCheck]):
    """Factory for creating CylinderPressureCheck instances."""

    class Meta:
        model = CylinderPressureCheck

    install: CylinderInstall = factory.SubFactory(CylinderInstallFactory)  # type: ignore[assignment]
    user: str = factory.LazyAttribute(  # type: ignore[assignment]
        lambda _: UserFactory.create().email
    )
    notes: str = factory.Faker("text", max_nb_chars=100)  # type: ignore[assignment]
    pressure: int = factory.Faker("random_int", min=1000, max=3000)  # type: ignore[assignment]
    unit_system = UnitSystem.IMPERIAL
    check_date: date = factory.Faker("date_object")  # type: ignore[assignment]
