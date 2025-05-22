import re
from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from typing import Any

from django.urls import register_converter as _register_converter

from speleodb.surveys.models import Format


def register_converter(type_name: str) -> Callable[[type[object]], Any]:
    """
    Decorator to register a custom path converter with a given type_name.z
    """

    def decorator(cls: type[object]) -> Any:
        _register_converter(cls, type_name)
        return cls

    return decorator


class BaseRegexConverter(ABC):
    @property
    @abstractmethod
    def regex(self) -> re.Pattern[str]: ...

    def to_python(self, value: str) -> str:
        # Validate the hexsha value with the regex
        if not self.regex.match(value):
            raise ValueError(f"Invalid value: {value}")
        return value

    def to_url(self, value: str) -> str:
        return value  # Return the value as is for URL generation


@register_converter("gitsha")
class GitSHAConverter(BaseRegexConverter):
    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile(r"[0-9a-fA-F]{6,40}")


@register_converter("blobsha")
class BlobSHAConverter(BaseRegexConverter):
    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile(r"[0-9a-fA-F]{40}")


class BaseChoicesConverter(BaseRegexConverter):
    choices: list[str]

    @property
    def regex(self) -> re.Pattern[str]:
        escaped_strings = map(re.escape, self.choices)
        return re.compile(r"|".join(escaped_strings))


@register_converter("download_format")
class DownloadFormatsConverter(BaseChoicesConverter):
    choices = Format.FileFormat.download_choices


@register_converter("upload_format")
class UploadFormatsConverter(BaseChoicesConverter):
    choices = Format.FileFormat.upload_choices
