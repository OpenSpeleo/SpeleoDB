import unittest

import pytest

from speleodb.processors.base import BaseFileProcessor


@pytest.mark.parametrize(
    "cls_processor",
    list(BaseFileProcessor.__subclasses__()),
)
def test_no_extension_collisions(cls_processor: type[BaseFileProcessor]):
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
def test_no_duplicate_extensions(cls_processor: type[BaseFileProcessor]):
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


if __name__ == "__main__":
    unittest.main()
