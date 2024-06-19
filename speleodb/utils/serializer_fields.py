#!/usr/bin/env python
# -*- coding: utf-8 -*-

import enum

from django_countries.fields import Country
from rest_framework import serializers


class CustomChoiceField(serializers.ChoiceField):
    def to_representation(self, obj):
        if obj == "" and self.allow_blank:
            return obj

        if isinstance(obj, Country):
            return obj.code

        val = self._choices[obj]

        if isinstance(val, enum.Enum):
            return self._choices[obj].name

        return val

    def to_internal_value(self, data):
        if self.field_name == "country":
            return super().to_internal_value(data)

        return getattr(self._kwargs["choices"], data)