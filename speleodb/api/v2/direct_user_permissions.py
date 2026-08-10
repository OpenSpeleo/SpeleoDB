# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import NotRequired
from typing import TypedDict

from speleodb.common.enums import PermissionLevel
from speleodb.users.models import User
from speleodb.utils.exceptions import BadRequestError
from speleodb.utils.exceptions import MissingFieldError
from speleodb.utils.exceptions import NotAuthorizedError
from speleodb.utils.exceptions import UserNotActiveError
from speleodb.utils.exceptions import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping


class DirectUserPermissionData(TypedDict):
    """Validated input shared by direct-user permission endpoints."""

    user: User
    level: NotRequired[PermissionLevel]


def parse_direct_user_permission_data(
    *,
    request_user: User,
    data: Mapping[str, Any],
    skip_level: bool = False,
) -> DirectUserPermissionData:
    """Validate a direct-user permission mutation payload.

    Projects have additional team and WEB_VIEWER semantics. Direct GIS entities
    instead share this smaller contract: an active target user and one of the
    three collaboration levels.
    """

    try:
        raw_user = data["user"]
    except KeyError as exc:
        raise MissingFieldError("Attribute: `user` is missing.") from exc

    if not isinstance(raw_user, str):
        raise BadRequestError("Attribute: `user` must be an email address.")

    try:
        target_user = User.objects.get(email=raw_user)
    except User.DoesNotExist as exc:
        raise UserNotFoundError(f"The user: `{raw_user}` does not exist.") from exc

    if request_user == target_user:
        raise NotAuthorizedError("A user can not edit their own permission")

    if not target_user.is_active:
        raise UserNotActiveError(f"The user: `{raw_user}` is inactive.")

    permission_data: DirectUserPermissionData = {"user": target_user}
    if skip_level:
        return permission_data

    try:
        raw_level = data["level"]
    except KeyError as exc:
        raise MissingFieldError("Attribute: `level` is missing.") from exc

    allowed_levels = {str(label) for _, label in PermissionLevel.choices_no_webviewer}
    if not isinstance(raw_level, str) or raw_level.upper() not in allowed_levels:
        raise BadRequestError(f"Invalid value received for `level`: `{raw_level}`")

    permission_data["level"] = PermissionLevel.from_str(raw_level.upper())
    return permission_data
