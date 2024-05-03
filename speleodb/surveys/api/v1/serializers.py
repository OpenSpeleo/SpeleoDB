#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import serializers
from rest_framework.serializers import FileField
from rest_framework.serializers import Serializer

from speleodb.surveys.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"


# Serializers define the API representation.
class UploadSerializer(Serializer):
    file_uploaded = FileField()

    class Meta:
        fields = ["file_uploaded"]
