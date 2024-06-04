from django.urls import resolve


class ViewNameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        url_name = resolve(request.path).url_name
        request.url_name = url_name

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response
