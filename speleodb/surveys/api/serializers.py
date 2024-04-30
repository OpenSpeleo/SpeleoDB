#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import serializers

from speleodb.surveys.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "owner",
            "fork_from",
            "creation_date",
            "name",
            "description",
            "longitude",
            "latitude",
            "git_name",
        ]
