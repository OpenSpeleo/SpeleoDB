# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from typing import TYPE_CHECKING
from typing import Any

from django_countries import countries
from factory.django import DjangoModelFactory
from factory.faker import Faker
from factory.helpers import post_generation

from speleodb.users.models import User

if TYPE_CHECKING:
    from collections.abc import Sequence

    from factory.base import StubObject


class UserFactory(DjangoModelFactory[User]):
    email: str = Faker("email")  # type: ignore[assignment]
    name: str = Faker("name")  # type: ignore[assignment]
    country: str = random.choice(countries).code  # pyright: ignore[reportAttributeAccessIssue]

    class Meta:
        model = User
        django_get_or_create = ["email"]

    @post_generation
    def password(self, create: bool, extracted: Sequence[Any], **kwargs: Any) -> None:
        password = (
            extracted
            if extracted
            else Faker(
                "password",
                length=42,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})  # type: ignore[arg-type]
        )
        self.set_password(password)  # type: ignore[attr-defined]

    @classmethod
    def _after_postgeneration(
        cls,
        instance: User | StubObject,
        create: bool,
        results: dict[str, Any] | None = None,
    ) -> None:
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:  # type: ignore[attr-defined]
            # Some post-generation hooks ran, and may have modified us.
            instance.save()  # type: ignore[union-attr]
