# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings

from frontend_private.views.base import AuthenticatedTemplateView

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.utils.requests import AuthenticatedHttpRequest


class MapViewerView(AuthenticatedTemplateView):
    template_name = "pages/map_viewer.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        survey_projects = [
            project for project in request.user.projects if not project.exclude_geojson
        ]

        # Convert projects to a JSON-serializable format
        projects_data = []
        for project in survey_projects:
            data_entry = {
                "id": str(project.id),
                "name": project.name,
                "modified_date": project.modified_date.isoformat(),
                "permissions": request.user.get_best_permission(project).level_label,
                "geojson_url": None,
            }

            if (latest_geojson := project.rel_geojsons.first()) is not None:
                data_entry["geojson_url"] = latest_geojson.get_signed_download_url()

            projects_data.append(data_entry)

        # Check if user has write access to any project
        # For map viewer, we'll grant write access if user has write access
        # to any project

        has_write_access = any(
            request.user.get_best_permission(project) for project in survey_projects
        )

        data = {
            "projects": json.dumps(projects_data),
            "has_write_access": has_write_access,
            "mapbox_api_token": settings.MAPBOX_API_TOKEN,
        }
        return super().get(request, *args, **data, **kwargs)
