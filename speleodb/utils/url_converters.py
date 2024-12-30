import re
from abc import ABC
from abc import abstractmethod

from django.urls import register_converter as _register_converter

from speleodb.surveys.models import Format


def register_converter(type_name):
    """
    Decorator to register a custom path converter with a given type_name.
    """

    def decorator(cls):
        _register_converter(cls, type_name)
        return cls

    return decorator


class BaseRegexConverter(ABC):
    @abstractmethod
    def regex(self):
        raise NotImplementedError

    def to_python(self, value):
        # Validate the hexsha value with the regex
        if not re.match(self.regex, value):
            raise ValueError(f"Invalid value: {value}")
        return value

    def to_url(self, value):
        return value  # Return the value as is for URL generation


class BaseChoicesConverter(BaseRegexConverter):
    @property
    @abstractmethod
    def choices(self):
        raise NotImplementedError

    @property
    def regex(self):
        escaped_strings = map(re.escape, self.choices)
        return "|".join(escaped_strings)


@register_converter("gitsha")
class GitSHAConverter(BaseRegexConverter):
    regex = r"[0-9a-fA-F]{6,40}"


@register_converter("blobsha")
class BlobSHAConverter(BaseRegexConverter):
    regex = r"[0-9a-fA-F]{40}"


@register_converter("download_format")
class DownloadFormatsConverter(BaseChoicesConverter):
    choices = Format.FileFormat.download_choices


@register_converter("upload_format")
class UploadFormatsConverter(BaseChoicesConverter):
    choices = Format.FileFormat.upload_choices
