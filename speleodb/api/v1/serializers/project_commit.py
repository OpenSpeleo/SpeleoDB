# -*- coding: utf-8 -*-

from __future__ import annotations

from rest_framework import serializers

from speleodb.surveys.models import ProjectCommit


class ProjectCommitSerializer(serializers.ModelSerializer[ProjectCommit]):
    class Meta:
        model = ProjectCommit
        fields = [
            "oid",
            "parents",
            "author_name",
            "author_email",
            "message",
            "datetime",
            "tree",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = fields  # all fields read-only for safety
