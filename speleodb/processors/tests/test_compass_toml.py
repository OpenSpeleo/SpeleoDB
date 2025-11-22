import hashlib
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from speleodb.processors._impl.compass_toml import KNOWN_VERSIONS
from speleodb.processors._impl.compass_toml import CompassConfig

if TYPE_CHECKING:
    from pathlib import Path

# ----------------------------------------------------------------------
# Test data
# ----------------------------------------------------------------------

VALID_TOML = """
[speleodb]
id = "53b76eb6-0694-4b6f-a260-f875f5182222"
version = "0.0.1"

[project]
name = "Sample Project"
description = "This is a sample SpeleoDB Compass project."
mak_file = "project.mak"
dat_files = [
    "data/file1.dat",
    "data/file2.dat",
    "data/file3.dat",
]
plt_files = []
"""


INVALID_VERSION_TOML = VALID_TOML.replace('version = "0.0.1"', 'version = "99.99.99"')
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


def test_load_valid_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, VALID_TOML)
    cfg = CompassConfig.from_toml(path)

    assert str(cfg.speleodb.id) == "53b76eb6-0694-4b6f-a260-f875f5182222"
    assert cfg.speleodb.version == str(KNOWN_VERSIONS[0])
    assert cfg.project.name == "Sample Project"
    assert cfg.project.mak_file.endswith(".mak")
    assert all(d.endswith(".dat") for d in cfg.project.dat_files)
    assert cfg.project.plt_files == []


# ----------------------------------------------------------------------
# Basic Load + Validation (BytesIO)
# ----------------------------------------------------------------------


def test_load_valid_bytesio() -> None:
    bio = BytesIO(VALID_TOML.encode("utf-8"))
    cfg = CompassConfig.from_toml(bio)

    assert cfg.project.name == "Sample Project"
    assert cfg.project.mak_file == "project.mak"


# ----------------------------------------------------------------------
# Invalid Version
# ----------------------------------------------------------------------


def test_invalid_version(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_VERSION_TOML)
    with pytest.raises(ValueError, match="Unknown version"):
        CompassConfig.from_toml(path)


def test_invalid_version_bytesio() -> None:
    bio = BytesIO(INVALID_VERSION_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match="Unknown version"):
        CompassConfig.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid mak_file
# ----------------------------------------------------------------------


def test_invalid_mak_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_MAK_FILE_TOML)
    with pytest.raises(ValueError, match=r"mak_file must end with .mak"):
        CompassConfig.from_toml(path)


def test_invalid_mak_file_bytesio() -> None:
    bio = BytesIO(INVALID_MAK_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"mak_file must end with .mak"):
        CompassConfig.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid dat_files
# ----------------------------------------------------------------------


def test_invalid_dat_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_DAT_FILE_TOML)
    with pytest.raises(ValueError, match=r"must end with .dat"):
        CompassConfig.from_toml(path)


def test_invalid_dat_file_bytesio() -> None:
    bio = BytesIO(INVALID_DAT_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"must end with .dat"):
        CompassConfig.from_toml(bio)


# ----------------------------------------------------------------------
# Invalid plt_files
# ----------------------------------------------------------------------


def test_invalid_plt_file(tmp_path: Path) -> None:
    path = write_tmp_toml(tmp_path, INVALID_PLT_FILE_TOML)
    with pytest.raises(ValueError, match=r"must end with .plt"):
        CompassConfig.from_toml(path)


def test_invalid_plt_file_bytesio() -> None:
    bio = BytesIO(INVALID_PLT_FILE_TOML.encode("utf-8"))
    with pytest.raises(ValueError, match=r"must end with .plt"):
        CompassConfig.from_toml(bio)


# ----------------------------------------------------------------------
# Write to file
# ----------------------------------------------------------------------


def test_to_toml_file(tmp_path: Path) -> None:
    # Load valid config
    path = write_tmp_toml(tmp_path, VALID_TOML)
    cfg = CompassConfig.from_toml(path)

    # Write to new file
    out_file = tmp_path / "output.toml"
    cfg.to_toml(out_file)

    assert out_file.exists()

    # Reload and verify
    cfg2 = CompassConfig.from_toml(out_file)
    assert cfg2 == cfg  # Ensure round-trip consistency


# ----------------------------------------------------------------------
# Write to BytesIO
# ----------------------------------------------------------------------


def test_to_toml_bytesio() -> None:
    bio = BytesIO(VALID_TOML.encode("utf-8"))
    cfg = CompassConfig.from_toml(bio)

    out = BytesIO()
    cfg.to_toml(out)

    # Read back
    out.seek(0)
    cfg2 = CompassConfig.from_toml(out)

    assert cfg2 == cfg
    assert "project.mak" in out.getvalue().decode("utf-8")


def test_roundtrip_sha256_consistency(tmp_path: Path) -> None:
    # -----------------------------------------------------
    # 1. Write TOML to disk
    # -----------------------------------------------------
    input_f = tmp_path / "input.toml"
    input_f.write_text(
        """[speleodb]
id = "53b76eb6-0694-4b6f-a260-f875f5182222"
version = "0.0.1"

[project]
name = "Sample Project"
description = "This is a sample SpeleoDB Compass project."
mak_file = "project.mak"
dat_files = ["data/file1.dat", "data/file2.dat", "data/file3.dat"]
plt_files = []
""",
        encoding="utf-8",
    )

    # -----------------------------------------------------
    # 2. Compute first hash
    # -----------------------------------------------------
    hash_before = sha256_of_file(input_f)

    # -----------------------------------------------------
    # 3. Load from disk
    # -----------------------------------------------------
    loaded = CompassConfig.from_toml(input_f)

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
