from unittest import TestCase

import pytest

from speleodb.common.management.commands.preload_projects import Command


@pytest.mark.skip_if_lighttest
class TestMergeDotEnvCommandWithTempfile(TestCase):
    def test_preload_projects(self) -> None:
        # Call the merge function
        command = Command()
        command.handle()
