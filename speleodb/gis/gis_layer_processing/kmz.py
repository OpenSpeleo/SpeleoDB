# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import re
import stat
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any

from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.kml import compile_kml
from speleodb.gis.models.gis_layer import GISLayerSourceFormat

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class KMZProcessor(BaseGISLayerProcessor):
    source_format = GISLayerSourceFormat.KMZ

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        return compile_kml(read_kmz(source))


def read_kmz(source: bytes) -> bytes:
    """Return the primary KML document from a valid KMZ archive."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(source), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_INVALID,
            "The KMZ archive is not a valid ZIP container.",
        ) from exc

    with archive:
        entries = archive.infolist()
        if not entries:
            raise GISLayerProcessingError(
                ProcessingErrorCode.ZIP_INVALID,
                "The KMZ archive is empty.",
            )
        normalized_names: dict[str, zipfile.ZipInfo] = {}
        for entry in entries:
            normalized_name = _validate_entry(entry)
            if normalized_name.lower().endswith((".zip", ".kmz")):
                raise GISLayerProcessingError(
                    ProcessingErrorCode.ZIP_UNSAFE_ENTRY,
                    "Nested archives inside a KMZ are not supported.",
                    details={"entry": normalized_name},
                )
            collision_key = normalized_name.casefold()
            if collision_key in normalized_names:
                raise GISLayerProcessingError(
                    ProcessingErrorCode.ZIP_UNSAFE_ENTRY,
                    "The KMZ archive contains duplicate or case-colliding paths.",
                    details={"entry": normalized_name},
                )
            normalized_names[collision_key] = entry

        main_entry = _select_main_kml(entries)
        return _read_member(archive, main_entry)


def _validate_entry(entry: zipfile.ZipInfo) -> str:
    name = entry.filename
    if not name or "\x00" in name or "\\" in name:
        raise _unsafe_entry(name)
    if name.startswith(("/", "//")) or _WINDOWS_DRIVE.match(name):
        raise _unsafe_entry(name)

    raw_parts = name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts[:-1]):
        raise _unsafe_entry(name)
    if raw_parts[-1] in {"", ".", ".."} and not entry.is_dir():
        raise _unsafe_entry(name)
    normalized_parts = [unicodedata.normalize("NFC", part) for part in raw_parts]
    path = PurePosixPath(*normalized_parts)
    normalized_name = path.as_posix()

    unix_mode = entry.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type and not (stat.S_ISREG(unix_mode) or stat.S_ISDIR(unix_mode)):
        raise _unsafe_entry(name)
    if entry.flag_bits & 0x1:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_UNSAFE_ENTRY,
            "Encrypted KMZ entries are not supported.",
            details={"entry": normalized_name},
        )
    if entry.compress_type not in _ALLOWED_COMPRESSION_METHODS:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_UNSAFE_ENTRY,
            "The KMZ archive uses an unsupported compression method.",
            details={"entry": normalized_name},
        )
    return normalized_name


def _select_main_kml(entries: list[zipfile.ZipInfo]) -> zipfile.ZipInfo:
    candidates = [
        entry
        for entry in entries
        if not entry.is_dir() and entry.filename.lower().endswith(".kml")
    ]
    root_doc = [entry for entry in candidates if entry.filename.casefold() == "doc.kml"]
    if len(root_doc) == 1:
        return root_doc[0]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_INVALID,
            "The KMZ archive does not contain a KML document.",
        )
    raise GISLayerProcessingError(
        ProcessingErrorCode.ZIP_AMBIGUOUS_MAIN_KML,
        "The KMZ archive contains multiple KML documents and no root doc.kml.",
        details={"candidate_count": len(candidates)},
    )


def _read_member(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
) -> bytes:
    try:
        payload = archive.read(entry)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_INVALID,
            "A KMZ member failed integrity verification.",
            details={"entry": entry.filename},
        ) from exc
    if len(payload) != entry.file_size:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_INVALID,
            "A KMZ member size does not match its directory entry.",
            details={"entry": entry.filename},
        )
    return payload


def _unsafe_entry(name: str) -> GISLayerProcessingError:
    return GISLayerProcessingError(
        ProcessingErrorCode.ZIP_UNSAFE_ENTRY,
        "The KMZ archive contains an unsafe path or special entry.",
        details={"entry": name},
    )
