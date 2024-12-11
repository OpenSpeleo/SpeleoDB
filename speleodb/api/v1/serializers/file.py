#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework import serializers


class UploadSerializer(serializers.Serializer):
    file_uploaded = serializers.FileField()

    class Meta:
        fields = ["file_uploaded"]
