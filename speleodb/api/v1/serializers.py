#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django_countries import countries
from django_countries.fields import Country
from rest_framework import serializers

from speleodb.surveys.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    permission = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    active_mutex = serializers.SerializerMethodField()
    software = serializers.SerializerMethodField()
    visibility = serializers.SerializerMethodField()

    class Meta:
        model = Project
        # fields = "__all__"
        exclude = ("_software", "_visibility")

    def create(self, validated_data):
        # =========== VISIBILITY Validation =========== #
        visibility = self.initial_data.get("visibility", "private")

        if (
            not isinstance(visibility, str)
            or visibility.upper() not in Project.Visibility._member_names_
        ):
            raise ValidationError(
                f"Invalid value received for `visibility`: `{visibility}`"
            )
        visibility = getattr(Project.Visibility, visibility.upper())

        # =========== Country Validation =========== #
        try:
            country = self.initial_data.get("country")
        except KeyError as e:
            raise ValidationError("Value `country` is missing") from e

        if not isinstance(country, str):
            raise ValidationError(f"Invalid value received for `country`: `{country}`")
        country = country.upper()

        if country not in countries:
            raise ValidationError(f"Value `country` does not exist: {country}")

        country = Country(code=country)

        # =========== Software Validation =========== #
        try:
            software = self.initial_data.get("software")
        except KeyError as e:
            raise ValidationError("Value `software` is missing") from e

        if (
            not isinstance(software, str)
            or software.upper() not in Project.Software._member_names_
        ):
            raise ValidationError(
                f"Invalid value received for `software`: `{software}`"
            )
        software = getattr(Project.Software, software.upper())

        # ========================= UPDATE OF THE VALUE DICT ========================= #

        validated_data.update(
            {
                "country": country,
                "_software": software,
                "_visibility": visibility,
            }
        )
        return super().create(validated_data)

    def get_permission(self, obj):
        user = self.context.get("user")
        try:
            return obj.get_permission(user=user).level
        except ObjectDoesNotExist:
            return None

    def get_software(self, obj):
        return obj.software

    def get_visibility(self, obj):
        return obj.visibility

    def get_country(self, obj):
        return obj.country.code

    def get_active_mutex(self, obj):
        if obj.active_mutex is None:
            return None
        return {
            "user": obj.active_mutex.user.email,
            "creation_dt": obj.active_mutex.creation_dt,
            "heartbeat_dt": obj.active_mutex.heartbeat_dt,
        }


class UploadSerializer(serializers.Serializer):
    file_uploaded = serializers.FileField()

    class Meta:
        fields = ["file_uploaded"]
