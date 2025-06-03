from __future__ import annotations

from typing import TYPE_CHECKING

from speleodb.users.models import User

if TYPE_CHECKING:
    from rest_framework.request import Request


class SDBAPIViewMixin:
    request: Request

    def get_user(self) -> User:
        if not isinstance(user := self.request.user, User):
            raise TypeError(f"Expected type `User` - Received: `{type(user)}`")
        return user
