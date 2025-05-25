from typing import Self

from django.db import models


class BaseIntegerChoices(models.IntegerChoices):
    @classmethod
    def from_str(cls, value: str) -> Self:
        value = getattr(cls, value)
        assert isinstance(value, cls)
        return value

    @classmethod
    def from_value(cls, value: int) -> Self:
        return cls._value2member_map_[value]  # type: ignore[return-value]
