# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import re
import stat
import struct
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from speleodb.gis.gis_layer_processing import limits
from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.kml import _require_overlay
from speleodb.gis.gis_layer_processing.kml import analyze_kml
from speleodb.gis.gis_layer_processing.kml import compile_kml
from speleodb.gis.gis_layer_processing.types import CompilationResult
from speleodb.gis.gis_layer_processing.types import KMLWarning
from speleodb.gis.models.gis_layer import GISLayerSourceFormat

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class KMZProcessor(BaseGISLayerProcessor):
    source_format = GISLayerSourceFormat.KMZ

    def process(self, source: bytes) -> CompilationResult:
        document = read_kmz_document(source)
        analysis = _require_overlay(
            analyze_kml(document.source, warnings=document.warnings)
        )
        return CompilationResult(display_geojson=analysis.display_geojson)

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        return compile_kml(read_kmz(source))


def read_kmz(source: bytes) -> bytes:
    """Return the primary KML document from a valid KMZ archive."""
    return read_kmz_document(source).source


@dataclass(frozen=True, slots=True)
class KMZDocument:
    source: bytes
    warnings: tuple[KMLWarning, ...] = ()


def read_kmz_document(source: bytes) -> KMZDocument:
    limits.check_source_size(len(source))
    try:
        _preflight_member_count(source)
        archive = zipfile.ZipFile(io.BytesIO(source), mode="r")
    except (
        OSError,
        OverflowError,
        UnicodeError,
        NotImplementedError,
        struct.error,
        zipfile.BadZipFile,
    ) as exc:
        raise GISLayerProcessingError(
            ProcessingErrorCode.ZIP_INVALID,
            "The KMZ archive is not a valid ZIP container.",
        ) from exc

    with archive:
        entries = archive.infolist()
        if len(entries) > limits.MAX_KMZ_MEMBERS:
            raise _entry_limit_error()
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
        extra_documents = (
            sum(
                1
                for entry in entries
                if not entry.is_dir() and entry.filename.lower().endswith(".kml")
            )
            - 1
        )
        warnings = (
            (
                KMLWarning(
                    "ADDITIONAL_KML_DOCUMENTS",
                    "Only the primary KML document is imported.",
                    extra_documents,
                ),
            )
            if extra_documents
            else ()
        )
        return KMZDocument(_read_member(archive, main_entry), warnings)


def _preflight_member_count(source: bytes) -> None:
    """Count real directory records before ZipFile eagerly allocates ZipInfo.

    Reuse the standard library's EOCD/ZIP64 reader and record constants so this
    follows the exact directory ZipFile will consume, including prepended data.
    The declared entry count is not trusted: every directory header is walked
    without decoding or allocating its filename, extra data, or comment.
    """
    end_record = zipfile._EndRecData(io.BytesIO(source))  # type: ignore[attr-defined]  # noqa: SLF001
    if end_record is None:
        raise zipfile.BadZipFile("Missing end of central directory")
    directory_size: int = end_record[zipfile._ECD_SIZE]  # type: ignore[attr-defined]  # noqa: SLF001
    directory_end: int = end_record[zipfile._ECD_LOCATION]  # type: ignore[attr-defined]  # noqa: SLF001
    declared_count: int = end_record[zipfile._ECD_ENTRIES_TOTAL]  # type: ignore[attr-defined]  # noqa: SLF001
    if declared_count > limits.MAX_KMZ_MEMBERS:
        raise _entry_limit_error()
    if not 0 <= directory_size <= directory_end <= len(source):
        raise zipfile.BadZipFile("Invalid central directory size")
    if len(end_record[zipfile._ECD_COMMENT]) != end_record[zipfile._ECD_COMMENT_SIZE]:  # type: ignore[attr-defined]  # noqa: SLF001
        raise zipfile.BadZipFile("Truncated archive comment")
    cursor: int = directory_end - directory_size
    actual_count: int = 0
    while cursor < directory_end:
        actual_count += 1
        if actual_count > limits.MAX_KMZ_MEMBERS:
            raise _entry_limit_error()
        if directory_end - cursor < zipfile.sizeCentralDir:  # type: ignore[attr-defined]
            raise zipfile.BadZipFile("Truncated central directory header")
        header = struct.unpack_from(zipfile.structCentralDir, source, cursor)  # type: ignore[attr-defined]
        if header[zipfile._CD_SIGNATURE] != zipfile.stringCentralDir:  # type: ignore[attr-defined]  # noqa: SLF001
            raise zipfile.BadZipFile("Invalid central directory signature")
        cursor += (
            zipfile.sizeCentralDir  # type: ignore[attr-defined]
            + header[zipfile._CD_FILENAME_LENGTH]  # type: ignore[attr-defined]  # noqa: SLF001
            + header[zipfile._CD_EXTRA_FIELD_LENGTH]  # type: ignore[attr-defined]  # noqa: SLF001
            + header[zipfile._CD_COMMENT_LENGTH]  # type: ignore[attr-defined]  # noqa: SLF001
        )
        if cursor > directory_end:
            raise zipfile.BadZipFile("Truncated central directory fields")
    if actual_count != declared_count:
        raise zipfile.BadZipFile("Inconsistent central directory entry count")


def _entry_limit_error() -> GISLayerProcessingError:
    return GISLayerProcessingError(
        ProcessingErrorCode.ZIP_ENTRY_LIMIT,
        "The KMZ archive contains too many files.",
        details={"limit": limits.MAX_KMZ_MEMBERS},
    )


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
    limits.check_source_size(entry.file_size)
    try:
        with archive.open(entry) as member:
            payload = limits.read_bounded_source(member)
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
