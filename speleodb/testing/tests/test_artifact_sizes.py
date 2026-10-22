"""Keep regression inputs small, including the contents of compressed fixtures."""

from pathlib import Path
from zipfile import ZipFile
from zipfile import is_zipfile

MAX_ARTIFACT_BYTES = 100_000
ARTIFACTS = Path(__file__).resolve().parents[2] / "api/v2/tests/artifacts"


def test_backend_artifacts_stay_within_the_small_fixture_budget() -> None:
    for path in ARTIFACTS.rglob("*"):
        if not path.is_file():
            continue
        assert path.stat().st_size <= MAX_ARTIFACT_BYTES, path
        if is_zipfile(path):
            with ZipFile(path) as archive:
                assert sum(info.file_size for info in archive.infolist()) <= (
                    MAX_ARTIFACT_BYTES
                ), path
