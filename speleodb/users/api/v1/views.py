import contextlib

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken as _ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from speleodb.users.api.v1.serializers import AuthTokenSerializer
from speleodb.users.api.v1.serializers import UserSerializer
from speleodb.users.models import User
from speleodb.utils.utils import wrap_response_with_status


class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "pk"

    def get_queryset(self, *args, **kwargs):
        assert isinstance(self.request.user.email, str)
        return self.queryset.filter(email=self.request.user.email)

    @action(detail=False)
    def me(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)


class ObtainAuthToken(_ObtainAuthToken):
    serializer_class = AuthTokenSerializer

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return wrap_response_with_status(
                lambda *a, **kw: Response(
                    status=status.HTTP_401_UNAUTHORIZED,
                    data={"error": "Not authenticated"},
                ),
                request,
            )
        token, created = Token.objects.get_or_create(user=request.user)
        return wrap_response_with_status(
            lambda *a, **kw: Response({"token": token.key}), request
        )

    def post(self, request, *args, **kwargs):
        return wrap_response_with_status(super().post, request, *args, **kwargs)

    def _patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # delete to recreate a fresh token
        with contextlib.suppress(ObjectDoesNotExist):
            Token.objects.get(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})

    def patch(self, request, *args, **kwargs):
        return wrap_response_with_status(self._patch, request, *args, **kwargs)
