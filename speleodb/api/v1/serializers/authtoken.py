#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token


class AuthTokenSerializer(serializers.Serializer[Token]):
    email = serializers.CharField(label="Email", write_only=True, required=True)
    password = serializers.CharField(
        label="Password",
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
        required=True,
    )

    def validate(self, attrs: Any) -> Any:
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
