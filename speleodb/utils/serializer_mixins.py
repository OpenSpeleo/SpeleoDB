# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from speleodb.utils.sanitize import sanitize_text


class SanitizedFieldsMixin:
    """
    Mixin for DRF serializers that automatically sanitizes designated text fields.

    Usage:
        class MySerializer(SanitizedFieldsMixin, serializers.ModelSerializer):
            sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    During ``to_internal_value``, every field listed in ``sanitized_fields``
    whose incoming value is a non-empty string will be passed through
    :func:`~speleodb.utils.sanitize.sanitize_text`.

    The mixin deliberately does **not** touch read-only or outgoing
    representations — only data flowing *into* the serializer is sanitized.
    """

    sanitized_fields: ClassVar[list[str]] = []

    def to_internal_value(self, data: Any) -> Any:
        ret = super().to_internal_value(data)  # type: ignore[misc]

        for field_name in self.sanitized_fields:
            if field_name in ret and isinstance(ret[field_name], str):
                ret[field_name] = sanitize_text(ret[field_name])

        return ret
