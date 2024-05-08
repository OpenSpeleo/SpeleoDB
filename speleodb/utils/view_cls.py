#!/usr/bin/env python
# -*- coding: utf-8 -*-

from rest_framework.generics import GenericAPIView

from speleodb.utils.api_decorators import request_wrapper


class CustomAPIView(GenericAPIView):
    @request_wrapper
    def get(self, request, *args, **kwargs):
        pass

    @request_wrapper
    def post(self, request, *args, **kwargs):
        pass

    @request_wrapper
    def put(self, request, *args, **kwargs):
        pass

    @request_wrapper
    def delete(self, request, *args, **kwargs):
        pass
