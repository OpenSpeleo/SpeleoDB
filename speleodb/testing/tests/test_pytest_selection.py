"""A successful default run must not conceal unexecuted coverage."""

from __future__ import annotations

import pytest

pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def isolated_pytest_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Child runs exercise only selection policy, without the application's
    # settings or the enclosing invocation's reporting plugins and destinations.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)


@pytest.mark.parametrize(
    "source",
    [
        "import pytest\npytest.skip('missing prerequisite', allow_module_level=True)",
        "import pytest\n@pytest.mark.skipif(True, reason='missing prerequisite')\n"
        "def test_required(): pass",
    ],
)
def test_implicit_skips_fail_the_invocation(
    pytester: pytest.Pytester,
    source: str,
) -> None:
    pytester.makepyfile(source)
    result = pytester.runpytest_subprocess(
        "-p",
        "speleodb.testing.pytest_selection",
        "-o",
        "addopts=",
        "-q",
    )
    assert result.ret != pytest.ExitCode.OK
    result.stdout.fnmatch_lines(["*Implicit test skips are forbidden*"])


@pytest.mark.parametrize(
    ("arguments", "passed", "deselected"),
    [
        ([], 5, 0),
        (["--light", "--offline"], 3, 2),
        (["-m", "not live_services and not local_infrastructure"], 3, 2),
    ],
)
def test_coverage_is_excluded_only_when_requested(
    pytester: pytest.Pytester,
    arguments: list[str],
    passed: int,
    deselected: int,
) -> None:
    pytester.makepyfile(
        """
        import pytest
        def test_ordinary(): pass
        @pytest.mark.skip_if_lighttest
        def test_repository(): pass
        @pytest.mark.skip_if_offline
        def test_network(): pass
        @pytest.mark.live_services
        def test_worker(): pass
        @pytest.mark.local_infrastructure
        def test_local_gitlab(): pass
        """
    )
    result = pytester.runpytest_subprocess(
        "-p",
        "speleodb.testing.pytest_selection",
        "-o",
        "addopts=",
        "-q",
        *arguments,
    )
    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=passed, deselected=deselected)
