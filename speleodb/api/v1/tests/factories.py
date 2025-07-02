# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import random
import uuid
from typing import TYPE_CHECKING
from typing import Any

import factory
from django.utils import timezone
from django_countries import countries
from factory import Faker
from factory import post_generation
from factory.django import DjangoModelFactory
from rest_framework.authtoken.models import Token

from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import PluginRelease
from speleodb.surveys.models import Project
from speleodb.surveys.models import PublicAnnoucement
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.surveys.models.platform_base import OperatingSystemEnum
from speleodb.surveys.models.platform_base import SurveyPlatformEnum
from speleodb.surveys.models.station import Station
from speleodb.surveys.models.station import StationResource
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User

if TYPE_CHECKING:
    from factory.base import StubObject


class UserFactory(DjangoModelFactory[User]):
    email: str = Faker("email")  # type: ignore[assignment]
    name: str = Faker("name")  # type: ignore[assignment]
    country: str = random.choice(countries).code  # pyright: ignore[reportAttributeAccessIssue]

    class Meta:
        model = User

    @post_generation
    def password(self, *args: Any, **kwargs: Any) -> None:
        self.set_password(UserFactory.DEFAULT_PASSWORD())  # type: ignore[attr-defined]

    @classmethod
    def _after_postgeneration(
        cls,
        instance: User | StubObject,
        create: bool,
        results: dict[str, Any] | None = None,
    ) -> None:
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:  # type: ignore[attr-defined]
            # Some post-generation hooks ran, and may have modified us.
            instance.save()  # type: ignore[union-attr]

    @classmethod
    def DEFAULT_PASSWORD(cls) -> str:  # noqa: N802
        return "password"


class SurveyTeamFactory(DjangoModelFactory[SurveyTeam]):
    name: str = Faker("name")  # type: ignore[assignment]
    description: str = factory.LazyAttribute(
        lambda obj: f"Team description for `{obj.name}`"
    )  # type: ignore[assignment]
    country = random.choice(countries)[0]

    class Meta:
        model = SurveyTeam


class SurveyTeamMembershipFactory(DjangoModelFactory[SurveyTeamMembership]):
    user: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    team: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    role = random.choice(SurveyTeamMembership.Role.values)

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

    country = random.choice(countries).code  # pyright: ignore[reportAttributeAccessIssue]

    created_by: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]

    class Meta:
        model = Project


class UserPermissionFactory(DjangoModelFactory[UserPermission]):
    level = PermissionLevel.READ_AND_WRITE
    target: User = factory.SubFactory(UserFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = UserPermission


class TeamPermissionFactory(DjangoModelFactory[TeamPermission]):
    level = PermissionLevel.READ_AND_WRITE
    target: SurveyTeam = factory.SubFactory(SurveyTeamFactory)  # type: ignore[assignment]
    project: Project = factory.SubFactory(ProjectFactory)  # type: ignore[assignment]

    class Meta:
        model = TeamPermission


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


class StationFactory(DjangoModelFactory):
    """Factory for creating Station instances."""

    class Meta:
        model = Station

    id = factory.LazyFunction(uuid.uuid4)
    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"ST{n:03d}")
    description = factory.Faker("text", max_nb_chars=200)
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")
    created_by = factory.SubFactory(UserFactory)

    @classmethod
    def create_with_coordinates(cls, lat: float, lng: float, **kwargs):
        """Create a station with specific coordinates."""
        return cls.create(latitude=lat, longitude=lng, **kwargs)

    @classmethod
    def create_demo_stations(cls, project, count: int = 3, **kwargs):
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


