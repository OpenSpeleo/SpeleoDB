from django import template

from speleodb.users.models import SurveyTeam
from speleodb.users.models import User

register = template.Library()


@register.filter(name="user_has_team_access")
def user_has_team_access(team: SurveyTeam, user: User) -> bool:
    return bool(team.is_member(user))
