#!/usr/bin/env python
# -*- coding: utf-8 -*-


from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices


class PermissionLevel(BaseIntegerChoices):
    READ_ONLY = (0, "READ_ONLY")
    READ_AND_WRITE = (1, "READ_AND_WRITE")
    ADMIN = (2, "ADMIN")

    @classproperty
    def choices_no_admin(cls) -> list[tuple[int, str]]:  # noqa: N805
        return [member for member in PermissionLevel.choices if member[0] < cls.ADMIN]  # type: ignore[operator]

    @classproperty
    def values_no_admin(cls) -> list[int]:  # noqa: N805
        return [value for value in PermissionLevel.values if value < cls.ADMIN]  # type: ignore[operator]

    @classproperty
    def members_no_admin(cls) -> list["PermissionLevel"]:  # noqa: N805
        return [
            member  # type: ignore[misc]
            for member in PermissionLevel.members  # type: ignore[arg-type]
            if member.value < cls.ADMIN  # type: ignore[operator]
        ]
