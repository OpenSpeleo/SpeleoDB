# -*- coding: utf-8 -*-

from __future__ import annotations

import enum
from typing import Any

from django.core.exceptions import ValidationError
from django_countries.fields import Country
from rest_framework import serializers


class CustomChoiceField(serializers.ChoiceField):
    _kwargs: Any

    def to_representation(self, obj: Any) -> str | Any:
        if obj == "" and self.allow_blank:
            return obj

        if isinstance(obj, Country):
            return obj.code

        val = self._choices[obj]

        if isinstance(val, enum.Enum):
            return self._choices[obj].name

        return val

    def to_internal_value(self, data: Any) -> str | Any:
        if self.field_name == "country":
            return super().to_internal_value(data)

        choices = {val.name.upper(): val for val in self._kwargs["choices"]}

        try:
            return choices[data.upper()]
        except KeyError as e:
            raise ValidationError(
                f"Invalid value received: `{data}`. Allowed: {list(choices.keys())}"
            ) from e
