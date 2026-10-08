"""Block direct source lookup; Django's ignore_patterns owns collection."""

from __future__ import annotations

from django.contrib.staticfiles.apps import StaticFilesConfig
from django.contrib.staticfiles.finders import AppDirectoriesFinder
from django.contrib.staticfiles.finders import FileSystemFinder


class CompiledStaticFilesConfig(StaticFilesConfig):
    """Use Django's standard collection exclusions for compiler inputs."""

    ignore_patterns: list[str] = [*StaticFilesConfig.ignore_patterns, "*.ts"]


class SourceProtectedFileSystemFinder(FileSystemFinder):
    """Apply the source boundary to configured STATICFILES_DIRS locations."""

    def find_location(
        self, root: str, path: str, prefix: str | None = None
    ) -> str | None:
        if path.endswith(".ts"):
            return None
        return super().find_location(root, path, prefix)


class SourceProtectedAppDirectoriesFinder(AppDirectoriesFinder):
    """Apply the same source boundary to installed applications' static trees."""

    def find_in_app(self, app: str, path: str) -> str | None:
        if path.endswith(".ts"):
            return None
        return super().find_in_app(app, path)
