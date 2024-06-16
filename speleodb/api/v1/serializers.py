#!/usr/bin/env python
# -*- coding: utf-8 -*-
import enum

from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries
from django_countries.fields import Country
from rest_framework import serializers

from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project


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


class ProjectSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)
    latitude = serializers.DecimalField(
        max_digits=11, decimal_places=8, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=11, decimal_places=8, allow_null=True
    )
    software = CustomChoiceField(choices=Project.Software, source="_software")
    visibility = CustomChoiceField(
        choices=Project.Visibility,
        source="_visibility",
        default=Project.Visibility.PRIVATE,
    )

    permission = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()

    class Meta:
        model = Project
        exclude = ("_software", "_visibility")

    def get_permission(self, obj):
        user = self.context.get("user")
        try:
            return obj.get_permission(user=user).level
        except ObjectDoesNotExist:
            return None

    def get_active_mutex(self, obj):
        if obj.active_mutex is None:
            return None
        return {
            "user": obj.active_mutex.user.email,
            "creation_dt": obj.active_mutex.creation_dt,
            "last_modified_dt": obj.active_mutex.last_modified_dt,
        }


class PermissionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    level = CustomChoiceField(choices=Permission.Level, source="_level")

    class Meta:
        fields = ("user", "level", "creation_date", "modified_date")
        model = Permission


class PermissionListSerializer(serializers.ListSerializer):
    child = PermissionSerializer()


class UploadSerializer(serializers.Serializer):
    file_uploaded = serializers.FileField()

    class Meta:
        fields = ["file_uploaded"]
