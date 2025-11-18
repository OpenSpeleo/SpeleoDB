from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Annotated

from django.core.exceptions import ValidationError
from django.utils import timezone
from pydantic import AfterValidator
from pydantic import ValidationError as PydanticValidationError


def _not_in_future(v: date | datetime) -> date:
    if v > timezone.now().date():
        raise ValueError("Date cannot be in the future")
    return v


NotFutureDate = Annotated[date, AfterValidator(_not_in_future)]


def pydantic_to_django_validation_error(
    pydantic_error: PydanticValidationError,
    field_name: str = "experiment_fields",
) -> ValidationError:
    """
    Convert Pydantic ValidationError to Django ValidationError.

    Args:
        pydantic_error: The Pydantic validation error to convert
        field_name: The field name to use in the Django ValidationError

    Returns:
        Django ValidationError with formatted error messages
    """
    errors = []
    for error in pydantic_error.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        error_msg = error["msg"]
        # If it's a root-level error, format it nicely
        if field_path == "root":
            errors.append(error_msg)
        else:
            errors.append(f"{field_path}: {error_msg}")
    return ValidationError({field_name: errors})
