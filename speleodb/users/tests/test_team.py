import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError

from speleodb.api.v1.tests.factories import SurveyTeamMembershipFactory
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.fixture
def leader_membership(db, team: SurveyTeam) -> SurveyTeamMembership:
    """
    Fixture for creating a SurveyTeamMembership instance with a leader role.
    """
    user = UserFactory.create()
    return SurveyTeamMembershipFactory.create(
        team=team, user=user, role=SurveyTeamMembership.Role.LEADER
    )


@pytest.fixture
def member_membership(db: None, team: SurveyTeam) -> SurveyTeamMembership:
    """
    Fixture for creating a SurveyTeamMembership instance with a member role.
    """
    user = UserFactory.create()
    return SurveyTeamMembershipFactory.create(
        team=team, user=user, role=SurveyTeamMembership.Role.MEMBER
    )


@pytest.mark.django_db
class TestSurveyTeam:
    def test_str_representation(self, team: SurveyTeam) -> None:
        """Test the __str__ method."""
        assert str(team) == team.name

    def test_get_all_memberships(
        self,
        team: SurveyTeam,
        leader_membership: SurveyTeamMembership,
        member_membership: SurveyTeamMembership,
    ) -> None:
        """
        Test get_all_memberships returns active memberships in the correct order.
        """
        memberships = team.get_all_memberships()
        assert memberships.count() == 2  # noqa: PLR2004
        assert memberships.first() == leader_membership
        assert memberships.last() == member_membership

    def test_get_member_count(
        self,
        team: SurveyTeam,
        leader_membership: SurveyTeamMembership,
        member_membership: SurveyTeamMembership,
    ) -> None:
        """Test get_member_count returns the correct number of active members."""
        assert team.get_member_count() == 2  # noqa: PLR2004

    def test_get_membership(
        self, team: SurveyTeam, leader_membership: SurveyTeamMembership
    ) -> None:
        """Test get_membership retrieves an active membership."""
        user = leader_membership.user
        membership = team.get_membership(user)
        assert membership == leader_membership

    def test_get_membership_not_found(self, team: SurveyTeam, user: User) -> None:
        """Test get_membership returns None if no active membership is found."""
        with pytest.raises(ObjectDoesNotExist):
            _ = team.get_membership(user)

    def test_is_leader_true(
        self, team: SurveyTeam, leader_membership: SurveyTeamMembership
    ) -> None:
        """Test is_leader returns True for a user with the leader role."""
        assert team.is_leader(leader_membership.user) is True

    def test_is_leader_false(
        self, team: SurveyTeam, member_membership: SurveyTeamMembership
    ) -> None:
        """Test is_leader returns False for a user without the leader role."""
        assert team.is_leader(member_membership.user) is False


@pytest.mark.django_db
class TestSurveyTeamMembership:
    def test_str_representation_leader(
        self, leader_membership: SurveyTeamMembership
    ) -> None:
        """Test the __str__ method."""
        assert (
            str(leader_membership)
            == f"{leader_membership.user} => {leader_membership.team} [LEADER]"
        ), str(leader_membership)

    def test_str_representation_member(
        self, member_membership: SurveyTeamMembership
    ) -> None:
        """Test the __str__ method."""
        assert (
            str(member_membership)
            == f"{member_membership.user} => {member_membership.team} [MEMBER]"
        ), str(member_membership)

    def test_role_property_getter(
        self, member_membership: SurveyTeamMembership
    ) -> None:
        """Test the role property getter."""
        assert member_membership.role == "MEMBER"

    def test_role_property_setter(
        self, member_membership: SurveyTeamMembership
    ) -> None:
        """Test the role property setter."""
        member_membership.role = SurveyTeamMembership.Role.LEADER
        member_membership.save()
        assert member_membership._role == SurveyTeamMembership.Role.LEADER  # type: ignore # noqa: SLF001

    def test_deactivate(
        self, member_membership: SurveyTeamMembership, user: User
    ) -> None:
        """Test deactivate marks the membership as inactive and sets deactivated_by."""
        member_membership.deactivate(deactivated_by=user)
        assert not member_membership.is_active
        assert member_membership.deactivated_by == user

    def test_reactivate(
        self, member_membership: SurveyTeamMembership, user: User
    ) -> None:
        """Test reactivate resets is_active and role."""
        member_membership.deactivate(deactivated_by=user)
        member_membership.reactivate(SurveyTeamMembership.Role.LEADER)
        assert member_membership.is_active
        assert member_membership.deactivated_by is None
        assert member_membership.role == "LEADER"

    @pytest.mark.django_db(transaction=True)
    def test_unique_together_constraint(self, team: SurveyTeam, user: User) -> None:
        """Test unique_together prevents duplicate memberships."""
        SurveyTeamMembershipFactory(
            team=team, user=user, role=SurveyTeamMembership.Role.MEMBER
        )
        with pytest.raises(IntegrityError):
            SurveyTeamMembershipFactory(
                team=team, user=user, role=SurveyTeamMembership.Role.MEMBER
            )

    def test_inactive_membership_not_included(
        self, team: SurveyTeam, user: User, member_membership: SurveyTeamMembership
    ) -> None:
        """Test inactive memberships are excluded from active queries."""
        member_membership.deactivate(deactivated_by=user)
        memberships = team.get_all_memberships()
        assert member_membership not in memberships
