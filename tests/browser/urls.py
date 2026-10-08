"""HTTP fixtures for native synchronous XHR, scoped to the browser wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import JsonResponse
from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from config.urls import urlpatterns as application_urls
from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import UserProjectPermission

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpRequest

_tree_reads: dict[UUID, int] = {}


def permitted(request: HttpRequest, project_id: UUID) -> bool:
    return (
        request.method == "GET"
        and request.user.is_authenticated
        and UserProjectPermission.objects.filter(
            project_id=project_id,
            target_id=request.user.pk,
            is_active=True,
            level__gte=PermissionLevel.READ_ONLY,
        ).exists()
    )


def revision_fixture(request: HttpRequest, project_id: UUID) -> JsonResponse:
    """Keep the controller's original URL and blocking request semantics."""
    if not permitted(request, project_id):
        return JsonResponse({"detail": "Browser fixture access denied"}, status=403)
    response: JsonResponse = JsonResponse(
        {
            "commits": [
                {
                    "id": str(index) * 40,
                    "author_name": "Browser author",
                    "authored_date": "2026-01-01T12:00:00Z",
                    "message": f"Browser revision {index}",
                    "url": "#",
                    "formats": [
                        {"name": "DMP", "download_url": "/browser-fixture.dmp"}
                    ],
                }
                for index in (1, 2)
            ]
        }
    )
    response["X-SpeleoDB-Browser-Fixture"] = "revisions"
    return response


def tree_fixture(request: HttpRequest, project_id: UUID, hexsha: str) -> JsonResponse:
    """Serve deterministic repository presentation without opening a repository."""
    if not permitted(request, project_id):
        return JsonResponse({"detail": "Browser fixture access denied"}, status=403)
    _tree_reads[project_id] = _tree_reads.get(project_id, 0) + 1
    response: JsonResponse = JsonResponse(
        {
            "commit": {
                "author_name": "Browser author",
                "message": "Browser tree",
                "hexsha_short": hexsha[:8],
                "dt_since": "today",
            },
            "project": {"n_commits": 1},
            "files": [
                {
                    "path": "surveys/cave.dmp",
                    "name": "cave.dmp",
                    "size": "10 B",
                    "download_url": "/fixture.dmp",
                    "commit": {
                        "message": "Survey file",
                        "authored_date": "2026/01/01 12:00",
                        "dt_since": "today",
                        "url": "#",
                    },
                }
            ],
        }
    )
    response["X-SpeleoDB-Browser-Fixture"] = "tree"
    response["X-SpeleoDB-Fixture-Reads"] = str(_tree_reads[project_id])
    return response


# WebKit bypasses Playwright routing for synchronous XHR. These two explicit
# GET boundaries precede the production URLconf only in the browser test server;
# native XHR, controller contexts, Django URL reversal and vendor code stay real.
urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v2/projects/<uuid:project_id>/revisions/", revision_fixture),
    path(
        "api/v2/projects/<uuid:project_id>/git_explorer/<gitsha:hexsha>/", tree_fixture
    ),
    *application_urls,
]
