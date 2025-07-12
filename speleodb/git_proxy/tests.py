# -*- coding: utf-8 -*-

from __future__ import annotations

import base64

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase

USER_TEST_PASSWORD = "YeeOfLittleFaith"  # noqa: S105


class TestGitProxyServer(BaseAPITestCase):
    def _get_token_auth(self) -> str:
        return f"{self.header_prefix}{self.token.key}"

    def _get_basic_auth(self) -> str:
        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        return "Basic {}".format(
            base64.b64encode(f"{self.user.email}:{USER_TEST_PASSWORD}".encode()).decode(
                "utf-8"
            )
        )

    # def test_invalid_token(self):
    #     endpoint = reverse("git_info", kwargs={"path": "test-repo"})
    #     response = self.client.get(
    #         f"{endpoint}?service=git-upload-pack",
    #         headers={"authorization": "Token invalid-token"},
    #     )
    #     assert (
    #         response.status_code == status.HTTP_401_UNAUTHORIZED
    #     ), response.status_code

    # def test_invalid_basic_auth(self):
    #     endpoint = reverse("git_info", kwargs={"path": "test-repo"})
    #     invalid_auth = base64.b64encode(b"invalid:invalid").decode()
    #     response = self.client.get(
    #         f"{endpoint}?service=git-upload-pack",
    #         headers={"authorization": f"Basic {invalid_auth}"},
    #     )
    #     assert (
    #         response.status_code == status.HTTP_401_UNAUTHORIZED
    #     ), response.status_code

    # @parameterized.expand([True, False])
    # def test_git_info(self, use_token_auth: bool):
    #     endpoint = reverse("git_info", kwargs={"path": "test-repo"})

    #     auth = self._get_token_auth() if use_token_auth else self._get_basic_auth()
    #     response = self.client.get(
    #         f"{endpoint}?service=git-upload-pack", headers={"authorization": auth}
    #     )
    #     assert response.status_code == status.HTTP_200_OK, response.status_code
    #     assert (
    #        response["Content-Type"] == "application/x-git-upload-pack-advertisement"
    #     )

    # @parameterized.expand([True, False])
    # def test_service_post(self, use_token_auth: bool):
    #     target_repo = "test-repo"

    #     endpoint = reverse(
    #         "git_service", kwargs={"path": target_repo, "service": "git-receive-pack"}
    #     )

    #     auth = self._get_token_auth() if use_token_auth else self._get_basic_auth()
    #     response = self.client.post(
    #         endpoint,
    #         data=b"test-data",  # Binary data for Git service
    #         content_type="application/octet-stream",  # Specify binary data type
    #         headers={"authorization": auth},
    #     )

    #     assert response.status_code == status.HTTP_200_OK, response.status_code
    #     assert response["Content-Type"] == "application/x-git-receive-pack-result"

    # @parameterized.expand([True, False])
    # def test_repo_not_found(self, use_token_auth: bool):
    #     endpoint = reverse(
    #         "git_service",
    #         kwargs={"path": "non-existent-repo", "service": "git-receive-pack"},
    #     )

    #     auth = self._get_token_auth() if use_token_auth else self._get_basic_auth()
    #     response = self.client.post(
    #         endpoint,
    #         data=b"test-data",  # Binary data for Git service
    #         content_type="application/octet-stream",  # Specify binary data type
    #         headers={"authorization": auth},
    #     )
    #     assert response.status_code == status.HTTP_404_NOT_FOUND, response.status_code
    #     assert response.json()["error"] == "Repository not found"

    # @parameterized.expand([True, False])
    # def test_invalid_service(self, use_token_auth: bool):
    #     endpoint = reverse(
    #         "git_service", kwargs={"path": "test-repo", "service": "invalid-service"}
    #     )

    #     auth = self._get_token_auth() if use_token_auth else self._get_basic_auth()
    #     response = self.client.post(
    #         endpoint,
    #         data=b"test-data",  # Binary data for Git service
    #         content_type="application/octet-stream",  # Specify binary data type
    #         headers={"authorization": auth},
    #     )
    #     assert (response.status_code == status.HTTP_400_BAD_REQUEST),
    #         response.status_code
    #     assert response.json()["error"] == "Invalid service"
