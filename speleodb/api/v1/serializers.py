#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
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
