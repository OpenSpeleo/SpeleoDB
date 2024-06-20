#!/usr/bin/env python
# -*- coding: utf-8 -*-


from allauth.account import signals
from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.password_change import logout_on_password_change
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django_countries import countries
from rest_framework import serializers

from speleodb.users.models import User
from speleodb.utils.serializer_fields import CustomChoiceField


class UserSerializer(serializers.ModelSerializer):
    country = CustomChoiceField(choices=countries)

    class Meta:
        model = User
        fields = [
            "country",
            "email",
            "email_on_projects_updates",
            "email_on_speleodb_updates",
            "name",
        ]

    def update(self, instance, validated_data) -> User:
        request = self.context.get("request")

        email = validated_data.pop("email", None)
        if email is not None and email != request.user.email:
            validate_email(email)
            EmailAddress.objects.add_new_email(request, request.user, email)

        return super().update(instance, validated_data)


class AuthTokenSerializer(serializers.Serializer):
    email = serializers.CharField(label="Email", write_only=True, required=True)
    password = serializers.CharField(
        label="Password",
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
        required=True,
    )

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
