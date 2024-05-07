from contextlib import suppress

from rest_framework import exceptions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from speleodb.surveys.api.v1.utils import SortedResponse
from speleodb.surveys.api.v1.utils import get_timestamp


class CustomAPIView(GenericAPIView):
    def base_request(self, view_fn, request, *args, **kwargs):
        try:
            view_fn = getattr(self, view_fn)
        except AttributeError as e:
            raise exceptions.MethodNotAllowed(request.method) from e

        payload = {}
        http_status = status.HTTP_200_OK
        try:
            with suppress(AttributeError):
                # remove the lookup field. Not needed
                del kwargs[self.lookup_field]
            response = view_fn(request, *args, **kwargs)

            if isinstance(response, Response):
                payload.update(response.data)
                http_status = response.status_code

            elif isinstance(response, (list, tuple, dict)):
                payload["data"] = response

            else:
                payload["data"] = f"Unsupported response type: {type(response)}"
                http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        except Exception as e:  # noqa: BLE001
            payload["data"] = {}
            payload["error"] = f"An error occured in the process: {e}"
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        payload["url"] = request.build_absolute_uri()
        payload["timestamp"] = get_timestamp()
        payload["success"] = http_status in range(200, 300)
        return SortedResponse(payload, status=http_status)

    def get(self, request, *args, **kwargs):
        return self.base_request("_get", request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.base_request("_post", request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.base_request("_put", request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.base_request("_delete", request, *args, **kwargs)
