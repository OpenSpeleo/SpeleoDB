import hashlib
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from speleodb.processors._impl.compass_toml import COMPASS_TOML_KNOWN_VERSIONS
from speleodb.processors._impl.compass_toml import CompassTOML
from speleodb.processors._impl.compass_toml import (
    build_compass_config_from_upload_filenames,
)
from speleodb.processors._impl.compass_toml import (
    build_compass_toml_bytes_from_upload_filenames,
)

if TYPE_CHECKING:
    from pathlib import Path

    from packaging.version import Version

# ----------------------------------------------------------------------
# Test data
# ----------------------------------------------------------------------

VALID_TOML = """[speleodb]
id = "53b76eb6-0694-4b6f-a260-f875f5182222"
version = "{version}"

[project]
mak_file = "project.mak"
dat_files = [
    "data/file1.dat",
    "data/file2.dat",
    "data/file3.dat",
]
plt_files = []
"""


INVALID_VERSION_TOML = VALID_TOML.format(version="99.99.99")
INVALID_MAK_FILE_TOML = VALID_TOML.replace("project.mak", "project.txt")
INVALID_DAT_FILE_TOML = VALID_TOML.replace('"data/file2.dat"', '"data/file2.txt"')
INVALID_PLT_FILE_TOML = VALID_TOML.replace(
    "plt_files = []", 'plt_files = ["plot.wrong"]'
)


# ----------------------------------------------------------------------
# Utility: write TOML to tmp path
# ----------------------------------------------------------------------


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tmp_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.toml"
    p.write_text(content, encoding="utf-8")
    return p


# ----------------------------------------------------------------------
# Basic Load + Validation (File)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("version", COMPASS_TOML_KNOWN_VERSIONS)
def test_load_valid_file(version: Version, tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, VALID_TOML.format(version=version))
    cfg = CompassTOML.from_toml(path)

    assert str(cfg.speleodb.id) == "53b76eb6-0694-4b6f-a260-f875f5182222"
    assert cfg.speleodb.version == str(version)
    assert cfg.project.mak_file.endswith(".mak")
    assert all(d.endswith(".dat") for d in cfg.project.dat_files)
    assert cfg.project.plt_files == []


# ----------------------------------------------------------------------
# Basic Load + Validation (BytesIO)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("version", COMPASS_TOML_KNOWN_VERSIONS)
def test_load_valid_bytesio(version: Version) -> None:
    bio = BytesIO(VALID_TOML.format(version=version).encode("utf-8"))
    cfg = CompassTOML.from_toml(bio)

    assert cfg.project.mak_file == "project.mak"
    assert all(d.endswith(".dat") for d in cfg.project.dat_files)
    assert cfg.project.plt_files == []


# ----------------------------------------------------------------------
# Invalid Version
# ----------------------------------------------------------------------


def test_invalid_version(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_VERSION_TOML)
    with pytest.raises(ValueError, match="Unknown version"):
        CompassTOML.from_toml(path)


def test_invalid_version_bytesio() -> None:
    bio = BytesIO(INVALID_VERSION_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match="Unknown version"):
        CompassTOML.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid mak_file
# ----------------------------------------------------------------------


def test_invalid_mak_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_MAK_FILE_TOML)
    with pytest.raises(ValueError, match=r"mak_file must end with .mak"):
        CompassTOML.from_toml(path)


def test_invalid_mak_file_bytesio() -> None:
    bio = BytesIO(INVALID_MAK_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"mak_file must end with .mak"):
        CompassTOML.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid dat_files
# ----------------------------------------------------------------------


def test_invalid_dat_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_DAT_FILE_TOML)
    with pytest.raises(ValueError, match=r"must end with .dat"):
        CompassTOML.from_toml(path)


def test_invalid_dat_file_bytesio() -> None:
    bio = BytesIO(INVALID_DAT_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"must end with .dat"):
        CompassTOML.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid plt_files
# ----------------------------------------------------------------------


def test_invalid_plt_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_PLT_FILE_TOML)
    with pytest.raises(ValueError, match=r"must end with .plt"):
        CompassTOML.from_toml(path)


def test_invalid_plt_file_bytesio() -> None:
    bio = BytesIO(INVALID_PLT_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"must end with .plt"):
        CompassTOML.from_toml(bio)


# ----------------------------------------------------------------------
# Write to file
# ----------------------------------------------------------------------


