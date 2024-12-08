#!/usr/bin/env python
# -*- coding: utf-8 -*-

from allauth.account import signals
from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.password_change import logout_on_password_change
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers


class PasswordChangeSerializer(serializers.Serializer):
    oldpassword = serializers.CharField(
        label="Old Password",
        style={"input_type": "password", "placeholder": "Old Password"},
        trim_whitespace=False,
        write_only=True,
        required=True,
    )
    password1 = serializers.CharField(
        label="New Password",
        style={"input_type": "password", "placeholder": "Old Password"},
        trim_whitespace=False,
        write_only=True,
        required=True,
    )
    password2 = serializers.CharField(
        label="New Password (Repeat)",
        style={"input_type": "password", "placeholder": "Old Password"},
        trim_whitespace=False,
        write_only=True,
        required=True,
    )

    def validate(self, attrs):
        oldpassword = attrs.get("oldpassword")
        password1 = attrs.get("password1")
        password2 = attrs.get("password2")

        user = self.context.get("request").user

        if password1 != password2:
            raise ValidationError("Password mismatch: `password1` != `password2`")

        if not user.check_password(oldpassword):
            raise ValidationError("Current password is not valid.")

        if oldpassword == password1:
            raise ValidationError("The new password is identical to the old password.")

        if not settings.DEBUG:
            validate_password(password1, user=user)

        return {"password": password1}

    def save(self):
        password = self.validated_data["password"]
        request = self.context.get("request")
        user = request.user

        get_adapter(request).set_password(user, password)
        user.save()
        signals.password_changed.send(
            sender=user.__class__,
            request=request,
            user=user,
        )

        logout_on_password_change(request, user)
