import re
from typing import Any

from deepdiff import DeepDiff


def is_valid_git_sha(hash_string: str) -> bool:
    """Check if the provided string is a valid Git SHA-1 hash."""
    pattern = r"^[0-9a-fA-F]{40}$"
    return bool(re.fullmatch(pattern, hash_string))


def is_subset(subset_dict: dict[Any, Any], super_dict: dict[Any, Any]) -> bool:
    # return all(item in super_dict.items() for item in subset_dict.items())
    ddiff = DeepDiff(subset_dict, super_dict, ignore_order=True)
    return ddiff.get("values_changed", None) is None
