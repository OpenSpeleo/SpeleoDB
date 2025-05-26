from rest_framework.request import Request

from speleodb.users.models import User


class SDBAPIViewMixin:
    request: Request

    def get_user(self) -> User:
        if not isinstance(user := self.request.user, User):
            raise TypeError(f"Expected type `User` - Received: `{type(user)}`")
        return user
