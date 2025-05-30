#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any

from rest_framework import serializers


class UploadSerializer(serializers.Serializer[Any]):
    file_uploaded = serializers.FileField()

    class Meta:
        fields = ["file_uploaded"]
