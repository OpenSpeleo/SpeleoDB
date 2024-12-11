import re


def is_valid_git_sha(hash_string: str) -> bool:
    """Check if the provided string is a valid Git SHA-1 hash."""
    pattern = r"^[0-9a-fA-F]{40}$"
    return bool(re.fullmatch(pattern, hash_string))


def is_subset(subset_dict, super_dict):
    return all(item in super_dict.items() for item in subset_dict.items())
