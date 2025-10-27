# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import override

from django.core.exceptions import ObjectDoesNotExist
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.users.models import SurveyTeam

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpResponse

    from speleodb.utils.requests import AuthenticatedHttpRequest


class TeamListingView(AuthenticatedTemplateView):
    template_name = "pages/teams.html"


class NewTeamView(AuthenticatedTemplateView):
    template_name = "pages/team/new.html"


class _BaseTeamView(AuthenticatedTemplateView):
    def get_data_or_redirect(
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
    ) -> HttpResponseRedirectBase | dict[str, SurveyTeam | bool]:
        try:
            team = SurveyTeam.objects.get(id=team_id)
            if request.user and request.user.is_authenticated:
                if not team.is_member(request.user):
                    return redirect(reverse("private:teams"))
            else:
                return redirect(reverse("home"))
        except ObjectDoesNotExist:
            return redirect(reverse("private:teams"))

        return {"team": team, "is_team_leader": team.is_leader(request.user)}


class TeamDetailsView(_BaseTeamView):
    template_name = "pages/team/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse | dict[str, SurveyTeam | bool]:
        data = self.get_data_or_redirect(request, team_id=team_id)
        if isinstance(data, HttpResponseRedirectBase):
            return data

        return super().get(request, *args, **data, **kwargs)


class TeamMembershipsView(_BaseTeamView):
    template_name = "pages/team/memberships.html"

    @override
    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        data: Any = self.get_data_or_redirect(request, team_id=team_id)
        if isinstance(data, HttpResponseRedirectBase):
            return data

        data["memberships"] = data["team"].get_all_memberships()  # pyright: ignore[reportAttributeAccessIssue]

        return super().get(request, *args, **data, **kwargs)


class TeamDangerZoneView(_BaseTeamView):
    template_name = "pages/team/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        team_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        data = self.get_data_or_redirect(request, team_id=team_id)
        if not isinstance(data, dict):
            return data  # redirection

        if not data["is_team_leader"]:
            return redirect(
                reverse("private:team_details", kwargs={"team_id": team_id})
            )

        return super().get(request, *args, **data, **kwargs)
