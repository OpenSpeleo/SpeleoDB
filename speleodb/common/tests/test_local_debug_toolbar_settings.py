from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

BASE_DIR = Path(__file__).parents[3]

SETTINGS_PROBE = """
import json

import django
from django.conf import settings
from django.urls import get_resolver

django.setup()

from django.http import HttpResponse
from django.test import RequestFactory
from debug_toolbar.middleware import DebugToolbarMiddleware

patterns = {str(pattern.pattern) for pattern in get_resolver().url_patterns}
request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
response = DebugToolbarMiddleware(
    lambda _: HttpResponse("<html><body>ok</body></html>")
)(request)
print(
    json.dumps(
        {
            "installed": "debug_toolbar" in settings.INSTALLED_APPS,
            "middleware": (
                "debug_toolbar.middleware.DebugToolbarMiddleware"
                in settings.MIDDLEWARE
            ),
            "route": "__debug__/" in patterns,
            "rendered": b"djDebug" in response.content,
            "configured": hasattr(settings, "DEBUG_TOOLBAR_CONFIG"),
            "panels": list(settings.DEBUG_TOOLBAR_PANELS),
            "disabled_panels": sorted(
                settings.DEBUG_TOOLBAR_CONFIG["DISABLE_PANELS"]
            ),
            "enable_stacktraces": settings.DEBUG_TOOLBAR_CONFIG[
                "ENABLE_STACKTRACES"
            ],
            "enable_stacktraces_locals": settings.DEBUG_TOOLBAR_CONFIG[
                "ENABLE_STACKTRACES_LOCALS"
            ],
            "prettify_sql": settings.DEBUG_TOOLBAR_CONFIG["PRETTIFY_SQL"],
            "profiler_capture_project_code": settings.DEBUG_TOOLBAR_CONFIG[
                "PROFILER_CAPTURE_PROJECT_CODE"
            ],
            "show_template_context": settings.DEBUG_TOOLBAR_CONFIG[
                "SHOW_TEMPLATE_CONTEXT"
            ],
            "show_toolbar_callback": settings.DEBUG_TOOLBAR_CONFIG[
                "SHOW_TOOLBAR_CALLBACK"
            ],
        }
    )
)
"""


class DebugToolbarState(TypedDict):
    installed: bool
    middleware: bool
    route: bool
    rendered: bool
    configured: bool
    panels: list[str]
    disabled_panels: list[str]
    enable_stacktraces: bool
    enable_stacktraces_locals: bool
    prettify_sql: bool
    profiler_capture_project_code: bool
    show_template_context: bool
    show_toolbar_callback: str


def probe_local_settings() -> DebugToolbarState:
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "AWS_ACCESS_KEY_ID": "access_key",
            "AWS_S3_CUSTOM_DOMAIN": "localhost:9000/test-bucket",
            "AWS_SECRET_ACCESS_KEY": "secret_key",
            "AWS_STORAGE_BUCKET_NAME": "test-bucket",
            "DATABASE_URL": "sqlite:///:memory:",
            "DJANGO_READ_DOT_ENV_FILE": "False",
            "DJANGO_SECRET_KEY": "test-only-secret-key",
            "DJANGO_SETTINGS_MODULE": "config.settings.local",
            "GITLAB_GROUP_ID": "1",
            "GITLAB_GROUP_NAME": "test-group",
            "GITLAB_HOST_URL": "localhost:9080",
            "GITLAB_TOKEN": "test-token",
            "MAPBOX_API_TOKEN": "test-token",
            "USE_DOCKER": "False",
        }
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", SETTINGS_PROBE],
        cwd=BASE_DIR,
        env=child_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"Local settings probe failed with exit code {result.returncode}:\n"
            f"{result.stderr}"
        )
    payload: object = json.loads(result.stdout)

    def require_bool(key: str) -> bool:
        if not isinstance(payload, dict):
            raise TypeError("Settings probe did not return a JSON object")
        value = payload.get(key)
        if not isinstance(value, bool):
            raise TypeError(f"Settings probe field {key!r} is not a boolean")
        return value

    def require_string(key: str) -> str:
        if not isinstance(payload, dict):
            raise TypeError("Settings probe did not return a JSON object")
        value = payload.get(key)
        if not isinstance(value, str):
            raise TypeError(f"Settings probe field {key!r} is not a string")
        return value

    def require_string_list(key: str) -> list[str]:
        if not isinstance(payload, dict):
            raise TypeError("Settings probe did not return a JSON object")
        value = payload.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise TypeError(f"Settings probe field {key!r} is not a string list")
        return value

    return DebugToolbarState(
        installed=require_bool("installed"),
        middleware=require_bool("middleware"),
        route=require_bool("route"),
        rendered=require_bool("rendered"),
        configured=require_bool("configured"),
        panels=require_string_list("panels"),
        disabled_panels=require_string_list("disabled_panels"),
        enable_stacktraces=require_bool("enable_stacktraces"),
        enable_stacktraces_locals=require_bool("enable_stacktraces_locals"),
        prettify_sql=require_bool("prettify_sql"),
        profiler_capture_project_code=require_bool("profiler_capture_project_code"),
        show_template_context=require_bool("show_template_context"),
        show_toolbar_callback=require_string("show_toolbar_callback"),
    )


def test_local_debug_toolbar_is_present_with_all_panels_disabled() -> None:
    state = probe_local_settings()

    assert state["installed"] is True
    assert state["middleware"] is True
    assert state["route"] is True
    assert state["rendered"] is True
    assert state["configured"] is True
    assert state["panels"]
    assert set(state["disabled_panels"]) == set(state["panels"])
    assert state["enable_stacktraces"] is False
    assert state["enable_stacktraces_locals"] is False
    assert state["prettify_sql"] is False
    assert state["profiler_capture_project_code"] is False
    assert state["show_template_context"] is False
    assert state["show_toolbar_callback"] == "speleodb.debug_toolbar.show_toolbar"
