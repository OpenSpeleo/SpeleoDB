from typing import Self

from django.db import models

from speleodb.utils.decorators import classproperty


class BaseIntegerChoices(models.IntegerChoices):
    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls._member_map_[value]  # type: ignore[return-value]

    @classmethod
    def from_value(cls, value: int) -> Self:
        return cls._value2member_map_[value]  # type: ignore[return-value]

    @classproperty
    def members(cls) -> list[Self]:  # noqa: N805
        return list(cls._member_map_.values())  # type: ignore[attr-defined]