@pytest.mark.parametrize("version", COMPASS_TOML_KNOWN_VERSIONS)
def test_to_toml_file(version: Version, tmp_path: Path) -> None:
    # Load valid config
    path = write_tmp_toml(tmp_path, VALID_TOML.format(version=version))
    cfg = CompassTOML.from_toml(path)

    # Write to new file
    out_file = tmp_path / "output.toml"
    cfg.to_toml(out_file)

    assert out_file.exists()

    # Reload and verify
    cfg2 = CompassTOML.from_toml(out_file)
    assert cfg2 == cfg  # Ensure round-trip consistency


# ----------------------------------------------------------------------
# Write to BytesIO
# ----------------------------------------------------------------------


@pytest.mark.parametrize("version", COMPASS_TOML_KNOWN_VERSIONS)
def test_to_toml_bytesio(version: Version) -> None:
    bio = BytesIO(VALID_TOML.format(version=version).encode("utf-8"))
    cfg = CompassTOML.from_toml(bio)

    out = BytesIO()
    cfg.to_toml(out)

    # Read back
    out.seek(0)
    cfg2 = CompassTOML.from_toml(out)

    assert cfg2 == cfg
    assert "project.mak" in out.getvalue().decode("utf-8")


@pytest.mark.parametrize("version", COMPASS_TOML_KNOWN_VERSIONS)
def test_roundtrip_sha256_consistency(version: Version, tmp_path: Path) -> None:
    # -----------------------------------------------------
    # 1. Write TOML to disk
    # -----------------------------------------------------
    input_f = tmp_path / "input.toml"
    input_f.write_text(VALID_TOML.format(version=version), encoding="utf-8")

    # -----------------------------------------------------
    # 2. Compute first hash
    # -----------------------------------------------------
    hash_before = sha256_of_file(input_f)

    # -----------------------------------------------------
    # 3. Load from disk
    # -----------------------------------------------------
    loaded = CompassTOML.from_toml(input_f)

    # -----------------------------------------------------
    # 4. Write TOML again after parsing
    # -----------------------------------------------------
    output_f = tmp_path / "output.toml"
    loaded.to_toml(output_f)

    # -----------------------------------------------------
    # 5. Compute second hash
    # -----------------------------------------------------
    hash_after = sha256_of_file(output_f)

    # print(f"`{input_f.read_text(encoding='utf-8')=}`")
    # print(f"`{output_f.read_text(encoding='utf-8')=}`")

    # -----------------------------------------------------
    # 6. Ensure TOML bytes are identical
    # -----------------------------------------------------
    assert hash_before == hash_after, (
        f"TOML serialization is not stable: before={hash_before} after={hash_after}"
    )


def test_build_compass_config_from_upload_filenames_includes_plt() -> None:
    cfg = build_compass_config_from_upload_filenames(
        project_id="53b76eb6-0694-4b6f-a260-f875f5182222",
        filenames=[
            "sample.mak",
            "sample-1.dat",
            "sample-2.dat",
            "sample.plt",
        ],
    )
    assert cfg is not None
    assert cfg.project.mak_file == "sample.mak"
    assert cfg.project.dat_files == ["sample-1.dat", "sample-2.dat"]
    assert cfg.project.plt_files == ["sample.plt"]


def test_build_compass_config_from_upload_filenames_without_mak_returns_none() -> None:
    cfg = build_compass_config_from_upload_filenames(
        project_id="53b76eb6-0694-4b6f-a260-f875f5182222",
        filenames=["sample-1.dat", "sample-2.dat"],
    )
    assert cfg is None


def test_build_compass_toml_bytes_from_upload_filenames_no_cross_validation() -> None:
    # `sample.mak` references sample-1.dat and sample-2.dat,
    # but we intentionally provide only one DAT.
    # This confirms the generation helper does not cross-validate references.
    toml_bytes = build_compass_toml_bytes_from_upload_filenames(
        project_id="53b76eb6-0694-4b6f-a260-f875f5182222",
        filenames=[
            "sample.mak",
            "sample-1.dat",
        ],
    )
    assert toml_bytes is not None

    cfg = CompassTOML.from_toml(BytesIO(toml_bytes))
    assert cfg.project.mak_file == "sample.mak"
    assert cfg.project.dat_files == ["sample-1.dat"]
    assert cfg.project.plt_files == []
