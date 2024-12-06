#!/usr/bin/env python
# -*- coding: utf-8 -*-

from allauth.account.models import EmailAddress
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
