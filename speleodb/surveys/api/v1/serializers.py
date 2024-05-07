#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from speleodb.surveys.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    permission = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = "__all__"

    def get_permission(self, obj):
        user = self.context.get("user")
        try:
            return obj.get_permission(user=user).level_name
        except ObjectDoesNotExist:
            return None


# Serializers define the API representation.
class UploadSerializer(serializers.Serializer):
    file_uploaded = serializers.FileField()

    class Meta:
        fields = ["file_uploaded"]
