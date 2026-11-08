# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

import pytest
from django.urls import Resolver404
from django.urls import resolve

from speleodb.processors._impl.dump import DumpProcessor
from speleodb.processors.auto_selector import AutoSelector
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import FileFormat


@pytest.mark.parametrize("excluded", [FileFormat.DUMP, (9999, "DUMP")])
def test_file_format_exclusions_accept_enum_and_choice_tuple(
    excluded: FileFormat | tuple[int, str],
) -> None:
    choices = FileFormat.filtered_choices(exclude_vals=[excluded])
    assert (FileFormat.DUMP.value, FileFormat.DUMP.label) not in choices
    assert (FileFormat.STALAGMIGHT.value, FileFormat.STALAGMIGHT.label) in choices


@pytest.mark.parametrize("fileformat", FileFormat.download_choices)
def test_download_formats_have_an_implemented_download(fileformat: str) -> None:
    processor = AutoSelector.get_processor(FileFormat.from_str(fileformat.upper()))
    assert processor is DumpProcessor or processor.TARGET_SAVE_FILENAME is not None
    route = (
        f"/api/v2/projects/00000000-0000-0000-0000-000000000001/download/{fileformat}/"
    )
    assert resolve(route).url_name == "project-download"


@pytest.mark.parametrize(
    ("operation", "fileformat"),
    [
        ("upload", "dump"),
        ("download", "auto"),
        ("download", "other"),
        ("download", "compass_manual"),
        ("download", "walls_srv"),
        ("download", "walls_wpj"),
        ("download", "stickmaps"),
    ],
)
def test_unsupported_file_operations_do_not_resolve(
    operation: str, fileformat: str
) -> None:
    route = (
        "/api/v2/projects/00000000-0000-0000-0000-000000000001/"
        f"{operation}/{fileformat}/"
    )
    with pytest.raises(Resolver404):
        resolve(route)


def test_pseudo_formats_are_not_persistable_choices() -> None:
    values = {value for value, _label in FileFormat.db_choices}
    assert FileFormat.AUTO not in values
    assert FileFormat.DUMP not in values
    assert FileFormat.STALAGMIGHT in values


@pytest.mark.parametrize(
    "cls_processor",
    list(BaseFileProcessor.__subclasses__()),
)
def test_no_extension_collisions(cls_processor: type[BaseFileProcessor]) -> None:
    subclasses = BaseFileProcessor.__subclasses__()
    collisions = []

    for subclass in subclasses:
        if subclass is cls_processor:
            continue

        overlapping_extensions = set(subclass.ALLOWED_EXTENSIONS).intersection(
            cls_processor.ALLOWED_EXTENSIONS
        )

        # Special case for wildcard
        if "*" in overlapping_extensions:
            overlapping_extensions.remove("*")

        if overlapping_extensions:
            for ext in overlapping_extensions:
                collisions.append(  # noqa: PERF401
                    f"Collision found: Extension '{ext}' is in both "
                    f"{subclass.__name__} and {cls_processor.__name__}"
                )

    assert not collisions, "\n".join(collisions)


@pytest.mark.parametrize(
    "cls_processor",
    list(BaseFileProcessor.__subclasses__()),
)
def test_no_duplicate_extensions(cls_processor: type[BaseFileProcessor]) -> None:
    duplicate_extensions = []

    allowed_extensions = cls_processor.ALLOWED_EXTENSIONS
    seen = set()

    # Check for duplicates by comparing original list with a set
    for ext in allowed_extensions:
        if ext in seen:
            duplicate_extensions.append(
                f"Duplicate found: Extension '{ext}' in class {cls_processor.__name__}"
            )
        seen.add(ext)

    assert not duplicate_extensions, "\n".join(duplicate_extensions)


@pytest.mark.parametrize(
    "cls_processor",
    list(BaseFileProcessor.__subclasses__()),
)
def test_no_dangerous_extension_is_allowed(
    cls_processor: type[BaseFileProcessor],
) -> None:
    error_messages = []

    # Check for duplicates by comparing original list with a set
    for ext in cls_processor.ALLOWED_EXTENSIONS:
        if ext in BaseFileProcessor.REJECTED_EXTENSIONS:
            error_messages.append(  # noqa: PERF401
                f"Dangerous extension found: Extension '{ext}' in class: "
                f"{cls_processor.__name__}"
            )

    assert not error_messages, "\n".join(error_messages)


if __name__ == "__main__":
    unittest.main()
