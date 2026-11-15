"""Native shot import preserves user edits, deletions and project ownership."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone

from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.common.enums import ProjectType
from speleodb.gis.models import ExplorationLead
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models.project import ResolvedSurveyShot

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        (None, []),
        ("!ZAW! !399! !360! !-1! !1.5!", []),
        ("!nne! !E! !nnw!", [22.5, 90, 337.5]),
        ("!N! !0! !000! !90! !E! !S! !W!", [0, 90, 180]),
        ("!ZAW! !399! !NE!", [45]),
        ("!000359! !\uff11\uff10\uff10! !359.0! !+359! !360!", [359]),
        ("Great! Direction: !ne!", [45]),
        ("!!n!", [0]),
        ("!" + "9" * 5000 + "! !W!", [270]),
    ],
)
def test_marker_parsing(comment: str | None, expected: list[float]) -> None:
    assert Project.exploration_headings(comment) == expected


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("n", 0),
        ("nne", 22.5),
        ("ne", 45),
        ("ene", 67.5),
        ("e", 90),
        ("ese", 112.5),
        ("se", 135),
        ("sse", 157.5),
        ("s", 180),
        ("ssw", 202.5),
        ("sw", 225),
        ("wsw", 247.5),
        ("w", 270),
        ("wnw", 292.5),
        ("nw", 315),
        ("nnw", 337.5),
    ],
)
def test_lowercase_cardinal_directions(direction: str, expected: float) -> None:
    assert Project.exploration_headings(f"Passage !{direction}!") == [expected]


def source_shot(**changes: Any) -> ResolvedSurveyShot:
    return replace(
        ResolvedSurveyShot(
            uuid=None,
            shot_id="2",
            from_id="1",
            namespace=(),
            length_m=10,
            azimuth=45,
            comment="Full comment\n!N! !E! !22! !399! !S!",
            longitude=-87,
            latitude=20,
        ),
        **changes,
    )


@pytest.fixture
def source_commit(project: Project) -> ProjectCommit:
    project.type = ProjectType.ARIANE
    project.save(update_fields=["type"])
    return ProjectCommit.objects.create(
        id="a" * 40,
        project=project,
        author_name="Surveyor",
        author_email="surveyor@example.test",
        authored_date=timezone.now(),
        message="Source",
    )


@pytest.mark.django_db
def test_import_preserves_existing_lead_and_retains_new_signatures(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    shot = source_shot(uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(source_commit, [shot])
    lead = project.exploration_leads.get()
    assert lead.description == shot.comment
    assert lead.headings == [0, 90, 22]
    assert lead.created_by == source_commit.author_email
    lead.description = "User description"
    lead.headings = [337.5]
    lead.save()
    saved_values = project.exploration_leads.values().get(pk=lead.pk)
    moved = replace(shot, uuid=str(uuid.uuid4()), longitude=-86, comment="no markers")
    project.sync_exploration_leads(source_commit, [moved])
    lead.refresh_from_db()
    assert project.exploration_leads.values().get(pk=lead.pk) == saved_values
    # The learned UUID bridges a later change of all non-UUID signatures.
    project.sync_exploration_leads(
        source_commit, [replace(moved, shot_id="3", from_id="9", length_m=4)]
    )
    assert project.exploration_leads.count() == 1
    assert project.exploration_leads.values().get(pk=lead.pk) == saved_values


@pytest.mark.django_db
def test_deletion_survives_regeneration_and_later_signatures(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    shot = source_shot(uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(source_commit, [shot])
    project.exploration_leads.get().delete()
    changed = replace(shot, uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(source_commit, [changed])
    project.sync_exploration_leads(
        source_commit, [replace(changed, shot_id="5", from_id="4")]
    )
    assert not project.exploration_leads.exists()
    assert project.exploration_lead_sources.filter(lead__isnull=True).exists()


@pytest.mark.django_db
def test_all_matching_is_restricted_to_project(source_commit: ProjectCommit) -> None:
    shot = source_shot(uuid=str(uuid.uuid4()))
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [shot])
    other = ProjectFactory.create(type=ProjectType.ARIANE)
    other_commit = ProjectCommit.objects.create(
        id="b" * 40,
        project=other,
        author_name="Other",
        author_email="other@example.test",
        authored_date=timezone.now(),
        message="Other source",
    )
    other.sync_exploration_leads(other_commit, [replace(shot, longitude=-85)])
    assert other.exploration_leads.get().coordinates == (-85, 20)
    assert project.exploration_leads.get().coordinates == (-87, 20)
    project.exploration_leads.get().delete()
    other.sync_exploration_leads(other_commit, [replace(shot, longitude=-84)])
    assert other.exploration_leads.get().coordinates == (-85, 20)


@pytest.mark.django_db
def test_uuid_matches_without_namespace_and_compass_endpoints_are_namespaced(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    project.type = ProjectType.COMPASS
    project.save(update_fields=["type"])
    shot = source_shot(namespace=("first.dat", "First"))
    project.sync_exploration_leads(source_commit, [shot])
    original = project.exploration_leads.get()
    project.sync_exploration_leads(
        source_commit, [replace(shot, namespace=("second.dat", "Second"))]
    )
    expected_lead_count = 2
    assert project.exploration_leads.count() == expected_lead_count
    identified = replace(shot, uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(source_commit, [identified])
    renamed = replace(identified, namespace=("renamed.dat", "Renamed"), longitude=-85)
    project.sync_exploration_leads(source_commit, [renamed])
    assert project.exploration_leads.count() == expected_lead_count
    for kind, digest, _ in project._lead_signatures(renamed):  # noqa: SLF001
        assert project.exploration_lead_sources.get(
            kind=kind, digest=digest
        ).lead_id == (original.pk)


@pytest.mark.django_db
def test_no_uuid_measurement_signature_bridges_changed_parent(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    lead = project.exploration_leads.get()
    modified_date = lead.modified_date
    project.sync_exploration_leads(source_commit, [source_shot(from_id="8")])
    lead.refresh_from_db()
    assert lead.modified_date == modified_date
    assert project.exploration_leads.count() == 1
    # Learned origin identity survives a subsequent measurement correction.
    project.sync_exploration_leads(
        source_commit, [source_shot(from_id="8", length_m=12, longitude=-86)]
    )
    lead.refresh_from_db()
    assert lead.coordinates == (-87, 20)
    assert lead.modified_date == modified_date
    assert project.exploration_leads.count() == 1


@pytest.mark.django_db
def test_native_uuid_normalization_survives_format_and_namespace_changes(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    native_uuid = uuid.uuid4()
    shot = source_shot(uuid="{" + str(native_uuid).upper() + "}")
    project.sync_exploration_leads(source_commit, [shot])
    original = project.exploration_leads.get()
    original.description = "Description maintained in the map"
    original.headings = []
    original.save()

    project.type = ProjectType.STALAGMIGHT
    project.save(update_fields=["type"])
    project.sync_exploration_leads(
        source_commit,
        [
            replace(
                shot,
                uuid=native_uuid.hex,
                namespace=("Changed source",),
                shot_id="20",
                from_id="19",
                length_m=10.01,
                azimuth=45.01,
                longitude=-86,
                comment="Revised survey comment !S!",
            )
        ],
    )
    original.refresh_from_db()
    assert project.exploration_leads.get().pk == original.pk
    assert original.coordinates == (-87, 20)
    assert original.description == "Description maintained in the map"
    assert original.headings == []


@pytest.mark.django_db
@pytest.mark.parametrize("azimuth", [405.0, -315.0])
def test_equivalent_measurements_match_after_reparenting(
    source_commit: ProjectCommit, azimuth: float
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    original = project.exploration_leads.get()
    project.sync_exploration_leads(
        source_commit,
        [source_shot(from_id="8", length_m=10.0, azimuth=azimuth, longitude=-86)],
    )
    original.refresh_from_db()
    assert project.exploration_leads.get().pk == original.pk
    assert original.coordinates == (-87, 20)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("length", "azimuth"),
    [(None, 45), (10, None), (float("nan"), 45), (10, float("inf"))],
)
def test_endpoint_identity_survives_unavailable_measurements(
    source_commit: ProjectCommit, length: float | None, azimuth: float | None
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    original = project.exploration_leads.get()
    original.description = "Keep this user description"
    original.headings = [123]
    original.save()
    project.sync_exploration_leads(
        source_commit,
        [
            source_shot(
                length_m=length,
                azimuth=azimuth,
                comment="Changed source !S!",
                longitude=-86,
            )
        ],
    )
    original.refresh_from_db()
    assert project.exploration_leads.get().pk == original.pk
    assert original.coordinates == (-87, 20)
    assert original.description == "Keep this user description"
    assert original.headings == [123]


@pytest.mark.django_db
@pytest.mark.parametrize(("length", "azimuth"), [(10.001, 45), (10, 45.001)])
def test_reparenting_and_measurement_changes_have_no_fuzzy_match(
    source_commit: ProjectCommit, length: float, azimuth: float
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    original = project.exploration_leads.get()
    project.sync_exploration_leads(
        source_commit,
        [source_shot(from_id="8", length_m=length, azimuth=azimuth)],
    )
    # Without a UUID, changing both the endpoint pair and measurement removes
    # every shared signature. Identical coordinates cannot establish identity.
    assert project.exploration_leads.exclude(pk=original.pk).count() == 1
    original.refresh_from_db()
    assert original.coordinates == (-87, 20)


@pytest.mark.django_db
def test_manual_lead_at_same_location_is_not_claimed_or_overwritten(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    manual = ExplorationLead.objects.create(
        project=project,
        longitude=-87,
        latitude=20,
        description="Manually entered observation",
        headings=[123],
        created_by="manual@example.test",
    )
    modified_date = manual.modified_date
    project.sync_exploration_leads(source_commit, [source_shot()])
    imported = project.exploration_leads.exclude(pk=manual.pk).get()
    project.sync_exploration_leads(source_commit, [source_shot(longitude=-86)])
    manual.refresh_from_db()
    imported.refresh_from_db()
    assert manual.coordinates == (-87, 20)
    assert manual.description == "Manually entered observation"
    assert manual.headings == [123]
    assert manual.modified_date == modified_date
    assert not manual.sources.exists()
    assert imported.coordinates == (-87, 20)
    assert imported.sources.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("comment", [None, "!ZAW! !399! !down!"])
def test_unannotated_source_does_not_prevent_later_import(
    source_commit: ProjectCommit, comment: str | None
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot(comment=comment)])
    assert not project.exploration_leads.exists()
    assert not project.exploration_lead_sources.exists()
    project.sync_exploration_leads(
        source_commit, [source_shot(comment="decorate black, stag, !s! !down!")]
    )
    lead = project.exploration_leads.get()
    assert lead.description == "decorate black, stag, !s! !down!"
    assert lead.headings == [180]
    project.sync_exploration_leads(source_commit, [])
    project.sync_exploration_leads(source_commit, [source_shot(comment=comment)])
    lead.refresh_from_db()
    assert project.exploration_leads.get().pk == lead.pk
    assert lead.description == "decorate black, stag, !s! !down!"
    assert lead.headings == [180]


@pytest.mark.django_db
def test_historical_commit_cannot_import_leads_or_learn_aliases(
    source_commit: ProjectCommit,
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    sources = list(project.exploration_lead_sources.order_by("pk").values())
    project = Project.objects.prefetch_related("commits").get(pk=project.pk)
    ProjectCommit.objects.create(
        id="b" * 40,
        project=project,
        author_name="Surveyor",
        author_email="surveyor@example.test",
        authored_date=timezone.now() + timedelta(seconds=1),
        message="Latest source",
    )
    project.sync_exploration_leads(
        source_commit,
        [source_shot(uuid=str(uuid.uuid4()), longitude=-86), source_shot(shot_id="9")],
    )
    assert project.exploration_leads.count() == 1
    assert project.exploration_leads.get().coordinates == (-87, 20)
    assert list(project.exploration_lead_sources.order_by("pk").values()) == sources


@pytest.mark.django_db
def test_signature_priority_and_deleted_match(source_commit: ProjectCommit) -> None:
    project = source_commit.project
    first = source_shot(uuid=str(uuid.uuid4()))
    second = source_shot(uuid=str(uuid.uuid4()), shot_id="8", from_id="7")
    project.sync_exploration_leads(source_commit, [first, second])
    first_lead = project.exploration_leads.get(
        sources__kind=1, sources__payload=first.uuid
    )
    second_lead = project.exploration_leads.get(
        sources__kind=1, sources__payload=second.uuid
    )
    sources = list(project.exploration_lead_sources.values_list("pk", flat=True))
    mixed = replace(second, uuid=first.uuid, length_m=11, longitude=-86)
    project.sync_exploration_leads(source_commit, [mixed])
    first_lead.refresh_from_db()
    second_lead.refresh_from_db()
    assert first_lead.coordinates == (-87, 20)
    assert second_lead.coordinates == (-87, 20)
    learned = project.exploration_lead_sources.exclude(pk__in=sources).get()
    assert learned.lead_id == first_lead.pk
    second_lead.delete()
    project.sync_exploration_leads(
        source_commit, [replace(mixed, length_m=12, longitude=-85)]
    )
    first_lead.refresh_from_db()
    assert first_lead.coordinates == (-87, 20)
    tombstone = project.exploration_lead_sources.exclude(
        pk__in=[*sources, learned.pk]
    ).get()
    assert tombstone.lead_id is None


@pytest.mark.django_db
def test_equal_priority_conflicting_destinations_skip(
    source_commit: ProjectCommit, caplog: pytest.LogCaptureFixture
) -> None:
    project = source_commit.project
    shot = source_shot(uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(source_commit, [shot])
    changed = replace(shot, uuid=str(uuid.uuid4()))
    project.sync_exploration_leads(
        source_commit,
        [replace(changed, longitude=-86), replace(changed, longitude=-85)],
    )
    assert project.exploration_leads.get().coordinates == (-87, 20)
    assert not project.exploration_lead_sources.filter(
        kind=project.exploration_lead_sources.model.Kind.UUID, payload=changed.uuid
    ).exists()
    assert "Conflicting exploration lead" in caplog.text


@pytest.mark.django_db
@pytest.mark.parametrize("reverse", [False, True])
def test_batch_deletion_propagates_before_new_aliases_are_created(
    source_commit: ProjectCommit,
    reverse: bool,
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    project.exploration_leads.get().delete()
    native_uuid = str(uuid.uuid4())
    later_uuid = str(uuid.uuid4())
    shots = [
        source_shot(uuid=native_uuid, shot_id="9", from_id="8"),
        source_shot(uuid=native_uuid),
        source_shot(uuid=later_uuid, shot_id="9", from_id="8", length_m=14),
        source_shot(uuid=later_uuid, shot_id="11", from_id="10"),
    ]
    project.sync_exploration_leads(
        source_commit, list(reversed(shots)) if reverse else shots
    )
    assert not project.exploration_leads.exists()
    project.sync_exploration_leads(source_commit, [shots[0]])
    project.sync_exploration_leads(source_commit, [shots[-1]])
    assert not project.exploration_leads.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reverse", [False, True])
def test_chained_unclaimed_aliases_reach_the_persisted_owner(
    source_commit: ProjectCommit,
    reverse: bool,
) -> None:
    project = source_commit.project
    project.sync_exploration_leads(source_commit, [source_shot()])
    original = project.exploration_leads.get()
    first_uuid, second_uuid = str(uuid.uuid4()), str(uuid.uuid4())
    shots = [
        source_shot(uuid=first_uuid, longitude=-85),
        source_shot(uuid=first_uuid, shot_id="9", from_id="8", longitude=-85),
        source_shot(uuid=second_uuid, shot_id="9", from_id="8", longitude=-85),
        source_shot(uuid=second_uuid, shot_id="11", from_id="10", longitude=-85),
    ]
    project.sync_exploration_leads(
        source_commit, list(reversed(shots)) if reverse else shots
    )
    assert project.exploration_leads.get().pk == original.pk
    original.refresh_from_db()
    assert original.coordinates == (-87, 20)
    assert (
        project.exploration_lead_sources.get(
            kind=project.exploration_lead_sources.model.Kind.UUID, payload=second_uuid
        ).lead_id
        == original.pk
    )
    project.sync_exploration_leads(
        source_commit,
        [source_shot(uuid=second_uuid, shot_id="99", from_id="98", longitude=-84)],
    )
    assert project.exploration_leads.get().pk == original.pk
    assert project.exploration_leads.get().coordinates == (-87, 20)


@pytest.mark.django_db
@pytest.mark.parametrize("reverse", [False, True])
def test_known_uuid_owners_keep_priority_across_weaker_shared_endpoints(
    source_commit: ProjectCommit,
    reverse: bool,
) -> None:
    project = source_commit.project
    first = source_shot(uuid=str(uuid.uuid4()))
    second = source_shot(uuid=str(uuid.uuid4()), shot_id="8", from_id="7")
    project.sync_exploration_leads(source_commit, [first, second])
    first_lead = project.exploration_leads.get(
        sources__kind=1, sources__payload=first.uuid
    )
    second_lead = project.exploration_leads.get(
        sources__kind=1, sources__payload=second.uuid
    )
    shots = [
        replace(first, shot_id="99", from_id="98", longitude=-86),
        replace(second, shot_id="99", from_id="98", longitude=-85),
    ]
    project.sync_exploration_leads(
        source_commit, list(reversed(shots)) if reverse else shots
    )
    first_lead.refresh_from_db()
    second_lead.refresh_from_db()
    assert first_lead.coordinates == (-87, 20)
    assert second_lead.coordinates == (-87, 20)
    assert project.exploration_leads.count() == len(shots)
    # The disputed new endpoint and measurement aliases must not acquire an
    # arbitrary owner while the two established UUID identities stay distinct.
    for kind, digest, _ in project._lead_signatures(shots[0]):  # noqa: SLF001
        if kind != project.exploration_lead_sources.model.Kind.UUID:
            assert not project.exploration_lead_sources.filter(
                kind=kind, digest=digest
            ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reverse", [False, True])
def test_new_sources_with_conflicting_destinations_do_not_depend_on_order(
    source_commit: ProjectCommit,
    reverse: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    shots = [
        source_shot(uuid=str(uuid.uuid4())),
        source_shot(uuid=str(uuid.uuid4()), longitude=-85),
    ]
    project = source_commit.project
    project.sync_exploration_leads(
        source_commit, list(reversed(shots)) if reverse else shots
    )
    assert not project.exploration_leads.exists()
    assert not project.exploration_lead_sources.exists()
    assert "Conflicting exploration lead" in caplog.text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "headings", [[360], [-1], [float("nan")], [float("inf")], [None], [0, 1, 2, 3]]
)
def test_database_rejects_invalid_heading_arrays(
    project: Project, headings: list[float]
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ExplorationLead.objects.create(
            project=project,
            longitude=-87,
            latitude=20,
            headings=headings,
            created_by="surveyor@example.test",
        )
