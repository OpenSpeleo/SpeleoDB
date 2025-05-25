#!/usr/bin/env python
# -*- coding: utf-8 -*-

from speleodb.utils.decorators import classproperty
from speleodb.utils.django_base_models import BaseIntegerChoices


class PermissionLevel(BaseIntegerChoices):
    READ_ONLY = 0
    READ_AND_WRITE = 1
    ADMIN = 2

    @classproperty
    def choices_no_admin(cls) -> list[tuple[int, str]]:  # noqa: N805
        return [member for member in PermissionLevel.choices if member[0] < cls.ADMIN]
