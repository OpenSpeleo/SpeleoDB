# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.exceptions import ParseError

from speleodb.utils.requests import require_mapping_request_data


def test_require_mapping_request_data_returns_mapping_unchanged() -> None:
    data = {"field": "value"}

    assert require_mapping_request_data(data) is data


def test_require_mapping_request_data_rejects_list_body() -> None:
    with pytest.raises(ParseError) as exc_info:
        require_mapping_request_data([])

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert str(exc_info.value.detail) == "Request body must be a JSON object."
