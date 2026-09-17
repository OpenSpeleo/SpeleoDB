# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any
from typing import ClassVar

from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django_countries import countries
from rest_framework import serializers

from speleodb.users.models import User
from speleodb.utils.serializer_fields import CustomChoiceField
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin
from speleodb.utils.user_identity import validate_user_name


class UserSerializer(SanitizedFieldsMixin, serializers.ModelSerializer[User]):
    sanitized_fields: ClassVar[list[str]] = ["name"]

    country = CustomChoiceField(choices=list(countries))

    class Meta:
        model = User
        fields = [
            "country",
            "email",
            "email_on_projects_updates",
            "email_on_speleodb_updates",
            "name",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        # SanitizedFieldsMixin runs after field validation; tag-only and other
        # non-visible input can become empty only during sanitization.
        if "name" in attrs:
            try:
                validate_user_name(attrs["name"])
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"name": exc.messages}) from exc
        return attrs

    def update(self, instance: User, validated_data: Any) -> User:
        request = self.context.get("request")
        assert request is not None

        email = validated_data.pop("email", None)
        if email is not None and email != request.user.email:
            validate_email(email)
            EmailAddress.objects.add_new_email(request, request.user, email)  # pyright: ignore[reportAttributeAccessIssue]

        return super().update(instance, validated_data)


class UserAutocompleteSerializer(serializers.ModelSerializer[User]):
    """Minimal serializer for user autocomplete dropdowns."""

    label = serializers.SerializerMethodField()  # type: ignore[assignment]

    class Meta:
        model = User
        fields = ["email", "name", "label"]

    def get_label(self, obj: User) -> str:
        return f"{obj.name} <{obj.email}>"
