#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture()
def user(db) -> User:
    return UserFactory()
