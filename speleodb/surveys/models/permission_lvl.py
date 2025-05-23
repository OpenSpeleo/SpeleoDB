#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any

from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices


class PermissionLevel(BaseIntegerChoices):
    READ_ONLY = (0, "READ_ONLY")
    READ_AND_WRITE = (1, "READ_AND_WRITE")
    ADMIN = (2, "ADMIN")

    @classproperty
    def choices_no_admin(cls) -> list[tuple[None, Any]]:  # noqa: N805
        return [(member.value, member.label) for member in cls if member != cls.ADMIN]  # pyright: ignore[reportGeneralTypeIssues]
