from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from threading import RLock
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict
from typing import cast

from django import template
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.html import format_html_join

if TYPE_CHECKING:
    from django.utils.safestring import SafeString

register = template.Library()


class ManifestEntry(TypedDict, total=False):
    file: str
    name: str
    names: list[str]
    src: str
    isEntry: bool
    isDynamicEntry: bool
    imports: list[str]
    dynamicImports: list[str]


class EntryRegistry(TypedDict):
    styles: dict[str, str]
    scripts: dict[str, str]


@dataclass
class AssetCache:
    manifest: dict[str, ManifestEntry] | None = None
    manifest_mtime_ns: int | None = None
    registry: EntryRegistry | None = None


_cache_lock = RLock()
_cache = AssetCache()


def _configured_path(setting_name: str) -> Path:
    value = getattr(settings, setting_name, None)
    if value is None:
        raise ImproperlyConfigured(f"{setting_name} must be configured")
    return Path(value)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(f"Unable to read {label} at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ImproperlyConfigured(f"{label} at {path} must contain a JSON object")
    return cast("dict[str, Any]", parsed)


def _entry_registry() -> EntryRegistry:
    if _cache.registry is not None:
        return _cache.registry

    raw = _read_json_object(
        _configured_path("VITE_ENTRY_REGISTRY_PATH"), "Vite entry registry"
    )
    styles = raw.get("styles")
    scripts = raw.get("scripts")
    if not isinstance(styles, dict) or not isinstance(scripts, dict):
        raise ImproperlyConfigured(
            "Vite entry registry must define object-valued styles and scripts"
        )
    overlap = set(styles) & set(scripts)
    if overlap:
        names = ", ".join(sorted(overlap))
        raise ImproperlyConfigured(f"Duplicate Vite logical entry names: {names}")

    _cache.registry = {
        "styles": {str(key): str(value) for key, value in styles.items()},
        "scripts": {str(key): str(value) for key, value in scripts.items()},
    }
    return _cache.registry


def _validate_asset_file(asset_file: str) -> str:
    path = PurePosixPath(asset_file)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ImproperlyConfigured(f"Unsafe Vite manifest asset path: {asset_file!r}")
    if path.parts[0] != "assets":
        raise ImproperlyConfigured(
            f"Vite manifest asset must live under assets/: {asset_file!r}"
        )
    return asset_file


def _parse_manifest(raw: dict[str, Any]) -> dict[str, ManifestEntry]:
    parsed: dict[str, ManifestEntry] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            raise ImproperlyConfigured(f"Invalid Vite manifest entry: {key}")
        asset_file = value.get("file")
        if not isinstance(asset_file, str):
            raise ImproperlyConfigured(f"Vite manifest entry has no file: {key}")
        _validate_asset_file(asset_file)
        parsed[str(key)] = cast("ManifestEntry", value)
    return parsed


def _manifest() -> dict[str, ManifestEntry] | None:
    path = _configured_path("VITE_MANIFEST_PATH")
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError as exc:
        if getattr(settings, "VITE_ALLOW_MISSING_MANIFEST", False):
            return None
        raise ImproperlyConfigured(
            f"Vite manifest is missing at {path}; run npm run build"
        ) from exc

    with _cache_lock:
        should_reload = _cache.manifest is None
        if settings.DEBUG and _cache.manifest_mtime_ns != mtime_ns:
            should_reload = True
        if should_reload:
            _cache.manifest = _parse_manifest(_read_json_object(path, "Vite manifest"))
            _cache.manifest_mtime_ns = mtime_ns
        return _cache.manifest


def _entry_type(name: str) -> str:
    registry = _entry_registry()
    if name in registry["styles"]:
        return "style"
    if name in registry["scripts"]:
        return "script"
    raise ImproperlyConfigured(f"Unknown Vite logical entry: {name!r}")


def _manifest_entry(name: str) -> tuple[str, ManifestEntry] | None:
    manifest = _manifest()
    if manifest is None:
        return None

    registry = _entry_registry()
    source = registry["styles"].get(name) or registry["scripts"].get(name)
    if source is None:
        raise ImproperlyConfigured(f"Unknown Vite logical entry: {name!r}")
    entry = manifest.get(source)
    if entry is None or entry.get("isEntry") is not True:
        if getattr(settings, "VITE_ALLOW_MISSING_MANIFEST", False):
            return None
        raise ImproperlyConfigured(
            f"Vite manifest has no entry for {name!r} at source {source!r}"
        )
    return source, entry


def _fallback_file(name: str, entry_type: str) -> str:
    extension = "css" if entry_type == "style" else "js"
    return f"assets/{name}.{extension}"


def _static_asset_url(asset_file: str) -> str:
    safe_file = _validate_asset_file(asset_file)
    if not getattr(settings, "VITE_ALLOW_MISSING_MANIFEST", False):
        built_file = _configured_path("VITE_ASSET_ROOT") / safe_file
        if not built_file.is_file():
            raise ImproperlyConfigured(
                f"Vite manifest references a missing asset: {safe_file!r}"
            )
    return static(f"speleodb/vite/{safe_file}")


def _entry_file(name: str, expected_type: str) -> str:
    entry_type = _entry_type(name)
    if entry_type != expected_type:
        raise ImproperlyConfigured(
            f"Vite entry {name!r} is a {entry_type}, not a {expected_type}"
        )
    match = _manifest_entry(name)
    if match is None:
        return _fallback_file(name, entry_type)
    return match[1]["file"]


def _preload_files(name: str) -> list[str]:
    if _entry_type(name) != "script":
        raise ImproperlyConfigured(f"Vite preload entry must be a script: {name!r}")
    match = _manifest_entry(name)
    if match is None:
        return [_fallback_file(name, "script")]

    manifest = _manifest()
    if manifest is None:  # pragma: no cover - guarded by the match above
        return [_fallback_file(name, "script")]

    files: list[str] = []
    seen_keys: set[str] = set()
    follow_dynamic = name.startswith("controller-")

    def visit(key: str, include_dynamic: bool) -> None:
        if key in seen_keys:
            return
        seen_keys.add(key)
        entry = manifest.get(key)
        if entry is None:
            raise ImproperlyConfigured(f"Missing imported Vite manifest entry: {key}")
        for imported_key in entry.get("imports", []):
            visit(imported_key, include_dynamic)
        if include_dynamic:
            for imported_key in entry.get("dynamicImports", []):
                visit(imported_key, include_dynamic)
        files.append(entry["file"])

    visit(match[0], follow_dynamic)
    return files


@register.simple_tag
def vite_styles(*names: str) -> SafeString:
    rendered: list[SafeString] = []
    seen: set[str] = set()
    for name in names:
        asset_file = _entry_file(name, "style")
        if asset_file in seen:
            continue
        seen.add(asset_file)
        rendered.append(
            format_html(
                '<link rel="stylesheet" href="{}">',
                _static_asset_url(asset_file),
            )
        )
    return format_html_join("\n", "{}", ((item,) for item in rendered))


@register.simple_tag
def vite_preload(*names: str) -> SafeString:
    rendered: list[SafeString] = []
    seen: set[str] = set()
    for name in names:
        for asset_file in _preload_files(name):
            if asset_file in seen:
                continue
            seen.add(asset_file)
            rendered.append(
                format_html(
                    '<link rel="modulepreload" href="{}" crossorigin>',
                    _static_asset_url(asset_file),
                )
            )
    return format_html_join("\n", "{}", ((item,) for item in rendered))


@register.simple_tag
def vite_script(name: str) -> SafeString:
    asset_file = _entry_file(name, "script")
    return format_html(
        '<script type="module" src="{}" crossorigin></script>',
        _static_asset_url(asset_file),
    )


def reset_vite_asset_caches() -> None:
    with _cache_lock:
        _cache.manifest = None
        _cache.manifest_mtime_ns = None
        _cache.registry = None
