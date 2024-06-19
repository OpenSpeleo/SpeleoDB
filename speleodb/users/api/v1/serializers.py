#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate
from django_countries import countries
from rest_framework import serializers

from speleodb.users.models import User
from speleodb.utils.serializer_fields import CustomChoiceField


class UserSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)
    name = serializers.CharField(allow_blank=False)
    email = serializers.EmailField(allow_blank=False, read_only=True)
    email_on_projects_updates = serializers.BooleanField()
    email_on_speleodb_updates = serializers.BooleanField()

    class Meta:
        model = User
        # fields = "__all__"
        fields = [
            "country",
            "email",
            "email_on_projects_updates",
            "email_on_speleodb_updates",
            "name",
        ]

    # def get_country(self, obj):
    #     return obj.country.code


class AuthTokenSerializer(serializers.Serializer):
    email = serializers.CharField(label="Email", write_only=True)
    password = serializers.CharField(
        label="Password",
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
    )
    token = serializers.CharField(label="Token", read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                request=self.context.get("request"),
                email=email,
                password=password,
            )

            # The authenticate call simply returns None for is_active=False
            # users. (Assuming the default ModelBackend authentication
            # backend.)
            if not user:
                msg = "Unable to log in with provided credentials."
                raise serializers.ValidationError(msg, code="authorization")
        else:
            msg = 'Must include "email" and "password".'
            raise serializers.ValidationError(msg, code="authorization")

        attrs["user"] = user
        return attrs