class StationResourceFactory(DjangoModelFactory):
    """Factory for creating StationResource instances."""

    class Meta:
        model = StationResource
        skip_postgeneration_save = True  # Add this to avoid deprecation warning

    id = factory.LazyFunction(uuid.uuid4)
    station = factory.SubFactory(StationFactory)
    resource_type = factory.Faker(
        "random_element",
        elements=[
            StationResource.ResourceType.PHOTO,
            StationResource.ResourceType.VIDEO,
            StationResource.ResourceType.NOTE,
            StationResource.ResourceType.SKETCH,
            StationResource.ResourceType.DOCUMENT,
        ],
    )
    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("text", max_nb_chars=300)
    created_by = factory.SubFactory(UserFactory)

    @factory.post_generation
    def with_content(self, create, extracted, **kwargs):
        """Add appropriate content based on resource type."""
        if not create:
            return

        if self.resource_type == StationResource.ResourceType.NOTE:
            # Only set text_content if it's not already set
            if not self.text_content:
                # Use faker directly without instantiation
                from faker import Faker as FakerLib

                fake = FakerLib()
                self.text_content = fake.text(max_nb_chars=1000)
        elif self.resource_type == StationResource.ResourceType.SKETCH:
            # Only set text_content if it's not already set
            if not self.text_content:
                # Simple SVG sketch
                self.text_content = """<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
                    <rect width="300" height="200" fill="#1e293b"/>
                    <path d="M50 100 L250 100 M150 50 L150 150" stroke="#38bdf8" stroke-width="3" fill="none"/>
                    <circle cx="150" cy="100" r="8" fill="#f59e0b"/>
                    <text x="160" y="105" fill="#e2e8f0" font-size="12">Station</text>
                </svg>"""

    @classmethod
    def create_photo(cls, station, **kwargs):
        """Create a photo resource."""
        return cls.create(
            station=station,
            resource_type=StationResource.ResourceType.PHOTO,
            title="Station Overview Photo",
            description="Wide angle shot of the station location",
            **kwargs,
        )

    @classmethod
    def create_note(cls, station, **kwargs):
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
            resource_type=StationResource.ResourceType.NOTE,
            title="Survey Measurements",
            description="Water flow and depth readings",
            text_content=content,
            **kwargs,
        )

    @classmethod
    def create_sketch(cls, station, **kwargs):
        """Create a sketch resource."""
        return cls.create(
            station=station,
            resource_type=StationResource.ResourceType.SKETCH,
            title="Cross-section Diagram",
            description="Hand-drawn cross-section of the area",
            **kwargs,
        )

    @classmethod
    def create_video(cls, station, **kwargs):
        """Create a video resource."""
        return cls.create(
            station=station,
            resource_type=StationResource.ResourceType.VIDEO,
            title="360° Site Survey",
            description="Complete view of the station location",
            **kwargs,
        )

    @classmethod
    def create_demo_resources(cls, station):
        """Create a complete set of demo resources for a station."""
        resources = [
            cls.create_photo(station),
            cls.create_note(station),
            cls.create_sketch(station),
            cls.create_video(station),
        ]
        return resources


class PhotoStationResourceFactory(StationResourceFactory):
    """Factory specifically for photo station resources."""

    resource_type = StationResource.ResourceType.PHOTO
    title = factory.LazyAttribute(lambda obj: f"Photo - {obj.station.name}")
    text_content = ""


class VideoStationResourceFactory(StationResourceFactory):
    """Factory specifically for video station resources."""

    resource_type = StationResource.ResourceType.VIDEO
    title = factory.LazyAttribute(lambda obj: f"Video - {obj.station.name}")
    text_content = ""


class SketchStationResourceFactory(StationResourceFactory):
    """Factory specifically for sketch station resources."""

    resource_type = StationResource.ResourceType.SKETCH
    title = factory.LazyAttribute(lambda obj: f"Sketch - {obj.station.name}")
    text_content = '<svg width="200" height="200"><circle cx="100" cy="100" r="50" fill="blue"/><text x="100" y="100" text-anchor="middle" fill="white">Cave</text></svg>'


class NoteStationResourceFactory(StationResourceFactory):
    """Factory specifically for note station resources."""

    resource_type = StationResource.ResourceType.NOTE
    title = factory.LazyAttribute(lambda obj: f"Notes - {obj.station.name}")
    text_content = Faker("paragraph")  # type: ignore[assignment]


class DocumentStationResourceFactory(StationResourceFactory):
    """Factory specifically for document station resources."""

    resource_type = StationResource.ResourceType.DOCUMENT
    title = factory.LazyAttribute(lambda obj: f"Document - {obj.station.name}")
    text_content = ""
