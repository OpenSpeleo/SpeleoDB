from datetime import date
from datetime import datetime
from typing import Annotated

from django.utils import timezone
from pydantic import AfterValidator


def _not_in_future(v: date | datetime) -> date:
    if v > timezone.now().date():
        raise ValueError("Date cannot be in the future")
    return v


NotFutureDate = Annotated[date, AfterValidator(_not_in_future)]
