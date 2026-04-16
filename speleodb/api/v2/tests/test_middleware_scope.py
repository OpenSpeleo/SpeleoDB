# -*- coding: utf-8 -*-

"""Contract tests pinning the wrap-middleware scope.

``DRFWrapResponseMiddleware`` is now scoped to ``/api/v1/`` only. These
tests make the canonical invariants of the v2 unwrap migration part of
the test suite so a future middleware edit cannot silently break either
half of the contract:

* ``/api/v1/...`` responses MUST be wrapped with the v1 envelope
  (``data``, ``url``, ``timestamp``, ``success``).
* ``/api/v2/...`` responses MUST be returned verbatim, with no envelope
  rewrap on success OR on error.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase

V1_ENVELOPE_KEYS = {"data", "url", "timestamp", "success"}


@pytest.mark.django_db
class MiddlewareScopeContractTests(BaseAPITestCase):
    """The same view class is mounted under both ``/api/v1/projects/`` and
    ``/api/v2/projects/``. The wrap middleware must wrap only the v1
    responses. Authentication errors must behave the same way."""

    # ------------------------------------------------------------------ #
    # Happy path -- authenticated GET
    # ------------------------------------------------------------------ #

    def test_v1_projects_list_is_wrapped(self) -> None:
        response = self.client.get(
            reverse("api:v1:projects"), headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert isinstance(response.data, dict), response.data
        assert V1_ENVELOPE_KEYS.issubset(response.data.keys()), response.data
        assert response.data["success"] is True
        assert isinstance(response.data["data"], list)
        assert response.data["url"].endswith(reverse("api:v1:projects"))

    def test_v2_projects_list_is_raw(self) -> None:
        response = self.client.get(
            reverse("api:v2:projects"), headers={"authorization": self.auth}
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert isinstance(response.data, list), response.data
        # v2 must have zero envelope residue
        if response.data:
            sample = response.data[0]
            assert isinstance(sample, dict)
            assert V1_ENVELOPE_KEYS.isdisjoint(sample.keys()), sample

    # ------------------------------------------------------------------ #
    # Error path -- missing credentials
    # ------------------------------------------------------------------ #

    def test_v1_unauthenticated_error_is_wrapped(self) -> None:
        """DRF's default ``NotAuthenticated`` handler returns ``{"detail":
        "..."}``. For v1 the middleware merges that into the envelope and
        sets ``success: False``.

        Note: DRF returns 403 (not 401) when no credentials are provided
        for a view that only accepts Session/Token authentication -- it
        has no way to issue a ``WWW-Authenticate`` challenge. This is the
        project's actual behaviour for unauthenticated GETs.
        """
        response = self.client.get(reverse("api:v1:projects"))

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert isinstance(response.data, dict)
        assert "success" in response.data
        assert response.data["success"] is False
        assert "url" in response.data
        assert "timestamp" in response.data
        # DRF's detail is preserved inside the envelope
        assert "detail" in response.data

    def test_v2_unauthenticated_error_is_raw(self) -> None:
        """v2 must return DRF's default ``{"detail": "..."}`` unchanged --
        no ``success`` / ``url`` / ``timestamp`` keys injected."""
        response = self.client.get(reverse("api:v2:projects"))

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert isinstance(response.data, dict)
        assert "detail" in response.data
        assert "success" not in response.data
        assert "url" not in response.data
        assert "timestamp" not in response.data
